"""LLM 客户端工厂。

职责：
- 加载并缓存 ``config/llm.yaml``
- 根据 provider 名称创建对应客户端
- 提供 default_provider / routing.<场景> 的解析
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .base import BaseLLMClient
from .ollama import OllamaClient
from .openai_compat import OpenAICompatClient

def _find_repo_root() -> Path:
    """向上找项目根：包含 ``config/`` 目录且 ``pyproject.toml`` 标志 workspace。"""
    p = Path(__file__).resolve().parent
    for _ in range(8):
        if (p / "config").is_dir() and (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    # fallback：硬编码（server/src/core/llm/factory.py → 根）
    return Path(__file__).resolve().parents[4]


_LLM_CONFIG_PATH = _find_repo_root() / "config" / "llm.yaml"


def find_llm_config() -> Path | None:
    """定位 ``config/llm.yaml``。"""
    return _LLM_CONFIG_PATH if _LLM_CONFIG_PATH.is_file() else None


@lru_cache(maxsize=1)
def load_llm_config() -> dict[str, Any]:
    """加载 ``config/llm.yaml``，缓存到内存。"""
    path = find_llm_config()
    if path is None:
        logger.warning("llm.yaml not found at {}, using empty config", _LLM_CONFIG_PATH)
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        logger.warning("llm.yaml root is not a dict, got {}", type(data).__name__)
        return {}
    return data


def clear_cache() -> None:
    """测试 / 热重载用：清掉 lru_cache。"""
    load_llm_config.cache_clear()


def get_provider_config(provider: str) -> dict[str, Any]:
    """取某个 provider 的配置。"""
    cfg = load_llm_config()
    providers = cfg.get("providers") or {}
    if provider not in providers:
        raise KeyError(f"Unknown provider: {provider!r}. Available: {list(providers)}")
    pc = providers[provider]
    # 注入 provider_name 便于子客户端用
    return {**pc, "provider_name": provider}


def get_default_provider() -> str:
    """读 ``default_provider``。"""
    cfg = load_llm_config()
    return cfg.get("default_provider") or "minimax"


def resolve_provider_for_scene(scene: str, fallback: str | None = None) -> str:
    """根据 ``routing.<scene>`` 决定用哪个 provider。

    没有匹配时回退到 ``default_provider``，再回落到 ``fallback``。
    """
    cfg = load_llm_config()
    routing = cfg.get("routing") or {}
    return routing.get(scene) or get_default_provider() or fallback or "minimax"


# 哪些 provider 需要从 settings 拿 key（其余的走 os.environ / 自处理）
_API_KEY_FROM_SETTINGS = {
    "minimax": "minimax_api_key",
    "openai": "openai_api_key",
}


def _resolve_api_key_for(provider: str) -> str | None:
    """根据 provider 从 settings / os.environ 取 key。

    优先用 Settings（pydantic-settings 已从 .env 读），再回落到 os.environ。
    Ollama 不需要 key（返回 None）。
    """
    if provider in ("ollama",):
        return None
    field_name = _API_KEY_FROM_SETTINGS.get(provider)
    if field_name:
        # 延迟 import 避免循环依赖
        from src.core.config import settings

        val = getattr(settings, field_name, "") or ""
        if val:
            return val
    # fallback：直接从 .env 读
    import os

    env_var_map = {
        "minimax": "MINIMAX_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    env_var = env_var_map.get(provider)
    if env_var:
        return os.environ.get(env_var, "") or None
    return None


def create_llm_client(provider: str | None = None) -> BaseLLMClient:
    """根据 provider 名称创建客户端。

    业务代码调用：``from src.core.llm import create_llm_client``
    """
    name = provider or get_default_provider()
    pc = get_provider_config(name)
    ptype = pc.get("type")
    api_key = _resolve_api_key_for(name)

    if ptype == "openai_compat":
        return OpenAICompatClient(pc, api_key=api_key)
    if ptype == "ollama":
        return OllamaClient(pc, api_key=api_key)
    raise ValueError(f"Unknown provider type: {ptype!r} for provider {name!r}")


def create_llm_client_for_scene(scene: str) -> BaseLLMClient:
    """根据业务场景（如 ``chapter_generation``）选 provider 并创建。"""
    provider = resolve_provider_for_scene(scene)
    return create_llm_client(provider)
