"""流式契约测试 —— 防止"假流式"回归（2026-10 修复的真实 bug）。

背景
----
httpx 的 ``client.post()`` 默认 ``stream=False``，会在返回前
``await response.aread()`` **把整个响应体读完**。

如果用它做流式调用，后端会等模型把整章生成完（约 110 秒）才把数据推给
前端 —— 用户体感就是"流式输出跟阻塞一样"，最后文字唰一下全出来。

真正的流式必须用 ``client.stream()`` 上下文管理器。

本文件的断言方式
----------------
用一个**逐块吐字**的假 SSE 源（每次 yield 前 sleep），记录已吐出的块数：

- 真流式：拿到第一个 chunk 时，源只吐出了 1 块
- 假流式（用了 client.post）：拿到第一个 chunk 时，源已经把全部块吐完了

如果有人把 ``client.stream()`` 改回 ``client.post()``，本文件立刻变红。
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

# ⚠️ 异常类必须在**模块顶层**导入，不能在函数体内 import。
# 原因：conftest.temp_db fixture 会把 src.* 从 sys.modules 里删掉再重新导入，
# 重新导入会生成**新的**异常类对象。若在函数体 import，
# `pytest.raises(AuthError)` 拿到的是新类，而 client 抛出的是旧类 → 永远不匹配。
from src.core.llm.base import AuthError, ChatMessage, ProviderUnavailableError
from src.core.llm.openai_compat import OpenAICompatClient


def _sse_line(content: str) -> bytes:
    """构造一条 OpenAI 兼容的 SSE data 行。"""
    payload = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


class _SlowSseSource:
    """模拟一个逐块吐字、带间隔的 SSE 源，并记录已吐出的块数。"""

    def __init__(self, chunks: list[str], delay: float = 0.05) -> None:
        self.chunks = chunks
        self.delay = delay
        self.produced = 0

    async def __aiter__(self):
        for c in self.chunks:
            await asyncio.sleep(self.delay)
            self.produced += 1
            yield _sse_line(c)
        self.produced += 1  # [DONE]
        yield b"data: [DONE]\n\n"


class _SseStream(httpx.AsyncByteStream):
    """把 _SlowSseSource 包装成 httpx 能增量读取的字节流。"""

    def __init__(self, source: _SlowSseSource) -> None:
        self.source = source

    async def __aiter__(self):
        async for chunk in self.source:
            yield chunk


def _make_client(source: _SlowSseSource, **overrides) -> OpenAICompatClient:
    """构造一个注入 MockTransport 的客户端。"""
    config: dict = {
        "base_url": "http://llm.test/v1",
        "api_key_env": "",
        "default_model": "test-model",
        "provider_name": "test",
        "timeout_seconds": 5,
        "stream_read_timeout": 5,
        "stream_total_timeout": 30,
        "max_retries": 1,
        "model_specs": {"test-model": {"max_output_tokens": 4096}},
    }
    config.update(overrides)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_SseStream(source),
        )

    return OpenAICompatClient(
        config,
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )


# =====================================================================
# 核心契约：第一个 chunk 必须在源吐完之前到达
# =====================================================================


@pytest.mark.asyncio
async def test_stream_yields_first_chunk_before_source_finishes():
    """拿到第一个 chunk 时，源还没吐完 —— 证明是真流式。"""
    source = _SlowSseSource(["你", "好", "世", "界"], delay=0.05)
    client = _make_client(source)

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    assert not isinstance(stream, httpx.Response)

    first = await stream.__anext__()

    assert first == "你"
    assert source.produced < len(source.chunks), (
        f"假流式！第一个 chunk 是在源吐完 {source.produced} 块之后才拿到的。"
        "检查 core/llm/openai_compat.py 的 _stream_chat 是否用了 client.stream()"
    )
    # 更严格：真流式下此刻只应产出 1 块
    assert source.produced <= 1, f"期望此刻只产出 1 块，实际 {source.produced} 块"

    await stream.aclose()


@pytest.mark.asyncio
async def test_stream_yields_incrementally_not_all_at_once():
    """逐块消费：每消费一个，源的产出数应当同步 +1（不是一次性全吐）。"""
    source = _SlowSseSource(["a", "b", "c", "d"], delay=0.05)
    client = _make_client(source)

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)

    seen: list[str] = []
    produced_when_first_seen: list[int] = []
    async for delta in stream:
        seen.append(delta)
        produced_when_first_seen.append(source.produced)

    assert seen == ["a", "b", "c", "d"]
    # 消费第 1 个时源才产出 1 块；消费最后一个时源共产出 4 块 + DONE
    assert produced_when_first_seen[0] <= 1
    assert produced_when_first_seen[-1] <= len(source.chunks) + 1


@pytest.mark.asyncio
async def test_stream_full_text_is_correct():
    """流式拼接结果必须与源内容完全一致（含多字节中文）。"""
    chunks = ["修仙", "归来", "！"]
    source = _SlowSseSource(chunks, delay=0.01)
    client = _make_client(source)

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    text = "".join([delta async for delta in stream])

    assert text == "修仙归来！"


# =====================================================================
# max_tokens 自动填充
# =====================================================================


@pytest.mark.asyncio
async def test_max_tokens_auto_filled_from_model_specs():
    """没传 max_tokens 时，按 model_specs.max_output_tokens 自动补。"""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_SseStream(_SlowSseSource(["ok"], delay=0.01)),
        )

    client = OpenAICompatClient(
        {
            "base_url": "http://llm.test/v1",
            "api_key_env": "",
            "default_model": "test-model",
            "provider_name": "test",
            "model_specs": {"test-model": {"max_output_tokens": 4096}},
        },
        api_key="k",
        transport=httpx.MockTransport(handler),
    )

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    async for _ in stream:
        pass

    assert captured["body"]["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_explicit_max_tokens_wins_over_model_specs():
    """显式传入的 max_tokens 优先于 model_specs。"""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_SseStream(_SlowSseSource(["ok"], delay=0.01)),
        )

    client = OpenAICompatClient(
        {
            "base_url": "http://llm.test/v1",
            "api_key_env": "",
            "default_model": "test-model",
            "provider_name": "test",
            "model_specs": {"test-model": {"max_output_tokens": 4096}},
        },
        api_key="k",
        transport=httpx.MockTransport(handler),
    )

    stream = await client.chat([ChatMessage("user", "hi")], stream=True, max_tokens=128)
    async for _ in stream:
        pass

    assert captured["body"]["max_tokens"] == 128


@pytest.mark.asyncio
async def test_no_max_tokens_when_model_unknown():
    """模型不在 model_specs 里 → 不设 max_tokens（交给上游默认）。"""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_SseStream(_SlowSseSource(["ok"], delay=0.01)),
        )

    client = OpenAICompatClient(
        {
            "base_url": "http://llm.test/v1",
            "api_key_env": "",
            "default_model": "unknown-model",
            "provider_name": "test",
        },
        api_key="k",
        transport=httpx.MockTransport(handler),
    )

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    async for _ in stream:
        pass

    assert "max_tokens" not in captured["body"]


# =====================================================================
# 错误路径
# =====================================================================


@pytest.mark.asyncio
async def test_stream_http_error_raises_mapped_exception():
    """流式请求的 4xx 也要映射成对应异常（且能读到错误 body）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "invalid api key"}},
        )

    client = OpenAICompatClient(
        {
            "base_url": "http://llm.test/v1",
            "api_key_env": "",
            "default_model": "test-model",
            "provider_name": "test",
        },
        api_key="k",
        transport=httpx.MockTransport(handler),
    )

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    with pytest.raises(AuthError) as exc:
        async for _ in stream:
            pass
    assert "invalid api key" in str(exc.value)


@pytest.mark.asyncio
async def test_connect_error_becomes_provider_unavailable():
    """连不上 → ProviderUnavailableError（而不是裸 httpx 异常）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = OpenAICompatClient(
        {
            "base_url": "http://llm.test/v1",
            "api_key_env": "",
            "default_model": "test-model",
            "provider_name": "ollama",
        },
        api_key="k",
        transport=httpx.MockTransport(handler),
    )

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    with pytest.raises(ProviderUnavailableError) as exc:
        async for _ in stream:
            pass
    # ollama 场景要给出"请先启动 Ollama"的可操作提示
    assert "ollama serve" in str(exc.value)
