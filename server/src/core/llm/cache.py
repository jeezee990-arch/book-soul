"""LLM 远程查询缓存：健康状态 + 模型清单。

为什么需要这个模块
------------------
``GET /llm/health`` 和 ``GET /llm/models`` 都要**实时打外部网络**：

- 顶栏的模型状态灯在应用启动时就会调 ``/llm/health``
- 设置页打开时也会调

而一次"探活所有 provider"里，"配置里有、网络不通"的那些（比如没配的 openai、
没启动的 ollama）会**把整批探测拖到连接超时**。实测用户要干等 ~3 秒才看到那颗灯。

这里用四层手段解决：

1. **连接超时不超过总超时**（见 ``factory.check_provider_health``）
2. **按 provider 粒度的探测任务共享** —— 同一个 provider 的探测只跑一次，
   启动预检、顶栏灯、设置页共用它（不会各打一轮）
3. **TTL 缓存**：命中直接返回，0 延迟
4. **stale-while-revalidate**：缓存过期时先把旧值给出去，再后台刷新 ——
   前端永远不用等网络

为什么缓存是**按 provider** 而不是一整批
----------------------------------------
顶栏灯只关心**当前生效的那一个** provider。如果 ``/llm/health`` 总是探测全部，
那么"用户用 mimo，但 openai/ollama 不可达"就会让灯白等 3 秒 ——
而那 3 秒对灯没有任何意义。所以：

- ``GET /llm/health?provider=mimo`` → **只探活 mimo**（约 0.2 秒）
- ``GET /llm/health``（不带参数）→ 探活全部（启动预检用，后台跑，不阻塞任何人）
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

# 健康状态缓存有效期（秒）。超过后仍先返回旧值，后台刷新。
HEALTH_TTL_SECS = 60.0

# 模型清单缓存有效期（秒）。模型清单变化比健康状态慢，可以缓存久一点。
MODELS_TTL_SECS = 300.0

# ===== 健康状态 =====
# provider → (是否可用, 说明)
_health: dict[str, tuple[bool, str]] = {}
# provider → 上次探测到的时刻（单调时钟）
_health_at: dict[str, float] = {}
# provider → 进行中的探测任务（**按 provider 共享**）
_probe_tasks: dict[str, asyncio.Task] = {}

# ===== 模型清单 =====
_models: dict[str, tuple[float, Any]] = {}


def _now() -> float:
    """单调时钟（不受系统时间调整影响）。"""
    return time.monotonic()


def _known_providers() -> list[str]:
    """配置里登记的所有 provider 名。"""
    try:
        from .factory import load_llm_config

        cfg = load_llm_config()
        return list((cfg.get("providers") or {}).keys())
    except Exception as e:  # noqa: BLE001
        logger.warning("读取 provider 列表失败：{}", e)
        return []


# =========================================================================
# 健康状态
# =========================================================================


def invalidate_health() -> None:
    """清空健康状态缓存（改了 key / provider 之后要调）。"""
    _health.clear()
    _health_at.clear()


def set_health(results: dict[str, tuple[bool, str]]) -> None:
    """写入探测结果（启动预检完成后调用，避免重复探测）。"""
    now = _now()
    for name, value in results.items():
        _health[name] = value
        _health_at[name] = now


def get_cached_health() -> dict[str, tuple[bool, str]]:
    """取当前缓存（不触发探测）。"""
    return dict(_health)


async def _probe_one(provider: str) -> tuple[bool, str]:
    """探测单个 provider 并写入缓存。"""
    from .factory import check_provider_health

    ok, message = await check_provider_health(provider)
    _health[provider] = (ok, message)
    _health_at[provider] = _now()
    return (ok, message)


def _spawn_probe(provider: str) -> asyncio.Task:
    """为某个 provider 启动（或复用）探测任务。

    复用是关键：启动预检、顶栏灯、设置页可能同时要探同一个 provider ——
    不复用的话同一个 provider 被探测多次（每轮都是真实的外部请求）。
    """
    task = _probe_tasks.get(provider)
    if task is None or task.done():
        task = asyncio.create_task(_probe_one(provider))
        _probe_tasks[provider] = task
    return task


async def get_health(
    providers: list[str] | None = None,
    max_age: float = HEALTH_TTL_SECS,
) -> dict[str, tuple[bool, str]]:
    """取 provider 的健康状态。

    :param providers: 要查哪些 provider。None = 配置里全部（启动预检用）。
        指定单个时**只探这一个** —— 顶栏灯只要知道自己用的那个 provider。
    :param max_age: 缓存有效期（秒）。

    语义：

    - 全部命中（未过期）→ 立刻返回
    - 有旧值但已过期     → 先返回旧值，后台刷新（stale-while-revalidate）
    - 完全没有值         → 等这一轮探测（与其它调用方共享任务，不重复打网络）
    """
    targets = list(providers) if providers is not None else _known_providers()
    now = _now()

    fresh: dict[str, tuple[bool, str]] = {}
    stale: dict[str, tuple[bool, str]] = {}
    pending: list[str] = []
    for name in targets:
        at = _health_at.get(name)
        if name not in _health:
            pending.append(name)
        elif at is not None and (now - at) < max_age:
            fresh[name] = _health[name]
        else:
            stale[name] = _health[name]

    # 全部新鲜 → 直接返回
    if not stale and not pending:
        return fresh

    # 有旧值但已过期 → 先给旧值，后台刷新（不阻塞前端）
    if stale:
        for name in stale:
            try:
                _spawn_probe(name)
            except RuntimeError:  # pragma: no cover - 没有运行中的事件循环
                pass
        fresh.update(stale)
        if not pending:
            return fresh

    # 从来没探过 → 必须等一次（共享任务，不会重复打网络）
    tasks = [_spawn_probe(name) for name in pending]
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("探测 provider '{}' 失败：{}", pending[0], e)

    for name in pending:
        if name in _health:
            fresh[name] = _health[name]
    return fresh


# =========================================================================
# 模型清单
# =========================================================================


def invalidate_models(provider: str | None = None) -> None:
    """清空模型清单缓存（指定 provider 则只清它）。"""
    if provider is None:
        _models.clear()
    else:
        _models.pop(provider, None)


async def get_models(provider: str, force: bool = False) -> Any:
    """取某 provider 的模型清单（带缓存）。

    :param force: True = 忽略缓存强制重新拉（设置页「刷新列表」按钮用）
    """
    from .factory import describe_provider_models

    now = _now()
    hit = _models.get(provider)
    if not force and hit is not None:
        cached_at, payload = hit
        if (now - cached_at) < MODELS_TTL_SECS:
            return payload

    payload = await describe_provider_models(provider)
    _models[provider] = (now, payload)
    return payload


def reset_all() -> None:
    """清空全部缓存（测试用）。"""
    invalidate_health()
    invalidate_models()
    _probe_tasks.clear()
