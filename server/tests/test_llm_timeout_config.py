"""OpenAICompatClient 默认 timeout + retry 配置（Phase 3.4 修）。

背景：原代码 timeout_seconds=60, max_retries=3，且 retry 不覆盖 TimeoutException。
minimax 海外节点偶尔卡 60s+ 时，60s × 3 = 180s 远超 Rust 120s timeout。
修后：timeout 30s，retries 2，retry 包含 TimeoutException。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.llm.openai_compat import OpenAICompatClient


@pytest.fixture
def client() -> OpenAICompatClient:
    return OpenAICompatClient(
        config={
            "base_url": "https://api.test.com/v1",
            "default_model": "test-model",
            "provider_name": "test",
        },
        api_key="sk-test",  # 直接传，绕过 _resolve_api_key 找 env var
    )


def test_default_timeout_is_30s(client: OpenAICompatClient) -> None:
    """默认 timeout 应是 30s（不是 60s）。

    60s × 3 retry = 180s 远超 Rust 120s timeout，导致前端报 network error。
    """
    assert client._timeout_s == 30.0


def test_default_max_retries_is_2(client: OpenAICompatClient) -> None:
    assert client._max_retries == 2


@pytest.mark.asyncio
async def test_timeout_exception_triggers_retry() -> None:
    """httpx.TimeoutException 应触发 retry（原代码只 retry TransportError，漏了 timeout）。"""
    call_count = 0

    async def fake_post(*_args: object, **_kw: object) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.TimeoutException("timeout", request=httpx.Request("POST", "/"))
        # 第二次成功
        return httpx.Response(
            200,
            json={
                "id": "x",
                "model": "test",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            },
            request=httpx.Request("POST", "/"),
        )

    with patch.object(OpenAICompatClient, "_resolve_api_key", return_value="sk-test"):
        c = OpenAICompatClient(
            config={
                "base_url": "https://api.test.com/v1",
                "default_model": "test-model",
                "provider_name": "test",
                "max_retries": 3,
            },
            api_key="sk-test",
        )
        # 用 AsyncMock 包 fake_post 避免 httpx 真实连接
        mock_http = AsyncMock()
        mock_http.post = fake_post
        # close 也要支持
        mock_http.aclose = AsyncMock()
        c._client = mock_http
        resp = await c._non_stream_chat({"messages": [], "temperature": 0.7})
    assert call_count == 2  # 第一次 timeout → retry 一次成功
    assert resp.content == "ok"
