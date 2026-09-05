"""ChapterRewriter 单元测试（Phase 4.4）。

覆盖：
- 流式 yield 每个 delta
- original_text / user_prompt 为空 → ChapterRewriteError
- 章节不存在 → ChapterRewriteError
- LLM 抛异常 → ChapterRewriteError
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.core.chapter_context import load_chapter_rewrite_prompt
from src.services.chapter_rewriter import ChapterRewriteError, ChapterRewriter


class _FakeAsyncStream:
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


def _mock_stream_llm(deltas: list[str]) -> AsyncMock:
    m = AsyncMock()

    async def fake_chat(_m, **_kw):
        if _kw.get("stream"):
            return _FakeAsyncStream(deltas)
        raise AssertionError("non-stream chat should not be called")

    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    m.model = "mock"
    m.aclose = AsyncMock()
    return m


async def _make_chapter(db_initialized: Path) -> int:
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xuanhuan"))
        ch = Chapter(novel_id=novel.id, chapter_number=1, title="第一章", status="drafting")
        session.add(ch)
        await session.commit()
        return ch.id


@pytest.mark.asyncio
async def test_stream_rewrite_yields_deltas(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["新", "文", "本"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        rw = ChapterRewriter(session, llm_client=mock)
        chunks: list[str] = []
        async for d in rw.stream_rewrite(
            chapter_id=chapter_id,
            original_text="原文",
            user_prompt="更紧凑",
        ):
            chunks.append(d)
    assert chunks == ["新", "文", "本"]


@pytest.mark.asyncio
async def test_stream_rewrite_empty_original(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm([])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        rw = ChapterRewriter(session, llm_client=mock)
        with pytest.raises(ChapterRewriteError, match="original_text is empty"):
            async for _ in rw.stream_rewrite(
                chapter_id=chapter_id,
                original_text="   ",
                user_prompt="更紧凑",
            ):
                pass


@pytest.mark.asyncio
async def test_stream_rewrite_empty_prompt(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm([])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        rw = ChapterRewriter(session, llm_client=mock)
        with pytest.raises(ChapterRewriteError, match="user_prompt is empty"):
            async for _ in rw.stream_rewrite(
                chapter_id=chapter_id,
                original_text="原文",
                user_prompt="",
            ):
                pass


@pytest.mark.asyncio
async def test_stream_rewrite_chapter_not_found(db_initialized: Path) -> None:
    mock = _mock_stream_llm(["x"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        rw = ChapterRewriter(session, llm_client=mock)
        with pytest.raises(ChapterRewriteError, match="Chapter 9999 not found"):
            async for _ in rw.stream_rewrite(
                chapter_id=9999,
                original_text="原文",
                user_prompt="要求",
            ):
                pass


@pytest.mark.asyncio
async def test_stream_rewrite_llm_init_failure(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    m = AsyncMock()

    async def fake_chat(_m, **_kw):
        raise RuntimeError("api error")

    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    m.model = "mock"
    m.aclose = AsyncMock()
    from src.db import SessionLocal

    async with SessionLocal() as session:
        rw = ChapterRewriter(session, llm_client=m)
        with pytest.raises(ChapterRewriteError, match="api error"):
            async for _ in rw.stream_rewrite(
                chapter_id=chapter_id,
                original_text="原文",
                user_prompt="要求",
            ):
                pass


def test_rewrite_prompt_loading() -> None:
    p = load_chapter_rewrite_prompt()
    assert isinstance(p, str)
    assert "{original_text}" in p
    assert "{user_prompt}" in p
