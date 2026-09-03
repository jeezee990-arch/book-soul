"""密钥管理（系统 Keyring）。

设计：
- 用系统 Keyring 存 Fernet 密钥（Windows = Credential Locker，macOS = Keychain）
- 第一次启动时生成密钥并存；后续读
- 任何异常（无 keyring daemon / 权限问题）→ 返回 None（调用方降级到"不加密"）
- 支持 backend 注入：测试时传 FakeBackend，避免污染真实 keyring
"""

from __future__ import annotations

import importlib
from typing import Protocol

from loguru import logger

# Fernet 是个大依赖，只在需要时导入
try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[misc,assignment]


class _KeyringLike(Protocol):
    """Keyring 兼容接口（duck typing）。

    真实 ``keyring`` 模块和任何 mock 都满足这个最小接口。
    """

    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, value: str) -> None: ...


# Keyring 服务/用户名约定（跨进程一致）
SERVICE_NAME = "BookSoul"
KEY_USERNAME = "encryption_key"


def _get_default_keyring() -> _KeyringLike | None:
    """导入全局 keyring 模块；失败返回 None。"""
    try:
        keyring = importlib.import_module("keyring")
    except ImportError:
        logger.warning("keyring package not installed; encryption will be disabled")
        return None
    return keyring  # type: ignore[return-value]


def _get_or_create_with_backend(backend: _KeyringLike) -> bytes | None:
    """从给定 backend 读 key，不存在则生成并写回。"""
    if Fernet is None:
        logger.warning("cryptography not installed; encryption will be disabled")
        return None
    try:
        existing = backend.get_password(SERVICE_NAME, KEY_USERNAME)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"keyring get_password failed: {e}; encryption disabled")
        return None
    if existing:
        return existing.encode()

    try:
        key = Fernet.generate_key()
        backend.set_password(SERVICE_NAME, KEY_USERNAME, key.decode())
        return key
    except Exception as e:  # noqa: BLE001
        logger.warning(f"keyring set_password failed: {e}; encryption disabled")
        return None


def get_or_create_key(backend: _KeyringLike | None = None) -> bytes | None:
    """获取或创建 Fernet 密钥。

    Args:
        backend: 可选 keyring 后端（用于测试注入）。None = 用全局 ``keyring`` 模块。

    Returns:
        32-byte url-safe base64 编码的 Fernet key；失败返回 None。
    """
    if backend is None:
        backend = _get_default_keyring()
    if backend is None:
        return None
    return _get_or_create_with_backend(backend)
