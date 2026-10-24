"""LLM 缓存模块（``src/core/llm/cache.py``）的单元测试。

锁住四件事 —— 每一件都对应一个真实的用户可感知问题：

1. **命中缓存不重复打网络**
   顶栏模型灯在应用启动时就会调 ``/llm/health``，而健康检查要实时探测 provider。
   之前每次调用都要等最慢的那个（实测 ~3 秒），顶栏卡成"转圈"。

2. **缓存过期时先返回旧值，再后台刷新**（stale-while-revalidate）
   用户永远不用等网络 —— 拿到的可能是几十秒前的状态，但立刻就有。

3. **并发调用共享同一个探测任务**
   启动预检和用户点开设置页会同时触发探测；不共享的话同一个 provider
   被探测两次（两轮外部网络请求）。

4. **定点探活只探那一个 provider**
   顶栏灯只关心"当前生效的 provider"。如果每次都探全部，
   "用户用 mimo，但没配的 openai / 没启动的 ollama 不可达"会让灯白等 3 秒。
"""

import asyncio

import pytest

from src.core.llm import cache as llm_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个用例前后都清干净缓存（模块级单例，跨用例会串）。

    ⚠️ 要清**两个**对象：模块级 import 拿到的那个（可能是 ``conftest.temp_db``
    卸载 ``src.*`` 之前的旧对象），以及**当前** ``sys.modules`` 里的那个
    （用例内部 ``from src.core.llm import cache`` 拿到的是它）。
    只清一个的话，全量跑时另一个会带着上个用例的缓存 → 断言飘。
    """
    from src.core.llm import cache as current

    llm_cache.reset_all()
    current.reset_all()
    yield
    llm_cache.reset_all()
    current.reset_all()


def _patch_probe(monkeypatch, results: dict[str, tuple[bool, str]], calls: list):
    """把 factory 里的探测函数换成假的，并记录调用了哪个 provider。"""

    async def fake_probe_one(provider: str):
        calls.append(provider)
        return results.get(provider, (True, "服务可达"))

    async def fake_probe_all():
        calls.append("all")
        return dict(results)

    monkeypatch.setattr("src.core.llm.factory.check_provider_health", fake_probe_one)
    monkeypatch.setattr("src.core.llm.factory.check_all_providers_health", fake_probe_all)


@pytest.mark.asyncio
async def test_first_call_probes_then_second_hits_cache(monkeypatch):
    calls: list[str] = []
    _patch_probe(monkeypatch, {"mimo": (True, "服务可达")}, calls)

    first = await llm_cache.get_health(["mimo"])
    second = await llm_cache.get_health(["mimo"])

    assert first["mimo"] == (True, "服务可达")
    assert second["mimo"] == (True, "服务可达")
    assert calls == ["mimo"], "第二次必须命中缓存，不能再打网络"


@pytest.mark.asyncio
async def test_concurrent_calls_share_single_probe(monkeypatch):
    calls: list[str] = []
    _patch_probe(monkeypatch, {"mimo": (True, "服务可达")}, calls)

    results = await asyncio.gather(*(llm_cache.get_health(["mimo"]) for _ in range(5)))

    assert all(r["mimo"][0] for r in results)
    assert calls == ["mimo"], "并发调用必须共享同一个探测任务"


@pytest.mark.asyncio
async def test_stale_returns_old_value_and_refreshes_in_background(monkeypatch):
    calls: list[str] = []

    async def fake_probe_one(provider: str):
        calls.append(provider)
        return (True, f"第{len(calls)}次")

    monkeypatch.setattr("src.core.llm.factory.check_provider_health", fake_probe_one)

    await llm_cache.get_health(["mimo"])
    assert calls == ["mimo"]

    # max_age=0 → 缓存立刻算过期
    stale = await llm_cache.get_health(["mimo"], max_age=0.0)
    assert stale["mimo"] == (True, "第1次"), "过期时必须先返回旧值，不能阻塞"

    # 等后台刷新跑完
    await asyncio.sleep(0.1)
    fresh = await llm_cache.get_health(["mimo"])
    assert fresh["mimo"] == (True, "第2次"), "后台刷新后应拿到新值"


@pytest.mark.asyncio
async def test_set_health_prefills_cache(monkeypatch):
    """启动预检写进来的结果应当直接被 /llm/health 命中。"""
    calls: list[str] = []
    _patch_probe(monkeypatch, {"mimo": (True, "应不该被调用")}, calls)

    llm_cache.set_health({"mimo": (True, "预检结果")})
    result = await llm_cache.get_health(["mimo"])

    assert result["mimo"] == (True, "预检结果")
    assert calls == [], "预检已填缓存，不该再探测一次"


@pytest.mark.asyncio
async def test_invalidate_health_forces_next_probe(monkeypatch):
    calls: list[str] = []
    _patch_probe(monkeypatch, {"mimo": (True, "服务可达")}, calls)

    await llm_cache.get_health(["mimo"])
    llm_cache.invalidate_health()
    await llm_cache.get_health(["mimo"])

    assert len(calls) == 2, "invalidate 之后必须重新探测"


@pytest.mark.asyncio
async def test_single_provider_probe_does_not_touch_others(monkeypatch):
    """定点探活只探那一个 provider。

    顶栏灯只关心当前生效的 provider —— 别的 provider 不可达不该拖慢它。
    """
    calls: list[str] = []
    _patch_probe(monkeypatch, {"mimo": (True, "服务可达")}, calls)

    result = await llm_cache.get_health(["mimo"])

    assert result["mimo"] == (True, "服务可达")
    assert calls == ["mimo"], "只该探 mimo，不能碰其它 provider"


@pytest.mark.asyncio
async def test_preflight_and_health_share_one_probe(monkeypatch):
    """启动预检与 ``GET /llm/health`` 必须**共用同一轮探测**。

    之前 ``_preflight_providers`` 直接调 ``check_all_providers_health()``，
    绕过了 cache 的任务共享 → 两边各打一轮外部网络：
    前端启动那一下 ``/llm/health`` 还要再干等一整轮探测，
    同一个 provider 也被探测两次。
    """
    calls: list[str] = []
    _patch_probe(monkeypatch, {"mimo": (True, "服务可达")}, calls)

    # ⚠️ 函数体内 import：``conftest.temp_db`` 会把 ``src.*`` 从 sys.modules
    # 删掉再重导，模块级 import 拿到的引用会指向**旧对象**，断言就不成立。
    from src.core.llm import cache as cache_mod
    from src.main import _preflight_providers

    await _preflight_providers()
    result = await cache_mod.get_health(["mimo"])

    assert result["mimo"] == (True, "服务可达")
    assert calls.count("mimo") == 1, "预检和 /llm/health 只能探测一次"


@pytest.mark.asyncio
async def test_models_cached_and_force_bypasses(monkeypatch):
    calls: list[str] = []

    async def fake_describe(provider: str):
        calls.append(provider)
        return {"models": ["m1"], "live_models": ["m1"]}

    monkeypatch.setattr("src.core.llm.factory.describe_provider_models", fake_describe)

    first = await llm_cache.get_models("mimo")
    second = await llm_cache.get_models("mimo")

    assert first["models"] == ["m1"]
    assert second["models"] == ["m1"]
    assert calls == ["mimo"], "第二次应命中缓存"

    forced = await llm_cache.get_models("mimo", force=True)
    assert forced["models"] == ["m1"]
    assert calls == ["mimo", "mimo"], "force=True 必须绕过缓存"


@pytest.mark.asyncio
async def test_invalidate_models_is_scoped(monkeypatch):
    calls: list[str] = []

    async def fake_describe(provider: str):
        calls.append(provider)
        return {"models": [provider]}

    monkeypatch.setattr("src.core.llm.factory.describe_provider_models", fake_describe)

    await llm_cache.get_models("mimo")
    await llm_cache.get_models("minimax")
    llm_cache.invalidate_models("mimo")

    await llm_cache.get_models("mimo")
    await llm_cache.get_models("minimax")

    assert calls == ["mimo", "minimax", "mimo"], "只应清掉被指定的那个 provider"
