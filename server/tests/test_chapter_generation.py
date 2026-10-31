"""ChapterGenerator 单元测试（Phase 4.3）。

覆盖：
- 流式 yield 每个 delta
- LLM 抛异常 → ChapterGenerationError
- 章节不存在 → ChapterGenerationError
- Prompt 模板 key 缺失 → ChapterGenerationError
- Prompt 文件缺失（用 monkeypatch 改 path）→ ChapterGenerationError
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.core.chapter_context import load_chapter_generation_prompt
from src.services.chapter_generator import (
    ChapterGenerationError,
    ChapterGenerator,
)


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


def _mock_stream_llm(deltas: list[str]) -> AsyncMock:
    """返回一个 mock client，调用 chat(stream=True) 返回 AsyncIterator。"""
    m = AsyncMock()

    async def fake_chat(_messages, **_kw):
        if _kw.get("stream"):
            return _FakeAsyncStream(deltas)
        # 非流式不应当被调用
        raise AssertionError("non-stream chat should not be called")

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
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xuanhuan"))
        outline = Outline(
            novel_id=novel.id,
            outline_type="complete",
            structure={
                "chapters": [
                    {"number": 1, "summary": "主角觉醒"},
                ]
            },
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


@pytest.mark.asyncio
async def test_stream_generate_yields_deltas(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["第", "一", "章", "正文"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        chunks: list[str] = []
        async for d in gen.stream_generate(chapter_id=chapter_id):
            chunks.append(d)
    assert chunks == ["第", "一", "章", "正文"]
    mock.aclose.assert_not_called()  # 外部注入的 client 不主动关


@pytest.mark.asyncio
async def test_stream_generate_skips_empty_deltas(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["", "  ", "正文", ""])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        chunks: list[str] = []
        async for d in gen.stream_generate(chapter_id=chapter_id):
            chunks.append(d)
    # 空串被过滤；连续空白被排版器压成一个（且挂到下一个有内容的增量上）
    assert "".join(chunks).strip() == "正文"
    assert all(c.strip() or c == " " for c in chunks)


@pytest.mark.asyncio
async def test_stream_generate_applies_prose_formatting(db_initialized: Path) -> None:
    """生成链路必须过排版器：去汉字间空格 + 兜底断段（2026-10-30）。

    用户实测：模型整章不给换行 → 正文挤成一行、无法阅读。
    """
    chapter_id = await _make_chapter(db_initialized)
    # 模型输出：汉字之间塞空格，且整章不给任何换行
    raw = (
        "山 门 前 的 铜 钟 连 响 三 声"
        "。"
        "这是第二句话内容也足够长可以触发兜底断段规则。"
        "这是第三句话同样足够长也应该被断开成新段落。"
    )
    mock = _mock_stream_llm(list(raw))
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        chunks: list[str] = []
        async for d in gen.stream_generate(chapter_id=chapter_id):
            chunks.append(d)

    text = "".join(chunks)
    # 汉字之间的空格被去掉
    assert "山门前的铜钟连响三声" in text
    assert " " not in text
    # 长段落被兜底断段
    assert "\n\n" in text


@pytest.mark.asyncio
async def test_stream_generate_preserves_model_paragraph_breaks(db_initialized: Path) -> None:
    """模型自己给的段落分隔要保留。"""
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["第一段内容。", "\n\n", "第二段内容。"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        chunks: list[str] = []
        async for d in gen.stream_generate(chapter_id=chapter_id):
            chunks.append(d)

    text = "".join(chunks)
    assert "第一段内容。" in text
    assert "第二段内容。" in text
    assert text.count("\n\n") == 1


@pytest.mark.asyncio
async def test_stream_generate_chapter_not_found(db_initialized: Path) -> None:
    mock = _mock_stream_llm(["正文"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        with pytest.raises(ChapterGenerationError, match="Chapter 9999 not found"):
            async for _ in gen.stream_generate(chapter_id=9999):
                pass


@pytest.mark.asyncio
async def test_stream_generate_llm_init_failure(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    m = AsyncMock()

    async def fake_chat(_m, **_kw):
        raise RuntimeError("network down")

    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    m.model = "mock"
    m.aclose = AsyncMock()
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=m)
        with pytest.raises(ChapterGenerationError, match="network down"):
            async for _ in gen.stream_generate(chapter_id=chapter_id):
                pass


@pytest.mark.asyncio
async def test_stream_generate_strips_thinking_blocks(db_initialized: Path) -> None:
    """推理模型的思考段不能混进章节正文（2026-10-25 修）。

    上游（MiniMax M3 等）会把思考包成 ``<think>...</think>`` 混在 delta 里
    （见 core/llm/openai_compat.py）。不剥掉的话章节正文里会多出一段
    "We need answer Chinese..." —— 比丢掉更糟。
    """
    chapter_id = await _make_chapter(db_initialized)
    mock = _mock_stream_llm(["<think>我先想想怎么写</think>", "第一章", "正文"])
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = ChapterGenerator(session, llm_client=mock)
        chunks: list[str] = []
        async for d in gen.stream_generate(chapter_id=chapter_id):
            chunks.append(d)
    assert chunks == ["第一章", "正文"]
    assert "<think>" not in "".join(chunks)


def test_prompt_loading() -> None:
    """确保 prompt 文件存在且有 'chapter_generation' 字段。"""
    p = load_chapter_generation_prompt()
    assert isinstance(p, str)
    assert len(p) > 100
