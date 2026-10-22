"""Settings 业务服务（Phase 2.4）。

设计：
- 用户运行时设置持久化到 ``<data_dir>/.book-soul-settings.yaml``
- 不依赖 DB（yaml 文件就够）
- 不依赖 FastAPI（单测容易）
- API Key 不入 yaml，单独存系统 Keyring（service=BookSoul, username=provider）
- 启动时若 yaml 不存在 → 写入默认值；存在 → 读
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Protocol

import yaml
from loguru import logger

from ..core.config import settings as app_settings
from ..core.security.secret_store import SecretStore, get_secret_store
from ..schemas.settings import (
    LLM_PROVIDERS,
    UI_THEMES,
    LLMConfig,
    SecurityConfig,
    SettingsRead,
    SettingsUpdate,
    UIConfig,
)

# Keyring 服务名（与 keyring_manager.py 共享）
KEYRING_SERVICE = "BookSoul"
# 每次改 schema 递增
CURRENT_VERSION = 1


class _KeyringLike(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, value: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


def _default_keyring() -> _KeyringLike | None:
    try:
        return importlib.import_module("keyring")  # type: ignore[return-value]
    except ImportError:
        logger.warning("keyring package not installed; API key storage disabled")
        return None


def _settings_path() -> Path:
    """用户 settings.yaml 的绝对路径。"""
    return app_settings.data_dir / ".book-soul-settings.yaml"


class SettingsServiceError(Exception):
    """Service 层基础异常。"""


class SettingsValidationError(SettingsServiceError):
    """字段取值非法。"""


class SettingsService:
    """用户运行时设置 service。"""

    def __init__(
        self,
        keyring_backend: _KeyringLike | None = None,
        settings_path: Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        # 允许注入 backend（测试用 mock）
        self._keyring = keyring_backend if keyring_backend is not None else _default_keyring()
        # 允许注入 settings 文件路径（测试用 tmp_path，不污染真实 data_dir）
        self._settings_path_override = settings_path
        # DPAPI 加密密钥库（打包版默认；明文不落盘）。
        # 注：注入 keyring mock 时（测试态）不启用，避免把 key 写进真实 data_dir。
        if secret_store is not None:
            self._secret_store: SecretStore | None = secret_store
        elif keyring_backend is not None:
            self._secret_store = None
        else:
            self._secret_store = get_secret_store()

    def _settings_path(self) -> Path:
        if self._settings_path_override is not None:
            return self._settings_path_override
        return _settings_path()

    # ===== 文件读写 =====
    def _read_yaml(self) -> dict[str, Any]:
        path = self._settings_path()
        if not path.is_file():
            return {}
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to read {path}: {e}; using defaults")
            return {}
        return data if isinstance(data, dict) else {}

    def _write_yaml(self, data: dict[str, Any]) -> None:
        path = self._settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # version 必带
        data = {**data, "version": CURRENT_VERSION}
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    # ===== 校验 =====
    @staticmethod
    def _validate(data: SettingsUpdate) -> None:
        if data.llm is not None and data.llm.provider not in LLM_PROVIDERS:
            raise SettingsValidationError(
                f"Invalid llm.provider: {data.llm.provider!r}; allowed: {LLM_PROVIDERS}"
            )
        if data.ui is not None and data.ui.theme not in UI_THEMES:
            raise SettingsValidationError(
                f"Invalid ui.theme: {data.ui.theme!r}; allowed: {UI_THEMES}"
            )

    # ===== 业务方法 =====
    def get(self) -> SettingsRead:
        """读当前设置。"""
        raw = self._read_yaml()
        try:
            llm = LLMConfig(**(raw.get("llm") or {}))
            ui = UIConfig(**(raw.get("ui") or {}))
            security = SecurityConfig(**(raw.get("security") or {}))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Invalid settings.yaml, using defaults: {e}")
            llm, ui, security = LLMConfig(), UIConfig(), SecurityConfig()
        return SettingsRead(
            llm=llm,
            ui=ui,
            security=security,
            api_key_configured=self._key_status_all(),
            api_key_source=self._key_source_all(),
        )

    def update(self, data: SettingsUpdate) -> SettingsRead:
        """合并更新 + 写回 yaml。"""
        self._validate(data)
        raw = self._read_yaml()
        if data.llm is not None:
            raw["llm"] = {**data.llm.model_dump()}
        if data.ui is not None:
            raw["ui"] = {**data.ui.model_dump()}
        if data.security is not None:
            raw["security"] = {**data.security.model_dump()}
        self._write_yaml(raw)
        return self.get()

    # ===== API Key（DPAPI 密钥库 / keyring）=====
    def _key_status_all(self) -> dict[str, bool]:
        """检查每个 provider 是否已存 key。"""
        return {p: self.has_api_key(p) for p in LLM_PROVIDERS}

    def _key_source_all(self) -> dict[str, str]:
        """每个 provider 的 key 来源（env / secret_store / keyring / none）。

        用途：用户可能用环境变量提供 key（最常见），设置页要能显示出来，
        否则用户会以为"没配"而重复去填。
        """
        from ..core.llm.factory import resolve_api_key_source

        return {p: resolve_api_key_source(p) for p in LLM_PROVIDERS}

    def has_api_key(self, provider: str) -> bool:
        """应用内是否存了 key（DPAPI 密钥库 或 系统 keyring）。

        注意：这里**不查环境变量** —— 环境变量是"外部注入"，
        由 :meth:`_key_source_all` 单独汇报来源。
        """
        if provider not in LLM_PROVIDERS:
            return False
        if self._secret_store is not None and self._secret_store.supported:
            try:
                if self._secret_store.get(provider):
                    return True
            except Exception as e:  # noqa: BLE001
                logger.warning(f"secret store get failed for {provider}: {e}")
        if self._keyring is None:
            return False
        try:
            return self._keyring.get_password(KEYRING_SERVICE, provider) is not None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"keyring get_password failed for {provider}: {e}")
            return False

    def set_api_key(self, provider: str, key: str) -> None:
        if provider not in LLM_PROVIDERS:
            raise SettingsValidationError(
                f"Invalid provider: {provider!r}; allowed: {LLM_PROVIDERS}"
            )
        # 优先 DPAPI 加密文件（打包版默认；明文不落盘）
        if self._secret_store is not None and self._secret_store.supported:
            try:
                self._secret_store.set(provider, key)
                return
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"secret store write failed for {provider}: {e}; fallback to keyring"
                )
        if self._keyring is None:
            raise SettingsServiceError(
                "No secure key storage available (DPAPI unsupported and system keyring unavailable)"
            )
        self._keyring.set_password(KEYRING_SERVICE, provider, key)

    def delete_api_key(self, provider: str) -> None:
        if provider not in LLM_PROVIDERS:
            raise SettingsValidationError(
                f"Invalid provider: {provider!r}; allowed: {LLM_PROVIDERS}"
            )
        if self._secret_store is not None:
            try:
                self._secret_store.delete(provider)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"secret store delete failed for {provider}: {e}")
        if self._keyring is None:
            return  # 幂等
        try:
            self._keyring.delete_password(KEYRING_SERVICE, provider)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"keyring delete_password failed for {provider}: {e}")
