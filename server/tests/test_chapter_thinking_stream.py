"""章节流式：思考内容单独一路（AGENTS.md §4.7 铁律）。

背景
----
推理模型（MiniMax M3 等）先吐好几秒 ``<think>`` 再开始写正文。
以前章节生成 / 重写把思考整段丢掉（``if kind == KIND_THINK: continue``），
后果有两个：

1. **思考期是空窗** —— 前端一个字都收不到 → 用户看到"生成卡住不动"；
2. 思考内容要是直接混进正文 → 章节里冒出 "We need answer Chinese..."。

现在：思考走 ``thinking`` 事件，正文走 ``text`` 增量 —— **两者都不丢**。

覆盖：
- service 层：``stream_generate_parts`` / ``stream_rewrite_parts`` 拆成两路
- service 层：兼容入口 ``stream_generate`` 只吐正文（不影响老调用方）
- API 层：端点把思考发成 ``{"event": "thinking", "text": ...}`` 帧
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core.llm.streaming import KIND_TEXT, KIND_THINK
from src.schemas.chapter import ChapterGenerateRequest, ChapterRewriteRequest
from src.services.chapter_generator import ChapterGenerator
from src.services.chapter_rewriter import ChapterRewriter


class _FakeAsyncStream:
    """模拟流式 LLM 客户端的 AsyncIterator。"""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas
        self._idx = 0

    def __aiter__(self) -> _FakeAsyncStream:
        return self

    async def __anext__(self) -> str:
        if self._idx >= len(self._deltas):
            raise StopAsyncIteration
        d = self._deltas[self._idx]
        self._idx += 1
        return d


def _mock_stream_llm(deltas: list[str]) -> Any:
    """返回一个 mock client，调用 chat(stream=True) 返回 AsyncIterator。"""
    from unittest.mock import AsyncMock

    m = AsyncMock()

    async def fake_chat(_messages, **_kw):
        return _FakeAsyncStream(deltas)

    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    m.model = "mock-model"
    m.aclose = AsyncMock()
    return m


async def _make_chapter(db_initialized: Path) -> int:
    """最小数据集：novel + 1 个 outline + 1 个 chapter。返回 chapter_id。"""
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.models.outline import Outline
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="思考测试", genre="xuanhuan"))
        outline = Outline(
            novel_id=novel.id,
            outline_type="complete",
            structure={"chapters": [{"number": 1, "summary": "主角觉醒"}]},
        )
        session.add(outline)
        chapter = Chapter(
            novel_id=novel.id,
            chapter_number=1,
            title="第一章",
            status="drafting",
        )
        session.add(chapter)
        await session.commit()
        return chapter.id


# ===== service 层 =====


@pytest.mark.asyncio
async def test_stream_generate_parts_splits_thinking_and_text(db_initialized: Path) -> None:
    """思考与正文必须拆成两路，且顺序保持上游顺序。"""
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["<think>我先想想</think>", "第一章", "正文"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        parts: list[tuple[str, str]] = []
        async for part in gen.stream_generate_parts(chapter_id=chapter_id):
            parts.append(part)

    assert parts == [
        (KIND_THINK, "我先想想"),
        (KIND_TEXT, "第一章"),
        (KIND_TEXT, "正文"),
    ]


@pytest.mark.asyncio
async def test_stream_generate_compat_yields_only_body(db_initialized: Path) -> None:
    """兼容入口 ``stream_generate`` 仍然只吐正文（老调用方不受影响）。"""
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["<think>我先想想</think>", "第一章", "正文"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        chunks: list[str] = []
        async for d in gen.stream_generate(chapter_id=chapter_id):
            chunks.append(d)

    assert chunks == ["第一章", "正文"]
    assert "<think>" not in "".join(chunks)


@pytest.mark.asyncio
async def test_stream_rewrite_parts_splits_thinking_and_text(db_initialized: Path) -> None:
    """重写路径同样要拆两路。"""
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["<think>重新组织语言</think>", "改写后的段落"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        rewriter = ChapterRewriter(session, llm_client=mock)
        parts: list[tuple[str, str]] = []
        async for part in rewriter.stream_rewrite_parts(
            chapter_id=chapter_id,
            original_text="原来的段落",
            user_prompt="更紧凑",
        ):
            parts.append(part)

    assert parts == [
        (KIND_THINK, "重新组织语言"),
        (KIND_TEXT, "改写后的段落"),
    ]


# ===== API 层 =====


class _FakeGenerator:
    """顶替 ChapterGenerator：只吐两路片段。"""

    def __init__(self, session: Any) -> None:
        self.session = session

    async def stream_generate_parts(self, **_kw: Any):
        yield (KIND_THINK, "先构思一下")
        yield (KIND_TEXT, "正文开始")

    def _get_llm(self) -> Any:
        class _L:
            provider = "mock"
            model = "mock-model"

        return _L()


class _FakeRewriter:
    """顶替 ChapterRewriter。"""

    def __init__(self, session: Any) -> None:
        self.session = session

    async def stream_rewrite_parts(self, **_kw: Any):
        yield (KIND_THINK, "换个说法")
        yield (KIND_TEXT, "改写结果")


def _parse_lines(lines: list[bytes]) -> list[dict[str, Any]]:
    return [json.loads(line.decode("utf-8")) for line in lines if line.strip()]


@pytest.mark.asyncio
async def test_chapter_generate_endpoint_emits_thinking_event(
    db_initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """端点要把思考发成 ``thinking`` 事件（前端才能显示"模型思考中…"）。"""
    from src.api import chapter_generation as api_mod
    from src.db import SessionLocal

    monkeypatch.setattr(api_mod, "ChapterGenerator", _FakeGenerator)

    chapter_id = await _make_chapter(db_initialized)
    payload = ChapterGenerateRequest(user_prompt="写第一章", target_word_count=2000)

    async with SessionLocal() as session:
        lines = [
            line async for line in api_mod._stream_chapter_generate(chapter_id, payload, session)
        ]

    events = _parse_lines(lines)
    thinking = [e for e in events if e.get("event") == "thinking"]
    body = [e for e in events if "text" in e and e.get("event") != "thinking"]

    assert thinking and thinking[0]["text"] == "先构思一下"
    assert body and body[0]["text"] == "正文开始"
    # 思考**不能**混进正文增量
    assert all("先构思一下" != e.get("text") for e in body)


@pytest.mark.asyncio
async def test_chapter_rewrite_endpoint_emits_thinking_event(
    db_initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """重写端点同样发 ``thinking`` 事件。"""
    from src.api import chapter_generation as api_mod
    from src.db import SessionLocal

    monkeypatch.setattr(api_mod, "ChapterRewriter", _FakeRewriter)

    chapter_id = await _make_chapter(db_initialized)
    payload = ChapterRewriteRequest(
        original_text="原来的段落",
        user_prompt="更紧凑",
        from_pos=0,
        to_pos=5,
    )

    async with SessionLocal() as session:
        lines = [
            line async for line in api_mod._stream_chapter_rewrite(chapter_id, payload, session)
        ]

    events = _parse_lines(lines)
    thinking = [e for e in events if e.get("event") == "thinking"]
    body = [e for e in events if "text" in e and e.get("event") != "thinking"]

    assert thinking and thinking[0]["text"] == "换个说法"
    assert body and body[0]["text"] == "改写结果"
