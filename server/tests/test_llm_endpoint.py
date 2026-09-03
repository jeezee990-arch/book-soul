"""测试 /llm/test 端点：stub 模式（CI 友好）+ 真实模式跳过。"""

from __future__ import annotations

import pytest


@pytest.fixture
def stub_env(monkeypatch):
    """BOOK_SOUL_SKIP_LLM=1 触发 stub，不真打 LLM。"""
    monkeypatch.setenv("BOOK_SOUL_SKIP_LLM", "1")
    # 强制 reload src.* 让 BOOK_SOUL_SKIP_LLM 在 endpoint 读取时生效
    import sys

    for name in [n for n in sys.modules if n.startswith("src.")]:
        del sys.modules[name]
    yield


@pytest.mark.asyncio
async def test_llm_test_stub_returns_prompt(stub_env):
    """stub 模式应返回 [stubbed] echo: <prompt>。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/llm/test",
            json={"prompt": "你好世界", "max_tokens": 50},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["content"] == "[stubbed] echo: 你好世界"
    assert data["total_tokens"] > 0
    assert data["provider"] == "minimax"  # default


@pytest.mark.asyncio
async def test_llm_test_default_max_tokens(stub_env):
    """不传 max_tokens 时用默认值 200。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/llm/test", json={"prompt": "test"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_llm_test_uses_specified_provider(stub_env):
    """指定 provider 字段应被使用。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/llm/test", json={"prompt": "test", "provider": "ollama"})
    assert resp.status_code == 200
    assert resp.json()["provider"] == "ollama"


@pytest.mark.asyncio
async def test_llm_test_accepts_null_system(stub_env):
    """system 字段为 null 时不应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 显式发 system=null（模拟 Rust 端未跳过 None 字段的情况）
        resp = await client.post("/llm/test", json={"prompt": "test", "system": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"].startswith("[stubbed]")
