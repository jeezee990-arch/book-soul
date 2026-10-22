"""Web search skill 升级版测试（Phase 7.1 + v2 SerpAPI 接入）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_web_search_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """无 API key：返回明确错误。"""
    from src.core.skills import run_skill

    monkeypatch.delenv("SERPAPI_KEY", raising=False)

    import asyncio

    result = asyncio.run(run_skill("web_search", query="test"))
    assert result.success is False
    assert "SERPAPI_KEY" in (result.error or "")


def _build_fake_client(httpx_response=None, side_effect=None):
    """构造一个 mock httpx.AsyncClient，让 ``async with httpx.AsyncClient() as client`` 工作。

    关键：``__aenter__`` 必须返回 awaitable（async function or coroutine）。
    简单做法：让 ``__aenter__`` 是一个 async 函数，返回 self。
    """

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self._resp = httpx_response
            self._exc = side_effect

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            if self._exc is not None:
                if isinstance(self._exc, Exception):
                    raise self._exc
                raise self._exc
            return self._resp

    return FakeClient()


@pytest.mark.asyncio
async def test_web_search_with_api_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """有 API key + mock 响应：返回 results。"""
    from src.core.skills import run_skill

    monkeypatch.setenv("SERPAPI_KEY", "test-key")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "organic_results": [
            {
                "title": "Result 1",
                "link": "https://example.com/1",
                "snippet": "snip 1",
                "position": 1,
            },
            {
                "title": "Result 2",
                "link": "https://example.com/2",
                "snippet": "snip 2",
                "position": 2,
            },
        ]
    }
    fake_client = _build_fake_client(httpx_response=fake_resp)

    with patch("httpx.AsyncClient", return_value=fake_client):
        r = await run_skill("web_search", query="python tutorial", limit=5)

    assert r.success is True
    assert r.data["count"] == 2
    assert r.data["results"][0]["title"] == "Result 1"
    assert r.data["results"][0]["url"] == "https://example.com/1"


@pytest.mark.asyncio
async def test_web_search_empty_query(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.skills import run_skill

    monkeypatch.setenv("SERPAPI_KEY", "test-key")
    r = await run_skill("web_search", query="")
    assert r.success is False
    assert "query" in (r.error or "")


@pytest.mark.asyncio
async def test_web_search_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from src.core.skills import run_skill

    monkeypatch.setenv("SERPAPI_KEY", "test-key")

    fake_client = _build_fake_client(side_effect=httpx.ConnectError("connection refused"))

    with patch("httpx.AsyncClient", return_value=fake_client):
        r = await run_skill("web_search", query="test")

    assert r.success is False
    assert "HTTP error" in (r.error or "")


@pytest.mark.asyncio
async def test_web_search_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.skills import run_skill

    monkeypatch.setenv("SERPAPI_KEY", "bad-key")

    fake_resp = MagicMock()
    fake_resp.status_code = 401
    fake_resp.text = "Invalid API key"
    fake_client = _build_fake_client(httpx_response=fake_resp)

    with patch("httpx.AsyncClient", return_value=fake_client):
        r = await run_skill("web_search", query="test")

    assert r.success is False
    assert "401" in (r.error or "")


@pytest.mark.asyncio
async def test_web_search_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.skills import run_skill

    monkeypatch.setenv("SERPAPI_KEY", "test-key")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {}  # 没 organic_results
    fake_client = _build_fake_client(httpx_response=fake_resp)

    with patch("httpx.AsyncClient", return_value=fake_client):
        r = await run_skill("web_search", query="test")

    assert r.success is True
    assert r.data["count"] == 0
    assert r.data["results"] == []
