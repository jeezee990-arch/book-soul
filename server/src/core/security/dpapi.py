"""Windows DPAPI 封装（Data Protection API）。

用途
----
把 API Key 加密后存到应用数据目录里，做到：

- **明文永不落盘**（不像 .env）
- 文件可以随便拷贝 / 备份 / 同步（不像系统 Keyring 绑死在当前账户）
- 只有当前 Windows 账户 + 当前机器能解密（DPAPI 用用户凭据做密钥派生）
- **零第三方依赖**（直接调 Windows 自带的 crypt32.dll）

原理
----
DPAPI 用当前登录用户的凭据（NTLM hash + profile key）派生会话密钥，
所以别的用户 / 别的机器拿到密文也解不开。
密文头部带 ``DPAPI`` 标记，可以识别。

非 Windows 平台
--------------
本模块在非 Windows 上直接抛 :class:`DPAPIUnavailableError`，
由调用方降级到系统 Keyring（见 :mod:`src.core.security.secret_store`）。
"""

from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes

__all__ = [
    "DPAPIUnavailableError",
    "is_supported",
    "protect",
    "unprotect",
]


class DPAPIUnavailableError(RuntimeError):
    """当前平台不支持 DPAPI。"""


# ===== Windows API 常量 =====

CRYPTPROTECT_UI_FORBIDDEN = 0x01
CRYPTPROTECT_LOCAL_MACHINE = 0x04

# ===== ctypes 结构 =====


class _DataBlob(ctypes.Structure):
    """Windows DATA_BLOB 结构（长度 + 字节指针）。"""

    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _load_crypt32():
    """加载 crypt32.dll 并声明函数签名。"""
    if sys.platform != "win32":
        raise DPAPIUnavailableError(f"DPAPI only works on Windows (current: {sys.platform})")
    try:
        crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    except OSError as e:  # pragma: no cover - Windows 上几乎不会发生
        raise DPAPIUnavailableError(f"cannot load crypt32.dll: {e}") from e

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_wchar_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    return crypt32, kernel32


def _make_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    """构造 DATA_BLOB。

    返回 (blob, buffer) —— buffer 必须由调用方持有，否则指针会悬空。
    """
    buf = ctypes.create_string_buffer(data, max(len(data), 1))
    blob = _DataBlob(
        len(data),
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buf


def is_supported() -> bool:
    """当前平台是否支持 DPAPI。"""
    if sys.platform != "win32":
        return False
    try:
        _load_crypt32()
    except DPAPIUnavailableError:
        return False
    return True


def protect(data: bytes, *, machine: bool = False) -> bytes:
    """加密数据（返回原始密文字节）。

    :param machine: True = 机器级加密（任何用户都能解）；False = 用户级（默认）。
    """
    crypt32, kernel32 = _load_crypt32()
    in_blob, in_buf = _make_blob(data)
    out_blob = _DataBlob()
    flags = CRYPTPROTECT_UI_FORBIDDEN | (CRYPTPROTECT_LOCAL_MACHINE if machine else 0)
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Book Soul",
        None,
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        del in_buf


def unprotect(data: bytes, *, machine: bool = False) -> bytes:
    """解密数据（protect 的逆操作）。"""
    crypt32, kernel32 = _load_crypt32()
    in_blob, in_buf = _make_blob(data)
    out_blob = _DataBlob()
    flags = CRYPTPROTECT_UI_FORBIDDEN | (CRYPTPROTECT_LOCAL_MACHINE if machine else 0)
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        del in_buf


def protect_b64(data: bytes) -> str:
    """加密并 base64 编码（便于存成文本文件）。"""
    return base64.b64encode(protect(data)).decode("ascii")


def unprotect_b64(text: str) -> bytes:
    """解码 base64 并解密。"""
    return unprotect(base64.b64decode(text.encode("ascii")))
