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


def test_resolve_provider_for_scene_quality_check():
    """routing.quality_check 应映射到 ollama（本地，不依赖网络）。"""
    from src.core.llm.factory import resolve_provider_for_scene

    assert resolve_provider_for_scene("quality_check") == "ollama"


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


def test_create_llm_client_for_scene_uses_routing():
    """create_llm_client_for_scene 应按 routing 选择 provider。"""
    from src.core.llm.factory import create_llm_client_for_scene

    client = create_llm_client_for_scene("quality_check")
    # quality_check 路由到 ollama
    assert client.provider == "ollama"


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
