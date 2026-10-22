"""测试 SettingsService（Phase 2.4）。

覆盖：
- get（无文件时返默认）
- update（部分合并 + 写盘）
- 校验（非法 provider / theme）
- API key（set / delete / has，注入 mock keyring）
"""

from __future__ import annotations

import pytest
import yaml

from src.schemas.settings import LLMConfig, SettingsUpdate, UIConfig
from src.services.settings_service import (
    SettingsService,
    SettingsValidationError,
)


class FakeKeyring:
    """用于测试的内存 keyring mock。"""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, value: str) -> None:
        self.store[(service, username)] = value

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


@pytest.fixture
def fake_keyring() -> FakeKeyring:
    return FakeKeyring()


@pytest.fixture
def settings_file(tmp_path):
    """测试用 settings.yaml 路径（不污染真实 data_dir）。"""
    return tmp_path / ".book-soul-settings.yaml"


@pytest.fixture
def svc(fake_keyring: FakeKeyring, settings_file) -> SettingsService:
    return SettingsService(keyring_backend=fake_keyring, settings_path=settings_file)


def test_get_default_no_yaml(svc: SettingsService) -> None:
    """无 yaml 时返默认（provider / model 来自 config/llm.yaml，不硬编码）。"""
    from src.core.llm.factory import get_default_provider, provider_default_model

    s = svc.get()
    assert s.llm.provider == get_default_provider()
    assert s.llm.model == provider_default_model(get_default_provider())
    assert s.ui.theme == "dark"
    assert s.security.encryption_enabled is False
    # 没有 key 时全部 False
    assert s.api_key_configured == {
        "mimo": False,
        "minimax": False,
        "openai": False,
        "ollama": False,
    }


def test_get_default_model_is_not_stale(svc: SettingsService) -> None:
    """默认模型必须是服务端还支持的（mimo-v2.5-pro 已下线，别再写死）。"""
    from src.core.llm.factory import get_configured_models

    s = svc.get()
    assert s.llm.model != "mimo-v2.5-pro"
    assert s.llm.model in get_configured_models(s.llm.provider)


def test_update_empty_model_fills_provider_default(svc: SettingsService) -> None:
    """只改 provider、不填 model → 用该 provider 的默认模型补齐。"""
    from src.core.llm.factory import provider_default_model

    s = svc.update(SettingsUpdate(llm=LLMConfig(provider="minimax", model="")))
    assert s.llm.provider == "minimax"
    assert s.llm.model == provider_default_model("minimax")


def test_get_reads_yaml(svc: SettingsService, settings_file) -> None:
    """已有 yaml 时读它。"""
    settings_file.write_text(
        "version: 1\nllm:\n  provider: openai\n  model: gpt-4\nui:\n  theme: light\n",
        encoding="utf-8",
    )
    s = svc.get()
    assert s.llm.provider == "openai"
    assert s.llm.model == "gpt-4"
    assert s.ui.theme == "light"


def test_update_partial(svc: SettingsService, settings_file) -> None:
    """只更新部分字段时合并保留其他。"""
    # 先写默认
    svc.update(SettingsUpdate(llm=LLMConfig(provider="openai", model="gpt-4o")))
    # 再只改 ui
    s2 = svc.update(SettingsUpdate(ui=UIConfig(theme="light")))

    assert s2.llm.provider == "openai"  # 保留
    assert s2.ui.theme == "light"  # 新
    # 文件持久化
    on_disk = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
    assert on_disk["llm"]["provider"] == "openai"
    assert on_disk["ui"]["theme"] == "light"
    assert on_disk["version"] == 1


def test_update_invalid_provider(svc: SettingsService) -> None:
    """非法 provider 抛 SettingsValidationError。"""
    with pytest.raises(SettingsValidationError):
        svc.update(SettingsUpdate(llm=LLMConfig(provider="bogus")))


def test_update_invalid_theme(svc: SettingsService) -> None:
    with pytest.raises(SettingsValidationError):
        svc.update(SettingsUpdate.model_validate({"ui": {"theme": "neon"}}))


def test_set_api_key(svc: SettingsService, fake_keyring: FakeKeyring) -> None:
    svc.set_api_key("openai", "sk-test-1234")
    assert fake_keyring.get_password("BookSoul", "openai") == "sk-test-1234"
    assert svc.has_api_key("openai") is True
    assert svc.has_api_key("minimax") is False


def test_set_api_key_invalid_provider(svc: SettingsService) -> None:
    with pytest.raises(SettingsValidationError):
        svc.set_api_key("bogus", "x")


def test_delete_api_key(svc: SettingsService, fake_keyring: FakeKeyring) -> None:
    svc.set_api_key("ollama", "key-1")
    assert svc.has_api_key("ollama") is True
    svc.delete_api_key("ollama")
    assert svc.has_api_key("ollama") is False


def test_delete_api_key_idempotent(svc: SettingsService) -> None:
    """不存在的 key 删了不抛。"""
    svc.delete_api_key("openai")  # 没设过，不应抛
    svc.delete_api_key("openai")  # 再删一次


def test_api_key_status_in_get(svc: SettingsService) -> None:
    """get 返回的 api_key_configured 反映 keyring 状态。"""
    svc.set_api_key("minimax", "k1")
    s = svc.get()
    assert s.api_key_configured == {
        "mimo": False,
        "minimax": True,
        "openai": False,
        "ollama": False,
    }
