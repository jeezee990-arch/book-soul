"""剧情流式的"耗时统计"与"空正文可操作报错"测试（2026-10-25 新增）。

背景
----
用户实测反馈：① 要看到"当前模型耗时多少秒"；② 偶发 ``version N empty``，
但这个文案完全看不出原因。

实测根因：MiniMax-M3.1-Flash 的思考内容走 ``delta.reasoning_content``，
**同样计入** ``max_tokens`` 额度。剧情场景的正文预算是 2048，思考一上来
就吃光 → 模型根本没机会写正文 → 空结果。

所以空正文时必须告诉用户"是思考占满了额度"，而不是干巴巴一句 "empty"。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.services.plot_service import PlotService


class _StreamMockLLM:
    """支持 ``chat(..., stream=True)`` 的 mock 客户端。"""

    provider = "mock"
    model = "mock-model"

    def __init__(self, chunks: list[str] | None = None) -> None:
        self._chunks = chunks if chunks is not None else ["主角", "历经", "苦难"]
        self.chat_calls = 0

    async def chat(self, messages: Any, **kwargs: Any) -> Any:
        self.chat_calls += 1
        if kwargs.get("stream"):

            async def gen():
                for c in self._chunks:
                    await asyncio.sleep(0)
                    yield c

            return gen()
        from src.core.llm.base import ChatResponse

        return ChatResponse(content="".join(self._chunks), model=self.model)


@pytest.mark.asyncio
async def test_stream_done_reports_model_and_timing() -> None:
    """done 事件要带上模型名 + 总耗时 + 首字延迟。"""
    svc = PlotService(llm_client=_StreamMockLLM())
    events: list[dict] = []

    async def run() -> None:
        async for ev in svc.stream_generate("修仙", ["x"], n_versions=1):
            events.append(ev)

    await asyncio.wait_for(run(), timeout=10)

    done = [e for e in events if e["event"] == "done"]
    assert done, "应该有 done 事件"
    assert done[0]["model"] == "mock-model"
    assert done[0]["provider"] == "mock"
    assert isinstance(done[0]["elapsed_sec"], (int, float))
    assert done[0]["elapsed_sec"] >= 0
    assert done[0]["first_delta_sec"] is not None
    assert done[0]["first_delta_sec"] >= 0


@pytest.mark.asyncio
async def test_stream_empty_body_gives_actionable_hint() -> None:
    """只有思考、没有正文 → 报错要说清原因（不能只是 "version N empty"）。"""
    llm = _StreamMockLLM(["<think>我先想想该怎么写这段剧情</think>"])
    svc = PlotService(llm_client=llm)
    events: list[dict] = []

    async def run() -> None:
        async for ev in svc.stream_generate("修仙", ["x"], n_versions=1):
            events.append(ev)

    await asyncio.wait_for(run(), timeout=10)

    errors = [e for e in events if e["event"] == "error"]
    assert errors, "空正文应该报错"
    message = errors[0]["message"]
    # 不能是干巴巴的 "version 1 empty"
    assert "empty" not in message.lower() or "思考" in message
    # 必须提到"思考"和"额度"这两个关键点 —— 用户才知道该干什么
    assert "思考" in message
    assert "额度" in message
    # 并且要给出下一步动作
    assert "重试" in message


@pytest.mark.asyncio
async def test_stream_thinking_is_forwarded_as_thinking_event() -> None:
    """思考内容要作为 ``thinking`` 事件转发（用户能看到"模型思考中…"）。"""
    llm = _StreamMockLLM(["<think>先构思一下</think>", "主角历经苦难"])
    svc = PlotService(llm_client=llm)
    events: list[dict] = []

    async def run() -> None:
        async for ev in svc.stream_generate("修仙", ["x"], n_versions=1):
            events.append(ev)

    await asyncio.wait_for(run(), timeout=10)

    thinking = [e for e in events if e["event"] == "thinking"]
    assert thinking, "应该有 thinking 事件"
    assert "先构思一下" in thinking[0]["text"]

    # 正文仍然是干净的
    done = [e for e in events if e["event"] == "version_done"]
    assert done
    assert "先构思一下" not in done[0]["summary"]
