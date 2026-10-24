"""API Key 链路 + LLM 探测超时的单元测试。

锁住两件与"生成能不能真的用"直接相关的事：

1. **设置页存的 key 必须真的被 LLM 客户端用到**
   查找顺序是 env > DPAPI 密钥库 > 系统 keyring。这条测试证明
   "用户在设置页填了 key → DPAPI 存下 → LLM 客户端拿到的是它"这条链是通的。
   以前这块没有覆盖，出现问题只能靠真调一次外部 API 才发现。

2. **健康探测的 connect 超时不能大于总超时**
   之前 connect=min(10, timeout) > probe_timeout=5，网络不通的 provider
   在**连接阶段**就能拖满 10 秒 —— 顶栏模型灯被卡住近 10 秒（实测 9.8s）。
"""

from __future__ import annotations

import pytest

from src.schemas.settings import LLMConfig, SettingsUpdate
from src.services.settings_service import SettingsService


class FakeKeyring:
    """内存版 keyring mock。"""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, value: str) -> None:
        self.store[(service, username)] = value

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


@pytest.fixture
def svc(tmp_path) -> SettingsService:
    return SettingsService(
        keyring_backend=FakeKeyring(),
        settings_path=tmp_path / ".book-soul-settings.yaml",
    )


@pytest.fixture
def llm_cache():
    """拿到**当前**的缓存模块。

    ⚠️ 必须在函数体内 import：``conftest.py`` 的 ``temp_db`` fixture 会把
    ``src.*`` 从 ``sys.modules`` 里删掉再重新导入 —— 模块级 import 拿到的引用
    会指向旧对象，断言就永远不成立（单独跑能过、全量跑挂）。
    """
    from src.core.llm import cache as cache_module

    return cache_module


@pytest.fixture(autouse=True)
def _clear_cache(llm_cache):
    """每个用例前后清一次缓存。"""
    llm_cache.reset_all()
    yield
    llm_cache.reset_all()


# =========================================================================
# 1. 设置页存的 key → LLM 客户端真的用上了
# =========================================================================


@pytest.mark.asyncio
async def test_key_in_secret_store_is_used_by_client(monkeypatch):
    """DPAPI 密钥库里的 key 必须被 create_llm_client 取到。"""

    class FakeStore:
        def get(self, provider: str) -> str | None:
            return "sk-from-settings" if provider == "mimo" else None

    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.setattr("src.core.security.secret_store.get_secret_store", lambda: FakeStore())

    from src.core.llm.factory import _resolve_api_key_for, create_llm_client

    assert _resolve_api_key_for("mimo") == "sk-from-settings"

    client = create_llm_client("mimo")
    try:
        assert client._api_key == "sk-from-settings"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_env_key_wins_over_secret_store(monkeypatch):
    """env 优先级最高（AGENTS.md §6 定的顺序）。

    注意：``settings`` 是**启动时**读一次 env 的单例，所以运行时改 os.environ
    不会反映到它身上 —— 这里直接改 settings 实例的字段来模拟"启动时环境里
    就有这个 key"。
    """

    class FakeStore:
        def get(self, provider: str) -> str | None:
            return "sk-from-secret-store"

    from src.core.config import settings

    monkeypatch.setattr(settings, "mimo_api_key", "sk-from-env", raising=False)
    monkeypatch.setattr("src.core.security.secret_store.get_secret_store", lambda: FakeStore())

    from src.core.llm.factory import _resolve_api_key_for

    assert _resolve_api_key_for("mimo") == "sk-from-env"


# =========================================================================
# 2. 改 key 之后缓存要作废
# =========================================================================


def test_set_api_key_invalidates_llm_cache(svc: SettingsService, llm_cache) -> None:
    """换 key 后，之前探测出来的健康状态必须作废。

    不作废的话：用户刚换好 key，顶栏还显示着换之前的"Key 无效"，
    得等缓存过期（60 秒）才更新 —— 用户会以为没生效。
    """
    llm_cache.set_health({"mimo": (True, "旧状态")})
    llm_cache.get_cached_health()
    assert llm_cache.get_cached_health(), "前置条件：先有缓存"

    svc.set_api_key("mimo", "sk-new")

    assert llm_cache.get_cached_health() == {}, "改 key 后健康状态缓存必须清空"


def test_delete_api_key_invalidates_llm_cache(svc: SettingsService, llm_cache) -> None:
    """删 key 同样要作废缓存。"""
    llm_cache.set_health({"mimo": (True, "旧状态")})
    svc.delete_api_key("mimo")
    assert llm_cache.get_cached_health() == {}


def test_update_provider_invalidates_models_cache(svc: SettingsService, llm_cache) -> None:
    """改 provider / model 后，模型清单缓存要作废。"""
    llm_cache._models["mimo"] = (0.0, {"models": ["old"]})
    svc.update(SettingsUpdate(llm=LLMConfig(provider="minimax", model="MiniMax-M3")))
    assert "mimo" not in llm_cache._models


# =========================================================================
# 3. 健康探测的超时
# =========================================================================


@pytest.mark.asyncio
async def test_probe_connect_timeout_never_exceeds_total(monkeypatch):
    """connect 超时必须 ≤ 总超时。

    否则"网络不通"的 provider（没配的 openai、没启动的 ollama）
    会在连接阶段拖满 10 秒，把整批健康检查拖成 ~10 秒。
    """
    captured: dict = {}

    class FakeResp:
        status_code = 200

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, path):
            return FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    from src.core.llm.factory import check_provider_health

    ok, _msg = await check_provider_health("mimo")

    assert ok
    timeout = captured["timeout"]
    assert timeout.connect is not None
    assert timeout.connect <= timeout.read, (
        f"connect 超时({timeout.connect}) 不能大于总超时({timeout.read})"
    )
