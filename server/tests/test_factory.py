"""测试 llm factory：配置加载 + 客户端创建 + routing 解析。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """每个测试清掉 keyring/真实 env，制造干净环境。"""
    for key in (
        "MIMO_API_KEY",
        "MINIMAX_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def user_settings(monkeypatch):
    """伪造"用户在设置页选了 provider/model"。"""

    def _set(provider: str = "", model: str = "") -> None:
        from src.core.llm import factory as factory_mod

        monkeypatch.setattr(
            factory_mod,
            "get_user_llm_prefs",
            lambda: (provider, model),
            raising=True,
        )

    return _set


def _pin_routing(monkeypatch, scene: str, provider: str) -> None:
    """临时把某个场景的 routing 钉到指定 provider（不改 llm.yaml）。"""
    from src.core.llm import factory as factory_mod

    original = factory_mod.load_llm_config

    def patched():
        cfg = dict(original())
        cfg["routing"] = {**cfg.get("routing", {}), scene: provider}
        return cfg

    monkeypatch.setattr(factory_mod, "load_llm_config", patched)


def test_load_llm_config_has_providers():
    """llm.yaml 应至少包含 mimo / minimax / openai / ollama 四个 provider。"""
    from src.core.llm.factory import load_llm_config

    cfg = load_llm_config()
    assert "providers" in cfg
    providers = cfg["providers"]
    assert "mimo" in providers
    assert "minimax" in providers
    assert "openai" in providers
    assert "ollama" in providers


def test_get_default_provider_is_mimo():
    """default_provider 应为 mimo（Phase 3.4+ 改：国内默认）。"""
    from src.core.llm.factory import get_default_provider

    assert get_default_provider() == "mimo"


def test_get_provider_config_mimo():
    """mimo provider config 应包含必要字段（Xiaomi 国内节点）。"""
    from src.core.llm.factory import get_provider_config

    pc = get_provider_config("mimo")
    assert pc["type"] == "openai_compat"
    assert pc["api_key_env"] == "MIMO_API_KEY"
    assert "base_url" in pc
    assert "xiaomimimo.com" in pc["base_url"]
    assert pc["provider_name"] == "mimo"


def test_get_provider_config_minimax():
    """minimax provider config 仍可加载（保留海外节点，需 VPN）。"""
    from src.core.llm.factory import get_provider_config

    pc = get_provider_config("minimax")
    assert pc["type"] == "openai_compat"
    assert pc["api_key_env"] == "MINIMAX_API_KEY"
    assert "MiniMax-M3" in pc["model_specs"]
    spec = pc["model_specs"]["MiniMax-M3"]
    assert spec["context_window"] >= 32000  # 必须支持章节生成
    assert pc["provider_name"] == "minimax"


def test_resolve_provider_for_scene_chapter():
    """routing.chapter_generation 应映射到 mimo（Phase 3.4+ 改）。"""
    from src.core.llm.factory import resolve_provider_for_scene

    assert resolve_provider_for_scene("chapter_generation") == "mimo"


def test_resolve_provider_for_scene_plot():
    """routing.plot_generation 应映射到 mimo。"""
    from src.core.llm.factory import resolve_provider_for_scene

    assert resolve_provider_for_scene("plot_generation") == "mimo"


def test_resolve_provider_for_scene_follows_settings_by_default():
    """routing 写 ``@settings`` 时跟随设置页的选择（2026-10-22 改）。

    这是"设置页选了 minimax 却还在用 mimo"那个 bug 的根因：
    原先把 routing 全部写死成 mimo，设置页形同虚设。
    """
    from src.core.llm.factory import resolve_provider_for_scene

    assert resolve_provider_for_scene("chapter_generation") == "mimo"


def test_resolve_provider_for_scene_uses_user_choice(user_settings):
    """用户在设置页选了 minimax → 创作场景真的走 minimax。"""
    from src.core.llm.factory import resolve_provider_for_scene

    user_settings("minimax", "MiniMax-M3")
    assert resolve_provider_for_scene("chapter_generation") == "minimax"
    assert resolve_provider_for_scene("plot_generation") == "minimax"
    assert resolve_provider_for_scene("summarize") == "minimax"


def test_resolve_provider_for_scene_pinned_provider_wins(user_settings, monkeypatch):
    """routing 写死具体 provider 时，以它为准（不跟设置页）。"""
    from src.core.llm.factory import resolve_provider_for_scene

    user_settings("minimax", "MiniMax-M3")
    _pin_routing(monkeypatch, "summarize", "ollama")
    assert resolve_provider_for_scene("summarize") == "ollama"


def test_resolve_model_for_scene_uses_user_model(user_settings):
    """场景 provider == 用户选的 provider → 用用户选的模型。"""
    from src.core.llm.factory import resolve_model_for_scene

    user_settings("minimax", "MiniMax-M3.1-Flash")
    assert resolve_model_for_scene("chapter_generation") == "MiniMax-M3.1-Flash"


def test_resolve_model_for_scene_falls_back_to_provider_default(user_settings, monkeypatch):
    """场景被钉到别的 provider → 用那个 provider 的 default_model。"""
    from src.core.llm.factory import resolve_model_for_scene

    user_settings("minimax", "MiniMax-M3")
    _pin_routing(monkeypatch, "summarize", "ollama")
    assert resolve_model_for_scene("summarize") == "qwen2.5:14b"


def test_resolve_provider_for_scene_unknown_falls_back():
    """未知 scene 应回落到 default_provider。"""
    from src.core.llm.factory import resolve_provider_for_scene

    assert resolve_provider_for_scene("totally_made_up_scene") == "mimo"


def test_create_llm_client_ollama_works_without_key():
    """Ollama 客户端创建时不应要求 key。"""
    from src.core.llm.factory import create_llm_client

    client = create_llm_client("ollama")
    assert client.provider == "ollama"


def test_create_llm_client_openai_compat_raises_without_key(monkeypatch):
    """mimo 客户端创建时如果 settings 没 key 应抛 AuthError。"""
    from src.core.llm import factory as factory_mod
    from src.core.llm.base import AuthError

    # 强制 _resolve_api_key_for 返回空
    monkeypatch.setattr(factory_mod, "_resolve_api_key_for", lambda _: "")
    with pytest.raises(AuthError):
        factory_mod.create_llm_client("mimo")


def test_create_llm_client_for_scene_uses_routing(monkeypatch):
    """create_llm_client_for_scene 应按 routing 选择 provider。

    ⚠️ 必须把 key 造出来再跑：``OpenAICompatClient`` 在 key 为空时直接抛
    ``AuthError``，而 ``src.core.config.settings`` 是**导入时**读 env 的单例
    —— 也就是说这条测试的成败取决于开发者本机 ``.env`` 里有没有真 key。
    之前就是靠本机配了 key 才"绿"的，换台机器立刻挂。
    """
    from src.core.llm import factory as factory_mod

    monkeypatch.setattr(factory_mod, "_resolve_api_key_for", lambda _: "sk-test-dummy")

    client = factory_mod.create_llm_client_for_scene("summarize")
    # summarize 默认跟随设置页 → 没设置时是 default_provider（mimo）
    assert client.provider == "mimo"


def test_get_provider_config_unknown_raises():
    """未知 provider 名应抛 KeyError。"""
    from src.core.llm.factory import get_provider_config

    with pytest.raises(KeyError):
        get_provider_config("totally_made_up")


def test_load_llm_config_caches():
    """load_llm_config 应被 lru_cache 缓存。"""
    from src.core.llm import factory

    factory.clear_cache()
    cfg1 = factory.load_llm_config()
    cfg2 = factory.load_llm_config()
    assert cfg1 is cfg2  # 同一对象
