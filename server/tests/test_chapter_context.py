"""Chapter 上下文 / prompt 加载 单元测试（Phase 4.3 / 4.4）。

覆盖：
- load_chapter_generation_prompt / load_chapter_rewrite_prompt
- format_characters / format_outline
- get_chapter_outline（从 structure 抠本章 vs fallback 到 chapter.outline）
- get_version_tail
- get_recent_summaries
- get_previous_tail
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.chapter_context import (
    format_characters,
    format_outline,
    get_chapter_outline,
    get_previous_tail,
    get_recent_summaries,
    get_version_tail,
    load_chapter_generation_prompt,
    load_chapter_rewrite_prompt,
)
from src.core.llm.base import LLMError

# ===== prompt 加载 =====


def test_load_chapter_generation_prompt() -> None:
    p = load_chapter_generation_prompt()
    assert isinstance(p, str)
    # 关键占位符都在
    for ph in (
        "{novel_name}",
        "{genre}",
        "{outline_mode}",
        "{all_characters}",
        "{novel_outline}",
        "{chapter_outline}",
        "{recent_summaries}",
        "{previous_tail}",
        "{target_word_count}",
        "{user_prompt}",
    ):
        assert ph in p, f"missing placeholder {ph}"


def test_load_chapter_rewrite_prompt() -> None:
    p = load_chapter_rewrite_prompt()
    assert isinstance(p, str)
    for ph in (
        "{genre}",
        "{all_characters}",
        "{chapter_outline}",
        "{original_text}",
        "{user_prompt}",
    ):
        assert ph in p, f"missing placeholder {ph}"


def test_prompt_caches_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """lru_cache 命中：连续调用应返回同一对象。"""
    p1 = load_chapter_generation_prompt()
    p2 = load_chapter_generation_prompt()
    assert p1 is p2


# ===== format_characters / format_outline =====


def test_format_characters_empty() -> None:
    assert format_characters([]) == "（暂无人物卡）"


def test_format_characters_basic() -> None:
    from src.models.character import Character

    c1 = Character(
        id=1,
        novel_id=1,
        name="韩立",
        role="主角",
        basic_info="凡人出身",
        personality="谨慎",
        habits="动手前先想",
        thinking="利弊权衡",
        relationships="南宫婉为道侣",
        growth_arc="从凡人到大乘",
    )
    out = format_characters([c1])
    assert "韩立" in out
    assert "主角" in out
    assert "谨慎" in out
    assert "利弊权衡" in out


def test_format_outline_none_and_empty() -> None:
    assert format_outline(None) == "（暂无大纲）"
    # 空 structure 视为无
    from src.models.outline import Outline

    o = Outline(id=1, novel_id=1, outline_type="freedom", structure={})
    assert format_outline(o) == "（暂无大纲）"


def test_format_outline_with_structure() -> None:
    from src.models.outline import Outline

    o = Outline(
        id=1,
        novel_id=1,
        outline_type="freedom",
        structure={"summary": "凡人修仙热血故事。", "key_beats": ["开端", "发展", "高潮", "收束"]},
    )
    out = format_outline(o)
    assert "凡人修仙" in out
    assert "开端" in out


# ===== get_chapter_outline =====


@pytest.mark.asyncio
async def test_get_chapter_outline_from_structure(db_initialized: Path) -> None:
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
                    {"number": 1, "summary": "主角觉醒血脉"},
                    {"number": 2, "summary": "拜入宗门"},
                ]
            },
        )
        session.add(outline)
        await session.flush()
        chapter = Chapter(novel_id=novel.id, chapter_number=1, title="第一章", status="outline")
        session.add(chapter)
        await session.commit()

    async with SessionLocal() as session:
        ch = await session.get(Chapter, chapter.id)
        o = await session.get(Outline, outline.id)
        text = await get_chapter_outline(session, ch, o)
    assert "主角觉醒血脉" in text


# ===== 需求7：两阶段大纲的 volumes[].chapters[] 嵌套结构 =====


@pytest.mark.asyncio
async def test_get_chapter_outline_from_volumes_structure(db_initialized: Path) -> None:
    """两阶段大纲的章在**卷里面** —— 必须能按位置找到本章（需求7 的核心）。

    旧实现只找顶层 key（chapters / chapter_list / outlines / scenes），
    对 ``volumes[].chapters[]`` 永远找不到 → 章节生成退化成"塞整份 JSON"，
    正文完全没按本章大纲走。
    """
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.models.outline import Outline
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    structure = {
        "volumes": [
            {
                "name": "第一卷 觉醒",
                "summary": "主角觉醒。",
                "chapters": [
                    {"title": "第一章 废柴", "summary": "主角被逐出宗门", "key_events": ["被逐"]},
                    {
                        "title": "第二章 血脉",
                        "summary": "主角觉醒血脉",
                        "key_events": ["觉醒", "反击"],
                    },
                ],
            },
            {
                "name": "第二卷 宗门",
                "summary": "入宗。",
                "chapters": [
                    {"title": "第三章 入宗", "summary": "主角拜入宗门", "key_events": ["拜师"]},
                ],
            },
        ]
    }

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="两阶段", genre="xuanhuan"))
        outline = Outline(novel_id=novel.id, outline_type="complete", structure=structure)
        session.add(outline)
        await session.flush()
        chapter = Chapter(novel_id=novel.id, chapter_number=3, title="第三章", status="outline")
        session.add(chapter)
        await session.commit()

    async with SessionLocal() as session:
        ch = await session.get(Chapter, chapter.id)
        o = await session.get(Outline, outline.id)
        text = await get_chapter_outline(session, ch, o)
    # 第 3 章在第二卷 → 位置推断
    assert "主角拜入宗门" in text
    assert "第二卷 宗门" in text
    assert "拜师" in text
    # 不能把整份 JSON 塞进来
    assert '"volumes"' not in text


@pytest.mark.asyncio
async def test_get_chapter_outline_volumes_respects_explicit_number(
    db_initialized: Path,
) -> None:
    """章节条目带显式章号时，优先按章号匹配。"""
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.models.outline import Outline
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    structure = {
        "volumes": [
            {
                "name": "第一卷",
                "chapters": [
                    {"number": 1, "title": "第一章", "summary": "甲"},
                    {"number": 5, "title": "第五章", "summary": "乙"},
                ],
            }
        ]
    }

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="显式章号", genre="xuanhuan"))
        outline = Outline(novel_id=novel.id, outline_type="complete", structure=structure)
        session.add(outline)
        await session.flush()
        chapter = Chapter(novel_id=novel.id, chapter_number=5, title="第五章", status="outline")
        session.add(chapter)
        await session.commit()

    async with SessionLocal() as session:
        ch = await session.get(Chapter, chapter.id)
        o = await session.get(Outline, outline.id)
        text = await get_chapter_outline(session, ch, o)
    assert "乙" in text
    assert "甲" not in text


def test_format_outline_is_readable_chinese_not_json() -> None:
    """整体大纲进 prompt 时必须是**可读中文**，不是英文 JSON（需求1/需求7）。"""
    from src.models.outline import Outline

    o = Outline(
        id=1,
        novel_id=1,
        outline_type="complete",
        structure={
            "volumes": [
                {
                    "name": "第一卷 觉醒",
                    "summary": "主角觉醒血脉。",
                    "chapters": [{"title": "第一章 废柴", "summary": "被逐出宗门"}],
                }
            ],
            "overall_theme": "逆袭",
        },
    )
    out = format_outline(o)
    assert "第一卷 觉醒" in out
    assert "被逐出宗门" in out
    # 不能出现 JSON 结构
    assert '"volumes"' not in out
    assert "{" not in out


@pytest.mark.asyncio
async def test_get_chapter_outline_fallback_to_field(db_initialized: Path) -> None:
    """outline 为空 / structure 里没匹配项时，用 chapter.outline 字段。"""
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试2", genre="xuanhuan"))
        # outline=None
        chapter = Chapter(
            novel_id=novel.id,
            chapter_number=1,
            title="第一章",
            outline="这是 chapter.outline 字段的内容",
            status="outline",
        )
        session.add(chapter)
        await session.commit()

    async with SessionLocal() as session:
        ch = await session.get(Chapter, chapter.id)
        text = await get_chapter_outline(session, ch, None)
    assert "chapter.outline 字段的内容" in text


# ===== get_version_tail / get_previous_tail / get_recent_summaries =====


@pytest.mark.asyncio
async def test_get_version_tail_short_content(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.models.chapter import Chapter, ChapterVersion
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试3", genre="xuanhuan"))
        chapter = Chapter(novel_id=novel.id, chapter_number=1, status="drafting", word_count=0)
        session.add(chapter)
        await session.flush()
        ver = ChapterVersion(
            chapter_id=chapter.id, content="短", trigger="user_create", word_count=1
        )
        session.add(ver)
        await session.flush()
        chapter.current_version_id = ver.id
        await session.commit()

    async with SessionLocal() as session:
        ch = await session.get(Chapter, chapter.id)
        tail = await get_version_tail(session, ch, chars=1500)
    assert tail == "短"


@pytest.mark.asyncio
async def test_get_version_tail_truncates(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.models.chapter import Chapter, ChapterVersion
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    content = "A" * 2000
    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试4", genre="xuanhuan"))
        chapter = Chapter(novel_id=novel.id, chapter_number=1, status="drafting")
        session.add(chapter)
        await session.flush()
        ver = ChapterVersion(
            chapter_id=chapter.id, content=content, trigger="user_create", word_count=2000
        )
        session.add(ver)
        await session.flush()
        chapter.current_version_id = ver.id
        await session.commit()

    async with SessionLocal() as session:
        ch = await session.get(Chapter, chapter.id)
        tail = await get_version_tail(session, ch, chars=500)
    assert len(tail) == 500
    assert tail == "A" * 500


@pytest.mark.asyncio
async def test_get_previous_tail_chapter_0(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        assert (
            await get_previous_tail(session, novel_id=1, before_chapter_number=0) == "（无上一章）"
        )
        assert (
            await get_previous_tail(session, novel_id=1, before_chapter_number=-5) == "（无上一章）"
        )


@pytest.mark.asyncio
async def test_get_previous_tail_no_content(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试5", genre="xuanhuan"))
        ch1 = Chapter(novel_id=novel.id, chapter_number=1, status="outline")
        session.add(ch1)
        await session.commit()

    async with SessionLocal() as session:
        tail = await get_previous_tail(session, novel_id=novel.id, before_chapter_number=1)
    assert tail == "（上一章暂无内容）"


@pytest.mark.asyncio
async def test_get_recent_summaries_empty(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试6", genre="xuanhuan"))
        await session.commit()

    async with SessionLocal() as session:
        s = await get_recent_summaries(session, novel_id=novel.id, n=3)
    assert "暂无历史章节" in s


# ===== LLMError sanity（确保导入路径稳定）=====


def test_llm_error_importable() -> None:
    # 不真正触发，只是 sanity check
    assert LLMError is not None
