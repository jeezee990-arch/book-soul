"""Inspiration detail 端点测试（Phase 6.1）。"""

from __future__ import annotations

from pathlib import Path

import pytest


async def _make_novel_with_inspiration(
    db_initialized: Path,
    *,
    inspiration_type: str = "keyword",
    content: dict | None = None,
    with_novel: bool = True,
    tags: list[str] | None = None,
):
    """最小数据集：novel + character + outline + chapter + inspiration。"""
    from src.db import SessionLocal
    from src.models.character import Character
    from src.models.chapter import Chapter, ChapterVersion
    from src.models.outline import Outline
    from src.services.novel_service import NovelService
    from src.services.inspiration_service import InspirationService
    from src.schemas.novel import NovelCreate
    from src.schemas.inspiration import InspirationCreate

    content = content or {"words": ["修仙", "逆袭"]}
    tags = tags or ["热门"]
    async with SessionLocal() as session:
        novel = None
        if with_novel:
            novel = await NovelService(session).create(
                NovelCreate(name="测试小说", genre="xiuxian")
            )
            ch = Chapter(novel_id=novel.id, chapter_number=1, title="第一章", status="drafting")
            session.add(ch)
            await session.flush()
            ver = ChapterVersion(
                chapter_id=ch.id, content="韩立出生了。", trigger="user_create", word_count=7
            )
            session.add(ver)
            await session.flush()
            ch.current_version_id = ver.id
            char = Character(
                novel_id=novel.id, name="韩立", role="主角", personality="谨慎"
            )
            session.add(char)
            session.add(Outline(novel_id=novel.id, outline_type="complete", structure={"chapters": []}))
            await session.commit()
            novel_id = novel.id
        else:
            novel_id = None

        ins = await InspirationService(session).create(
            InspirationCreate(
                novel_id=novel_id,
                type=inspiration_type,
                content=content,
                tags=tags,
                source="手动测试",
            )
        )
        return ins.id, novel_id


@pytest.mark.asyncio
async def test_detail_with_novel(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient
    from src.main import app

    ins_id, novel_id = await _make_novel_with_inspiration(db_initialized)
    client = TestClient(app)
    resp = client.get(f"/inspirations/{ins_id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == ins_id
    assert body["type"] == "keyword"
    assert body["content"]["words"] == ["修仙", "逆袭"]
    assert body["tags"] == ["热门"]
    assert body["novel"] is not None
    assert body["novel"]["id"] == novel_id
    assert body["novel"]["name"] == "测试小说"
    assert len(body["novel"]["characters"]) == 1
    assert body["novel"]["characters"][0]["name"] == "韩立"
    assert len(body["novel"]["chapters"]) == 1
    assert body["novel"]["chapters"][0]["title"] == "第一章"
    assert body["novel"]["outline_structure"] is not None


@pytest.mark.asyncio
async def test_detail_without_novel(db_initialized: Path) -> None:
    """通用灵感（novel_id=None）：返回 novel=null。"""
    from fastapi.testclient import TestClient
    from src.main import app

    ins_id, _ = await _make_novel_with_inspiration(db_initialized, with_novel=False)
    client = TestClient(app)
    resp = client.get(f"/inspirations/{ins_id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["novel_id"] is None
    assert body["novel"] is None


@pytest.mark.asyncio
async def test_detail_plot_type(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient
    from src.main import app

    ins_id, _ = await _make_novel_with_inspiration(
        db_initialized,
        inspiration_type="plot",
        content={"summary": "主角逆袭", "beats": ["开端", "高潮"]},
    )
    client = TestClient(app)
    resp = client.get(f"/inspirations/{ins_id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "plot"
    assert body["content"]["summary"] == "主角逆袭"
    assert body["content"]["beats"] == ["开端", "高潮"]


@pytest.mark.asyncio
async def test_detail_404(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)
    resp = client.get("/inspirations/9999/detail")
    assert resp.status_code == 404
