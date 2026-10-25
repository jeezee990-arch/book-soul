"""推理模型"思考内容"转发 + token 预算测试（2026-10-25 新增）。

背景
----
2026-10-25 用户实测报了两个现象：

1. 生成像"先想完再一口气吐出来"，中间是空的；
2. 偶发 ``version N empty``（某个剧情版本没产出正文）。

实测 MiniMax-M3.1-Flash 的一次响应，``delta`` 字段分布是::

    {'role': 195, 'reasoning_content': 172, 'content': 21}

也就是 **172/195 个片段是"思考"**，正文只有 21 个片段（404 字符），
而且正文首字在 8.66s 才到。两个根因：

- 后端 :func:`extract_delta_text` 只读 ``delta.content`` → 思考被整段丢掉 →
  思考期前端一个字都收不到 → 用户看到的"阻塞"；
- 思考 token **同样计入** ``max_tokens`` 额度 → 剧情场景的正文预算
  （2048）被思考吃光 → 正文为空 → "version N empty"。

本文件锁住这两个修复：

- :func:`extract_delta_reasoning` 能识别各家 provider 的思考字段；
- 流式客户端把思考包成 ``<think>...</think>`` 转发（下游 ThinkSplitter 会拆）；
- :meth:`OpenAICompatClient._effective_max_tokens` 会给推理模型留思考预算。
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.core.llm.base import ChatMessage
from src.core.llm.openai_compat import OpenAICompatClient
from src.core.llm.streaming import extract_delta_reasoning, extract_delta_text

# =====================================================================
# extract_delta_reasoning：各家 provider 的字段名
# =====================================================================


def test_extract_reasoning_from_minimax_field() -> None:
    """MiniMax 用 ``reasoning_content``（2026-10-25 实测确认）。"""
    chunk = {"choices": [{"delta": {"reasoning_content": "We need answer Chinese"}}]}
    assert extract_delta_reasoning(chunk) == "We need answer Chinese"


def test_extract_reasoning_from_reasoning_field() -> None:
    """部分 OpenAI 兼容端用 ``reasoning``。"""
    chunk = {"choices": [{"delta": {"reasoning": "思考中"}}]}
    assert extract_delta_reasoning(chunk) == "思考中"


def test_extract_reasoning_from_thinking_field() -> None:
    """Ollama 原生协议用 ``thinking``。"""
    chunk = {"choices": [{"delta": {"thinking": "让我想想"}}]}
    assert extract_delta_reasoning(chunk) == "让我想想"


def test_extract_reasoning_returns_empty_when_absent() -> None:
    """没有思考字段 → 空串（不能报错，也不能返回 None）。"""
    assert extract_delta_reasoning({"choices": [{"delta": {"content": "正文"}}]}) == ""
    assert extract_delta_reasoning({"choices": []}) == ""
    assert extract_delta_reasoning({}) == ""


def test_extract_reasoning_ignores_content_field() -> None:
    """正文不能被当成思考（两者必须分开）。"""
    chunk = {"choices": [{"delta": {"content": "正文", "reasoning_content": "思考"}}]}
    assert extract_delta_reasoning(chunk) == "思考"
    assert extract_delta_text(chunk) == "正文"


# =====================================================================
# 流式客户端：思考内容被包成 think 标签转发
# =====================================================================


def _sse_line(delta: dict) -> bytes:
    """构造一条 OpenAI 兼容的 SSE data 行。"""
    payload = {"choices": [{"delta": delta}]}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


class _SseStream(httpx.AsyncByteStream):
    """把预设的 SSE 行包装成 httpx 能增量读取的字节流。"""

    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    async def __aiter__(self):
        for line in self.lines:
            yield line
        yield b"data: [DONE]\n\n"


def _make_client(lines: list[bytes], **overrides) -> OpenAICompatClient:
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
        "model_specs": {"test-model": {"max_output_tokens": 32000}},
    }
    config.update(overrides)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_SseStream(lines),
        )

    return OpenAICompatClient(
        config,
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_stream_forwards_reasoning_as_think_tag() -> None:
    """思考内容必须被转发（包成 think 标签），不能被静默丢掉。"""
    lines = [
        _sse_line({"role": "assistant"}),
        _sse_line({"reasoning_content": "先想一下"}),
        _sse_line({"content": "正文开始"}),
    ]
    client = _make_client(lines)

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    deltas = [d async for d in stream]  # type: ignore[union-attr]

    assert "<think>先想一下</think>" in deltas
    assert "正文开始" in deltas


@pytest.mark.asyncio
async def test_stream_text_is_not_polluted_by_reasoning() -> None:
    """正文 delta 本身不能被思考污染（下游用 ThinkSplitter 拆）。"""
    lines = [
        _sse_line({"reasoning_content": "思考A"}),
        _sse_line({"content": "正文A"}),
        _sse_line({"reasoning_content": "思考B"}),
        _sse_line({"content": "正文B"}),
    ]
    client = _make_client(lines)

    stream = await client.chat([ChatMessage("user", "hi")], stream=True)
    deltas = [d async for d in stream]  # type: ignore[union-attr]

    # 用 ThinkSplitter 拆开后，正文里不能出现任何思考内容
    from src.core.llm.streaming import KIND_TEXT, ThinkSplitter

    splitter = ThinkSplitter()
    text_parts: list[str] = []
    for delta in deltas:
        for kind, text in splitter.feed(delta):
            if kind == KIND_TEXT:
                text_parts.append(text)
    joined = "".join(text_parts)
    assert joined == "正文A正文B"
    assert "思考" not in joined


# =====================================================================
# max_tokens 预算：正文预算 + 思考预算
# =====================================================================


def test_effective_max_tokens_adds_reasoning_overhead() -> None:
    """正文预算 + 思考预算（2026-10-25 修 version N empty 的关键）。"""
    client = _make_client([], reasoning_token_overhead=8192)
    # 正文预算 2048（剧情场景）+ 思考 8192
    assert client._effective_max_tokens("test-model", 2048) == 2048 + 8192


def test_effective_max_tokens_capped_by_model_hard_limit() -> None:
    """不能超过模型硬上限（超过上游会直接 400）。"""
    client = _make_client(
        [],
        reasoning_token_overhead=8192,
        model_specs={"test-model": {"max_output_tokens": 4096}},
    )
    assert client._effective_max_tokens("test-model", 2048) == 4096


def test_effective_max_tokens_without_overhead_is_unchanged() -> None:
    """没配思考预算的 provider 行为不变（非推理模型不受影响）。"""
    client = _make_client([])
    assert client._effective_max_tokens("test-model", 2048) == 2048
    assert client._effective_max_tokens("test-model", None) == 32000


def test_effective_max_tokens_uses_provider_default_when_unspecified() -> None:
    """业务层没给 max_tokens → 用 provider 级正文默认预算。"""
    client = _make_client(
        [],
        reasoning_token_overhead=4096,
        default_max_output_tokens=16384,
    )
    assert client._effective_max_tokens("test-model", None) == 16384 + 4096


def test_unknown_model_falls_back_to_provider_default() -> None:
    """用户自填了没登记的模型名 → 按 provider 级能力值兜底。"""
    client = _make_client(
        [],
        reasoning_token_overhead=4096,
        default_max_output_tokens=16384,
    )
    value = client._effective_max_tokens("brand-new-model", 2048)
    assert value == 2048 + 4096
