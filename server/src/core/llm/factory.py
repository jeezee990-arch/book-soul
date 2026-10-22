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

from ..paths import config_dir
from .base import BaseLLMClient
from .ollama import OllamaClient
from .openai_compat import OpenAICompatClient

_LLM_CONFIG_PATH = config_dir() / "llm.yaml"


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
    "mimo": "mimo_api_key",
    "minimax": "minimax_api_key",
    "openai": "openai_api_key",
}


def resolve_api_key_source(provider: str) -> str:
    """报告某个 provider 的 API key 来自哪里。

    :return: ``"env"`` / ``"secret_store"`` / ``"keyring"`` / ``"none"``

    用途：设置页要能告诉用户"你的 key 是从环境变量来的"，
    否则用环境变量的用户会以为没配而重复填写。
    """
    if provider in ("ollama",):
        return "none"
    field_name = _API_KEY_FROM_SETTINGS.get(provider)
    if not field_name:
        return "none"
    from src.core.config import settings

    if getattr(settings, field_name, "") or "":
        return "env"
    try:
        from ..security.secret_store import get_secret_store

        if get_secret_store().get(provider):
            return "secret_store"
    except Exception:  # noqa: BLE001
        pass
    try:
        import keyring

        if keyring.get_password("BookSoul", provider):
            return "keyring"
    except Exception:  # noqa: BLE001
        pass
    return "none"


def _resolve_api_key_for(provider: str) -> str | None:
    """根据 provider 查 API key。

    查找顺序（高 → 低）：
    1. pydantic-settings 字段（env 变量；如 ``MIMO_API_KEY``）—— **优先级最高**
    2. DPAPI 加密文件（``<data_dir>/secrets/keys.json``）—— 打包版默认
    3. 系统 keyring（用户在 Settings UI 存的 key，service=BookSoul, username=provider）
    4. 直接从 ``os.environ``（兜底）

    Ollama 不需要 key（返回 None）。
    """
    if provider in ("ollama",):
        return None
    field_name = _API_KEY_FROM_SETTINGS.get(provider)
    if field_name:
        # 1) pydantic-settings（env 变量）—— 用户已有习惯，优先级最高
        from src.core.config import settings

        val = getattr(settings, field_name, "") or ""
        if val:
            return val
        # 2) DPAPI 加密文件（打包版默认；明文不落盘）
        try:
            from ..security.secret_store import get_secret_store

            val = get_secret_store().get(provider) or ""
            if val:
                logger.debug("API key for provider={} resolved from secret store", provider)
                return val
        except Exception as e:  # noqa: BLE001
            logger.debug("secret store lookup failed for {}: {}", provider, e)
        # 3) 系统 keyring（用户在 Settings UI 存的）
        try:
            import keyring

            val = keyring.get_password("BookSoul", provider) or ""
            if val:
                logger.debug("API key for provider={} resolved from keyring", provider)
                return val
        except Exception as e:  # noqa: BLE001
            logger.debug("keyring lookup failed for {}: {}", provider, e)
    # 4) 直接从 os.environ 读（兜底）
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


# =========================================================================
# 性能优化：进程级 LLM 客户端单例（Phase 性能优化）
# =========================================================================
# 为什么：之前每个请求都创建/关闭 httpx.AsyncClient，连接池浪费且 GIL overhead 高
# 现在：lru_cache 按 scene 缓存，每个场景首次调用时创建，后续复用
# 注意：调用方不要再 aclose()，进程退出时 httpx 会清理
# =========================================================================


@lru_cache(maxsize=32)
def _llm_client_cache(scene: str) -> BaseLLMClient:
    """进程级缓存：每个 scene 共享一个 LLM client（httpx 连接池复用）。"""
    client = create_llm_client_for_scene(scene)
    logger.debug(
        "LLM client cached for scene={} (provider={})", scene, getattr(client, "provider", "?")
    )
    return client


def get_cached_llm_client(scene: str) -> BaseLLMClient:
    """取缓存的 LLM 客户端（按 scene 复用）。

    使用方式（流式 service 推荐）：
        llm = get_cached_llm_client("plot_generation")
        # 不要调用 aclose()
    """
    return _llm_client_cache(scene)


def clear_llm_client_cache() -> None:
    """测试 / 热重载用：清缓存。调用方负责关闭 httpx 连接。"""
    _llm_client_cache.cache_clear()
    logger.debug("LLM client cache cleared")


# =========================================================================
# Provider 健康检查（启动预检 / 设置页状态）
# =========================================================================


async def check_provider_health(provider: str) -> tuple[bool, str]:
    """探活某个 provider。

    :return: ``(是否可用, 说明文字)``

    为什么要这个：本地 Ollama 经常"没装"或"没启动"，
    而配置里 7 个质检场景默认路由到 ollama。启动时预检 + 明确提示，
    比让用户等 30 秒超时后才看到 "ConnectError" 友好得多。
    """
    import httpx

    try:
        pc = get_provider_config(provider)
    except KeyError as e:
        return False, f"未知 provider：{e}"

    base_url = str(pc.get("base_url", "")).rstrip("/")
    if not base_url:
        return False, f"provider '{provider}' 未配置 base_url"

    timeout = float(pc.get("timeout_seconds", 30))
    connect_timeout = min(10.0, timeout)
    # 探活用短超时：这是"能不能连上"，不是"能不能生成"
    probe_timeout = min(5.0, timeout)

    # 带 key 探测：/models 端点需要鉴权，不带 key 会一律 401，
    # 那样就无法区分"服务挂了"和"key 错了"
    headers: dict[str, str] = {}
    api_key = _resolve_api_key_for(provider)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(probe_timeout, connect=connect_timeout),
            headers=headers,
        ) as client:
            resp = await client.get("/models")
    except httpx.ConnectError as e:
        hint = ""
        if provider == "ollama":
            hint = "（请先运行 `ollama serve`，并确认已 `ollama pull qwen2.5:14b`）"
        return False, f"无法连接到 {base_url}{hint} — {e}"
    except httpx.HTTPError as e:
        return False, f"探测 {base_url} 失败：{e}"

    if resp.status_code >= 400:
        # 401/403 说明连上了但 key 不对 —— 服务本身是活的
        if resp.status_code in (401, 403):
            return True, f"服务可达，但 API Key 无效（HTTP {resp.status_code}）"
        return False, f"服务返回 HTTP {resp.status_code}"

    return True, "服务可达"


async def check_all_providers_health() -> dict[str, tuple[bool, str]]:
    """探活配置里所有 provider。"""
    cfg = load_llm_config()
    providers = cfg.get("providers") or {}
    result: dict[str, tuple[bool, str]] = {}
    for name in providers:
        result[name] = await check_provider_health(name)
    return result
