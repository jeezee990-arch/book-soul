"""测试模型清单端点 + "模型名不对"的错误映射。

背景（2026-10-22 的真实故障）
----------------------------
用户只在设置页填了 minimax 的 API Key，生成就报：

    LLM HTTP [HTTP 400] Unsupported model mimo-v2.5-pro

三个原因叠在一起：

1. ``config/llm.yaml`` 写死了已下线的模型名 ``mimo-v2.5-pro``
   （服务端 2026-10 只有 v2.6 系列）
2. ``routing.<场景>`` 把所有场景钉死在 mimo，**设置页选的 provider 根本没被读**
3. 报错文案是干巴巴的 400，看不出"换个模型就好了"

本文件锁住修复后的行为：

- ``GET /llm/models?provider=X`` 能列出服务端真实支持的模型
- 上游回 400 "Unsupported model" 时抛 :class:`ModelNotFoundError`，
  且文案里带"去设置页换模型"的可操作提示
"""

from __future__ import annotations

import httpx
import pytest

# ⚠️ 异常类必须顶层 import（conftest.temp_db 会重建 src.*，见 test_llm_streaming_contract.py）
from src.core.llm.base import ChatMessage, LLMError, ModelNotFoundError
from src.core.llm.openai_compat import OpenAICompatClient


def _client_returning(status: int, body: dict, **overrides) -> OpenAICompatClient:
    """构造一个固定返回某状态码的客户端。"""
    config: dict = {
        "base_url": "http://llm.test/v1",
        "api_key_env": "",
        "default_model": "mimo-v2.5-pro",
        "provider_name": "mimo",
        "timeout_seconds": 5,
        "max_retries": 1,
        "model_specs": {"mimo-v2.5-pro": {"max_output_tokens": 4096}},
    }
    config.update(overrides)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return OpenAICompatClient(config, api_key="test-key", transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_unsupported_model_raises_model_not_found():
    """上游 400 "Unsupported model" → ModelNotFoundError（不是干巴巴的 LLMError）。"""
    client = _client_returning(
        400,
        {"error": {"message": "Unsupported model mimo-v2.5-pro"}},
    )
    with pytest.raises(ModelNotFoundError) as exc:
        await client.chat([ChatMessage("user", "hi")])

    msg = str(exc.value)
    # 文案要带上模型名 + 可操作提示
    assert "mimo-v2.5-pro" in msg
    assert "设置" in msg


@pytest.mark.asyncio
async def test_plain_400_is_still_generic_error():
    """普通 400 仍走 LLMError（别把所有 400 都当成模型问题）。"""
    client = _client_returning(400, {"error": {"message": "bad request: prompt too long"}})
    with pytest.raises(LLMError) as exc:
        await client.chat([ChatMessage("user", "hi")])
    assert not isinstance(exc.value, ModelNotFoundError)


@pytest.mark.asyncio
async def test_unknown_model_markers_are_recognized():
    """上游换几种说法也要认出来（都当成"模型名不对"）。"""
    markers = [
        "Unsupported model foo",
        "model_not_found",
        "The model does not exist",
        "unknown model: foo",
    ]
    for text in markers:
        client = _client_returning(400, {"error": {"message": text}})
        with pytest.raises(ModelNotFoundError):
            await client.chat([ChatMessage("user", "hi")])


@pytest.mark.asyncio
async def test_unknown_model_uses_provider_default_max_tokens():
    """模型没登记规格时，按 provider 级 default_max_output_tokens 补 max_tokens。"""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    config = {
        "base_url": "http://llm.test/v1",
        "api_key_env": "",
        "default_model": "brand-new-model",
        "provider_name": "mimo",
        "timeout_seconds": 5,
        "max_retries": 1,
        "model_specs": {},
        "default_max_output_tokens": 8192,
    }
    client = OpenAICompatClient(config, api_key="k", transport=httpx.MockTransport(handler))
    await client.chat([ChatMessage("user", "hi")])
    assert seen["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_llm_models_endpoint_returns_configured_models():
    """GET /llm/models 至少要返回 llm.yaml 里登记的模型（即使 provider 连不上）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/llm/models", params={"provider": "ollama"})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["provider"] == "ollama"
    assert "qwen2.5:14b" in data["configured_models"]
    assert data["default_model"] == "qwen2.5:14b"
    # 本机没跑 Ollama → reachable=False，但接口不能挂
    assert data["reachable"] is False
    assert data["message"]


@pytest.mark.asyncio
async def test_llm_models_endpoint_unknown_provider_404():
    """未知 provider 返回 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/llm/models", params={"provider": "totally_made_up"})

    assert resp.status_code == 404
