"""NovelExportService 单元测试（Phase 3.8）。

覆盖：
- 完整导出：novel + complete outline + characters → md 包含所有关键段
- 完整导出：novel + freedom outline
- novel 不存在 → NovelNotFoundError
- 大纲缺失 → "（无）"
- 人物卡缺失 → "（无）"
- 退场人物标"（退场）"
- 空字段不渲染
- _safe_filename 去 Windows 非法字符
- 文件名回退
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.schemas.character import CharacterCreate
from src.schemas.novel import NovelCreate
from src.schemas.outline import OutlineCreate
from src.services.character_service import NovelNotFoundError
from src.services.export_service import NovelExportService, chapter_heading
from src.services.novel_service import NovelService
from src.services.outline_service import OutlineService

# ===== helpers =====


async def _create_novel(session, name: str = "测试作品", genre: str = "修仙") -> int:
    svc = NovelService(session)
    n = await svc.create(NovelCreate(name=name, genre=genre, description="test desc"))
    return n.id


async def _create_outline_complete(session, novel_id: int) -> int:
    svc = OutlineService(session)
    o = await svc.create(
        OutlineCreate(
            novel_id=novel_id,
            outline_type="complete",
            structure={
                "overall_theme": "凡人修仙",
                "volumes": [
                    {
                        "name": "第一卷 觉醒",
                        "summary": "主角觉醒血脉。",
                        "chapters": [
                            {
                                "title": "第一章 变故",
                                "summary": "家族被灭。",
                                "key_events": ["夜袭", "逃生"],
                            },
                        ],
                    },
                ],
            },
        )
    )
    return o.id


async def _create_outline_freedom(session, novel_id: int) -> int:
    svc = OutlineService(session)
    o = await svc.create(
        OutlineCreate(
            novel_id=novel_id,
            outline_type="freedom",
            structure={
                "summary": "一个凡人逆袭的故事。",
                "themes": ["逆天改命", "长生"],
                "key_beats": ["开端：测试", "高潮：突破"],
            },
        )
    )
    return o.id


async def _create_character(
    session,
    novel_id: int,
    name: str = "韩立",
    role: str = "主角",
    is_active: bool = True,
) -> int:
    svc = __import__(
        "src.services.character_service", fromlist=["CharacterService"]
    ).CharacterService(session)
    c = await svc.create(
        CharacterCreate(
            novel_id=novel_id,
            name=name,
            role=role,
            basic_info="凡人出身",
            personality="谨慎",
            habits="带法器",
            thinking="留后路",
            relationships="道侣：南宫婉",
            is_active=is_active,
        )
    )
    return c.id


# ===== 主路径 =====


@pytest.mark.asyncio
async def test_export_full_complete(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session, name="凡人修仙传")
        await _create_outline_complete(session, nid)
        await _create_character(session, nid, name="韩立")
        await _create_character(session, nid, name="墨大夫", role="反派")

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "# 凡人修仙传" in md
    assert "题材：修仙" in md
    assert "## 大纲" in md
    assert "**全篇主题**：凡人修仙" in md
    assert "第一卷 觉醒" in md
    assert "第一章 变故" in md
    assert "夜袭、逃生" in md
    assert "## 人物卡" in md
    assert "### 韩立（主角）" in md
    assert "### 墨大夫（反派）" in md
    assert "**基本信息**：凡人出身" in md
    assert "**性格**：谨慎" in md
    assert "**人物关系**：道侣：南宫婉" in md


@pytest.mark.asyncio
async def test_export_freedom_outline(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session)
        await _create_outline_freedom(session, nid)

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "## 大纲" in md
    assert "主题" in md
    assert "逆天改命、长生" in md
    assert "梗概" in md
    assert "凡人逆袭" in md
    assert "关键节拍" in md
    assert "1. 开端：测试" in md


@pytest.mark.asyncio
async def test_export_no_outline(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session)
        await _create_character(session, nid)

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "## 大纲" in md
    assert "（无）" in md
    assert "## 人物卡" in md
    assert "韩立" in md


@pytest.mark.asyncio
async def test_export_no_characters(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session)
        await _create_outline_complete(session, nid)

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "## 人物卡" in md
    assert "（无）" in md
    assert "## 大纲" in md
    assert "第一卷 觉醒" in md


@pytest.mark.asyncio
async def test_export_novel_not_found(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        with pytest.raises(NovelNotFoundError):
            await NovelExportService(session).export_markdown(999999)


@pytest.mark.asyncio
async def test_export_inactive_character_marked(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session)
        await _create_character(session, nid, name="退场人", is_active=False)

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "退场人" in md
    assert "（退场）" in md


@pytest.mark.asyncio
async def test_export_empty_fields_not_rendered(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session)
        svc = __import__(
            "src.services.character_service", fromlist=["CharacterService"]
        ).CharacterService(session)
        await svc.create(
            CharacterCreate(
                novel_id=nid,
                name="空字段人",
                role="其他",
                # 所有可选字段留空
            )
        )

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "### 空字段人（其他）" in md
    # 没有基本信息 → 不出现 "**基本信息**："
    assert "**基本信息**" not in md
    assert "**性格**" not in md


@pytest.mark.asyncio
async def test_export_status_translated(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        nid = await _create_novel(session)

    # 改 status
    async with SessionLocal() as session:
        svc = NovelService(session)
        await svc.update(
            nid,
            __import__("src.schemas.novel", fromlist=["NovelUpdate"]).NovelUpdate(status="writing"),
        )

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(nid)

    assert "状态：创作中" in md


@pytest.mark.asyncio
async def test_export_no_description(db_initialized: Path) -> None:
    """description 留空 → 显示'（无）'。"""
    from src.db import SessionLocal

    async with SessionLocal() as session:
        svc = NovelService(session)
        n = await svc.create(NovelCreate(name="x", genre="y"))

    async with SessionLocal() as session:
        md = await NovelExportService(session).export_markdown(n.id)

    assert "简介：（无）" in md


# ===== _safe_filename =====


def test_safe_filename_basic() -> None:
    from src.api.novels import _safe_filename

    assert _safe_filename("凡人修仙传") == "凡人修仙传"
    assert _safe_filename("book 1") == "book 1"


def test_safe_filename_strip_illegal() -> None:
    from src.api.novels import _safe_filename

    # Windows 非法字符
    assert "/" not in _safe_filename("a/b")
    assert "\\" not in _safe_filename("a\\b")
    assert ":" not in _safe_filename("a:b")
    assert "*" not in _safe_filename("a*b")
    assert "?" not in _safe_filename("a?b")
    assert '"' not in _safe_filename('a"b')
    assert "<" not in _safe_filename("a<b")
    assert ">" not in _safe_filename("a>b")
    assert "|" not in _safe_filename("a|b")


def test_safe_filename_empty_fallback() -> None:
    from src.api.novels import _safe_filename

    assert _safe_filename("") == "untitled"
    assert _safe_filename("   ") == "untitled"


# ===== 章节标题去重（2026-10-30）=====


def test_chapter_heading_avoids_duplicate_prefix() -> None:
    """章节标题本身带了「第 N 章」时，不能再叠一层前缀。

    旧写法固定拼 ``第 {n} 章 · {title}``，用户自己把章节命名成
    「第一章 灰光验凡根」时就会导出成「第 1 章 · 第一章 灰光验凡根」。
    """
    assert chapter_heading(1, "第一章 灰光验凡根") == "第一章 灰光验凡根"
    assert chapter_heading(12, "第十二章 归途") == "第十二章 归途"
    assert chapter_heading(3, "第三节 夜谈") == "第三节 夜谈"
    # 没有章节前缀 → 照常加
    assert chapter_heading(1, "开篇") == "第 1 章 · 开篇"
    assert chapter_heading(7, "雨夜") == "第 7 章 · 雨夜"
    # 缺标题 / 空白标题
    assert chapter_heading(3, None) == "第 3 章 · （未命名）"
    assert chapter_heading(3, "   ") == "第 3 章 · （未命名）"
