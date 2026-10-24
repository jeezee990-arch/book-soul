"""LLM 客户端工厂。

职责：
- 加载并缓存 ``config/llm.yaml``
- 根据 provider 名称创建对应客户端
- 解析 ``default_provider`` / ``routing.<场景>`` / 用户设置页的选择

场景路由的语义（2026-10-22）
----------------------------
``routing.<场景>`` 的值有三种含义：

- ``"@settings"``（或没写这一项）→ **跟随用户在设置页的选择**。
  用户在设置页选了 minimax，创作/质检/总结就全部走 minimax。
- 具体 provider 名 → 该场景强制用那个 provider
  （例：本机跑了 Ollama，把 ``quality_check`` 写成 ``ollama`` 走本地）。
- 留空 → 等同 ``"@settings"``。

模型名同理：场景用的 provider == 用户选的 provider 时用用户选的模型，
否则用该 provider 在 ``llm.yaml`` 里的 ``default_model``。
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from ..paths import config_dir
from ..user_settings import get_user_llm_prefs
from .base import BaseLLMClient
from .ollama import OllamaClient
from .openai_compat import OpenAICompatClient

_LLM_CONFIG_PATH = config_dir() / "llm.yaml"

# routing.<场景> 写成这个值 = 跟随设置页的用户选择
FOLLOW_SETTINGS = "@settings"

# 找不到 default_provider 时的兜底（国内节点，免 VPN）
_FALLBACK_PROVIDER = "mimo"


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
    return cfg.get("default_provider") or _FALLBACK_PROVIDER


def get_configured_models(provider: str) -> list[str]:
    """``llm.yaml`` 里登记的已知可用模型（设置页下拉框的兜底来源）。"""
    try:
        pc = get_provider_config(provider)
    except KeyError:
        return []
    return [str(m) for m in (pc.get("models") or [])]


def provider_default_model(provider: str) -> str:
    """某个 provider 在 ``llm.yaml`` 里的默认模型名。"""
    try:
        pc = get_provider_config(provider)
    except KeyError:
        return ""
    return str(pc.get("default_model") or "")


def resolve_provider_for_scene(scene: str, fallback: str | None = None) -> str:
    """根据 ``routing.<scene>`` 决定用哪个 provider。

    - ``routing.<scene>`` 是 ``"@settings"`` 或没配 → 跟随设置页的用户选择；
      用户还没选过时用 ``default_provider``，再回落到 ``fallback``。
    - ``routing.<scene>`` 是具体 provider 名 → 强制用它（不跟设置页）。
    """
    cfg = load_llm_config()
    routing = cfg.get("routing") or {}
    target = routing.get(scene)
    if target is None or str(target) in ("", FOLLOW_SETTINGS):
        user_provider, _ = get_user_llm_prefs()
        if user_provider:
            return user_provider
        return get_default_provider() or fallback or _FALLBACK_PROVIDER
    return str(target)


def resolve_model_for_scene(scene: str) -> str:
    """该场景实际使用的模型名。

    - 场景的 provider 就是用户选的那个 → 用用户选的模型
    - 否则（场景被 routing 钉到别的 provider）→ 用那个 provider 的 ``default_model``
    """
    provider = resolve_provider_for_scene(scene)
    user_provider, user_model = get_user_llm_prefs()
    if user_model and user_provider and provider == user_provider:
        return user_model
    return provider_default_model(provider)


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


def create_llm_client(provider: str | None = None, model: str | None = None) -> BaseLLMClient:
    """根据 provider 名称创建客户端。

    业务代码调用：``from src.core.llm import create_llm_client``

    :param provider: provider 名；None 用 ``default_provider``
    :param model: 覆盖该 provider 的默认模型（设置页选的就是它）；
        None 用 ``llm.yaml`` 里的 ``default_model``
    """
    name = provider or get_default_provider()
    pc = get_provider_config(name)
    if model:
        # 覆盖默认模型（不改动 llm.yaml 缓存对象）
        pc = {**pc, "default_model": model}
    ptype = pc.get("type")
    api_key = _resolve_api_key_for(name)

    if ptype == "openai_compat":
        return OpenAICompatClient(pc, api_key=api_key)
    if ptype == "ollama":
        return OllamaClient(pc, api_key=api_key)
    raise ValueError(f"Unknown provider type: {ptype!r} for provider {name!r}")


def create_llm_client_for_scene(scene: str) -> BaseLLMClient:
    """根据业务场景（如 ``chapter_generation``）选 provider + 模型并创建。"""
    provider = resolve_provider_for_scene(scene)
    model = resolve_model_for_scene(scene)
    return create_llm_client(provider, model or None)


# =========================================================================
# 性能优化：进程级 LLM 客户端单例（Phase 性能优化）
# =========================================================================
# 为什么：之前每个请求都创建/关闭 httpx.AsyncClient，连接池浪费且 GIL overhead 高
# 现在：lru_cache 按 provider+模型 缓存，同一个组合只建一次，后续复用
# 注意：调用方不要再 aclose()，进程退出时 httpx 会清理
# =========================================================================


@lru_cache(maxsize=32)
def _llm_client_cache(cache_key: str) -> BaseLLMClient:
    """进程级缓存：同一 ``provider::model`` 组合共享一个 LLM client。

    key 里带 provider + 模型，是为了让"用户在设置页换了模型/换了 provider"
    自动拿到新的 client，而不用手动清缓存。
    """
    provider, _, model = cache_key.partition("::")
    client = create_llm_client(provider, model or None)
    logger.debug(
        "LLM client cached for provider={} model={}",
        provider,
        getattr(client, "model", "?"),
    )
    return client


def get_cached_llm_client(scene: str) -> BaseLLMClient:
    """取缓存的 LLM 客户端（按 scene 复用）。

    使用方式（流式 service 推荐）：
        llm = get_cached_llm_client("plot_generation")
        # 不要调用 aclose()
    """
    provider = resolve_provider_for_scene(scene)
    model = resolve_model_for_scene(scene)
    return _llm_client_cache(f"{provider}::{model}")


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
    # 探活用短超时：这是"能不能连上"，不是"能不能生成"
    probe_timeout = min(5.0, timeout)
    # ⚠️ connect 超时**不能大于**总超时。
    # 之前 connect=min(10, timeout) > probe_timeout=5，导致"网络不通"的 provider
    # （比如没配的 openai、没启动的 ollama）在**连接阶段**就能拖满 10 秒 ——
    # /llm/health 一次调用就把顶栏模型灯卡住近 10 秒（实测 9.8s）。
    connect_timeout = min(3.0, probe_timeout)

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
    """探活配置里所有 provider（并发探测，别串行等）。"""
    cfg = load_llm_config()
    providers = list((cfg.get("providers") or {}).keys())
    if not providers:
        return {}
    results = await asyncio.gather(
        *(check_provider_health(name) for name in providers),
        return_exceptions=True,
    )
    out: dict[str, tuple[bool, str]] = {}
    for name, res in zip(providers, results, strict=True):
        if isinstance(res, BaseException):
            out[name] = (False, f"探测失败：{res}")
        else:
            out[name] = res
    return out


# =========================================================================
# 实时模型清单（设置页下拉框）
# =========================================================================


async def fetch_provider_models(provider: str) -> tuple[list[str], bool, str]:
    """实时拉取 provider 支持的模型列表。

    :return: ``(模型名列表, 服务是否可达, 状态说明)``

    为什么要实时拉
    --------------
    服务端会下线模型 —— mimo 的 ``mimo-v2.5-pro`` 就是这么消失的，
    结果配置里写死的模型名直接 400 "Unsupported model"。

    写死在 ``llm.yaml`` 里的名字迟早过期；实时拉 + 设置页下拉框，
    才能保证用户永远选得到服务端还支持的模型。
    """
    import httpx

    try:
        pc = get_provider_config(provider)
    except KeyError as e:
        return [], False, f"未知 provider：{e}"

    base_url = str(pc.get("base_url", "")).rstrip("/")
    if not base_url:
        return [], False, f"provider '{provider}' 未配置 base_url"

    timeout = float(pc.get("timeout_seconds", 30))
    headers: dict[str, str] = {}
    api_key = _resolve_api_key_for(provider)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(min(10.0, timeout), connect=min(5.0, timeout)),
            headers=headers,
        ) as client:
            resp = await client.get("/models")
    except httpx.HTTPError as e:
        return [], False, f"无法连接 {base_url}：{e}"

    if resp.status_code >= 400:
        if resp.status_code in (401, 403):
            return [], True, f"服务可达，但 API Key 无效（HTTP {resp.status_code}）"
        return [], True, f"服务返回 HTTP {resp.status_code}"

    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return [], True, "服务可达，但返回的不是 JSON"

    models = sorted(
        {
            str(item.get("id"))
            for item in (data.get("data") or [])
            if isinstance(item, dict) and item.get("id")
        }
    )
    if not models:
        return [], True, "服务可达，但没有返回任何模型"
    return models, True, f"服务可达，{len(models)} 个模型"


async def describe_provider_models(provider: str) -> dict[str, Any]:
    """设置页用：某个 provider 的模型清单（实时 ∪ 配置登记）。"""
    configured = get_configured_models(provider)
    live, reachable, message = await fetch_provider_models(provider)
    merged = list(dict.fromkeys([*live, *configured]))
    return {
        "provider": provider,
        "models": merged,
        "live_models": live,
        "configured_models": configured,
        "default_model": provider_default_model(provider),
        "reachable": reachable,
        "message": message,
    }
