"""API Key 存储（明文永不落盘）。

查找优先级（高 → 低）
--------------------
1. **环境变量**（``.env`` / 系统环境变量，如 ``MIMO_API_KEY``）
   —— 开发期最方便，用户已有习惯，优先级最高
2. **DPAPI 加密文件**（``<data_dir>/secrets/keys.json``）
   —— 打包版默认。Windows 用 DPAPI（系统自带，零依赖）加密：
   文件可随意拷贝/备份/同步，但只有当前 Windows 账户能解密
3. **系统 Keyring**（Windows 凭据管理器 / macOS Keychain）
   —— 非 Windows 平台降级路径
4. ``os.environ`` 兜底

文件格式（JSON）
----------------
.. code-block:: json

    {
      "version": 1,
      "providers": {
        "mimo": "<base64 DPAPI 密文>"
      }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from .dpapi import DPAPIUnavailableError, is_supported, protect_b64, unprotect_b64

__all__ = [
    "SecretStore",
    "get_secret_store",
    "reset_secret_store",
]

SECRETS_DIRNAME = "secrets"
SECRETS_FILENAME = "keys.json"
SECRET_FILE_VERSION = 1


class SecretStore:
    """DPAPI 加密的 provider key 存储。"""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir) / SECRETS_DIRNAME
        self._path = self._dir / SECRETS_FILENAME

    # ===== 路径 =====

    @property
    def path(self) -> Path:
        """密钥文件路径。"""
        return self._path

    @property
    def supported(self) -> bool:
        """当前平台是否支持 DPAPI。"""
        return is_supported()

    # ===== 读 =====

    def _read_raw(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("secret store read failed: {}", e)
            return {}
        if not isinstance(data, dict):
            return {}
        providers = data.get("providers")
        return providers if isinstance(providers, dict) else {}

    def get(self, provider: str) -> str | None:
        """取某个 provider 的明文 key（解密失败返回 None）。"""
        raw = self._read_raw().get(provider)
        if not isinstance(raw, str) or not raw:
            return None
        try:
            return unprotect_b64(raw).decode("utf-8")
        except (DPAPIUnavailableError, ValueError, OSError) as e:
            logger.warning("secret store decrypt failed for {}: {}", provider, e)
            return None

    def list_providers(self) -> list[str]:
        """列出已存 key 的 provider 名。"""
        return sorted(self._read_raw().keys())

    # ===== 写 =====

    def set(self, provider: str, value: str) -> None:
        """写入（加密后落盘）。value 为空字符串时等价于删除。"""
        if not value:
            self.delete(provider)
            return
        if not self.supported:
            raise DPAPIUnavailableError(
                "当前平台不支持 DPAPI，无法安全存储 API Key。请改用环境变量（.env）或系统 Keyring。"
            )
        providers = self._read_raw()
        providers[provider] = protect_b64(value.encode("utf-8"))
        self._write_raw(providers)

    def delete(self, provider: str) -> bool:
        """删除某个 provider 的 key。返回是否真的删掉了。"""
        providers = self._read_raw()
        if provider not in providers:
            return False
        providers.pop(provider)
        self._write_raw(providers)
        return True

    def _write_raw(self, providers: dict[str, Any]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SECRET_FILE_VERSION,
            "providers": providers,
        }
        # 原子写：先写临时文件再替换，避免中途崩溃留下半截 JSON
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)
        try:
            self._path.chmod(0o600)
        except OSError:  # pragma: no cover - Windows 上 chmod 语义有限
            pass


# ===== 全局单例 =====

_store: SecretStore | None = None


def get_secret_store() -> SecretStore:
    """取全局密钥存储实例（数据目录来自 settings）。"""
    global _store
    if _store is None:
        from ..config import settings

        _store = SecretStore(settings.data_dir)
    return _store


def reset_secret_store() -> None:
    """测试用：清掉单例缓存。"""
    global _store
    _store = None
