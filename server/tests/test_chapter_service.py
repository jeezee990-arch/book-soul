"""测试 Chapter 业务服务（Phase 1.3）。

覆盖：
- create（无 content / 有 content）
- get / list / update / delete
- update_content：版本化 + parent 链 + 字数
- list_versions / get_version
- chapter_number 唯一性
- 错误路径
- API 端点
"""

from __future__ import annotations

import pytest

# ===== helpers =====


async def _create_novel(db_initialized, **kwargs):
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    data = NovelCreate(name=kwargs.pop("name", "测试小说"), genre=kwargs.pop("genre", "xuanhuan"))
    async with get_session() as session:
        svc = NovelService(session)
        novel = await svc.create(data)
    return novel.id


# ===== Service 单元测试 =====


@pytest.mark.asyncio
async def test_create_chapter_minimal(db_initialized):
    """只填必填字段。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        data = ChapterCreate(novel_id=nid, chapter_number=1, title="第一章")
        chapter = await svc.create(data)

    assert chapter.id is not None
    assert chapter.novel_id == nid
    assert chapter.chapter_number == 1
    assert chapter.title == "第一章"
    assert chapter.status == "outline"
    assert chapter.word_count == 0
    assert chapter.current_version_id is None  # 没带 content


@pytest.mark.asyncio
async def test_create_chapter_with_content_creates_initial_version(db_initialized):
    """带 content 应自动写 user_create 版本。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    content = "七月的青牛镇，烈日当空。"
    async with get_session() as session:
        svc = ChapterService(session)
        data = ChapterCreate(novel_id=nid, chapter_number=1, title="第一章", content=content)
        chapter = await svc.create(data)

    assert chapter.current_version_id is not None
    assert chapter.word_count == len(content)
    assert chapter.status == "drafting"  # 写完自动 outline → drafting

    async with get_session() as session:
        svc = ChapterService(session)
        versions = await svc.list_versions(chapter.id)

    assert len(versions) == 1
    v = versions[0]
    assert v.trigger == "user_create"
    assert v.parent_version_id is None
    assert v.content == content
    assert v.word_count == len(content)


@pytest.mark.asyncio
async def test_create_chapter_rejects_invalid_status(db_initialized):
    """非法 status 抛 ValidationError。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import ChapterService, ChapterValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        data = ChapterCreate(novel_id=nid, chapter_number=1, status="random")
        with pytest.raises(ChapterValidationError, match="Invalid status"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_chapter_rejects_missing_novel(db_initialized):
    """novel_id 不存在抛 NovelNotFoundError。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import ChapterService, NovelNotFoundError

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(NovelNotFoundError):
            await svc.create(ChapterCreate(novel_id=9999, chapter_number=1))


@pytest.mark.asyncio
async def test_create_chapter_rejects_duplicate_chapter_number(db_initialized):
    """同一作品内 chapter_number 不能重复。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import (
        ChapterNumberConflictError,
        ChapterService,
    )

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        await svc.create(ChapterCreate(novel_id=nid, chapter_number=1))

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(ChapterNumberConflictError):
            await svc.create(ChapterCreate(novel_id=nid, chapter_number=1))


@pytest.mark.asyncio
async def test_get_chapter_returns(db_initialized):
    """get 已存在返回。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1))

    async with get_session() as session:
        svc = ChapterService(session)
        fetched = await svc.get(c.id)
    assert fetched.id == c.id


@pytest.mark.asyncio
async def test_get_chapter_404(db_initialized):
    """get 不存在抛 NotFound。"""
    from src.db import get_session
    from src.services.chapter_service import ChapterNotFoundError, ChapterService

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(ChapterNotFoundError):
            await svc.get(9999)


@pytest.mark.asyncio
async def test_list_all_filters_and_ordering(db_initialized):
    """按 novel_id / status 过滤，按 chapter_number 升序。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate
    from src.services.chapter_service import ChapterService

    n1 = await _create_novel(db_initialized, name="n1")
    n2 = await _create_novel(db_initialized, name="n2")
    async with get_session() as session:
        svc = ChapterService(session)
        await svc.create(ChapterCreate(novel_id=n1, chapter_number=3))
        await svc.create(ChapterCreate(novel_id=n1, chapter_number=1))
        await svc.create(ChapterCreate(novel_id=n1, chapter_number=2, status="drafting"))
        await svc.create(ChapterCreate(novel_id=n2, chapter_number=1))

    async with get_session() as session:
        svc = ChapterService(session)
        n1_all = await svc.list_all(novel_id=n1)
        n1_drafting = await svc.list_all(novel_id=n1, status="drafting")

    # 应按 chapter_number 升序
    assert [c.chapter_number for c in n1_all] == [1, 2, 3]
    assert [c.chapter_number for c in n1_drafting] == [2]


@pytest.mark.asyncio
async def test_update_chapter_partial(db_initialized):
    """update 只改指定字段；不改正文。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate, ChapterUpdate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1, title="原"))

    async with get_session() as session:
        svc = ChapterService(session)
        u = await svc.update(c.id, ChapterUpdate(title="新", status="drafting"))

    assert u.title == "新"
    assert u.status == "drafting"
    assert u.chapter_number == 1  # 未改


@pytest.mark.asyncio
async def test_update_chapter_number_checks_uniqueness(db_initialized):
    """update 改 chapter_number 时校验唯一性。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterCreate, ChapterUpdate
    from src.services.chapter_service import (
        ChapterNumberConflictError,
        ChapterService,
    )

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        await svc.create(ChapterCreate(novel_id=nid, chapter_number=1))
        c2 = await svc.create(ChapterCreate(novel_id=nid, chapter_number=2))

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(ChapterNumberConflictError):
            await svc.update(c2.id, ChapterUpdate(chapter_number=1))


@pytest.mark.asyncio
async def test_update_chapter_does_not_create_version(db_initialized):
    """update 元数据不应创建新版本。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterContentUpdate, ChapterCreate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1, content="initial"))

    async with get_session() as session:
        svc = ChapterService(session)
        await svc.update_content(
            c.id, ChapterContentUpdate(content="new content", trigger="user_edit")
        )
        versions = await svc.list_versions(c.id)

    assert len(versions) == 2  # initial + 1 edit
    # update_content 才创建版本；纯 update 不创建
    async with get_session() as session:
        svc = ChapterService(session)
        from src.schemas.chapter import ChapterUpdate

        await svc.update(c.id, ChapterUpdate(title="changed"))
        versions2 = await svc.list_versions(c.id)
    assert len(versions2) == 2  # 仍 2 个


@pytest.mark.asyncio
async def test_update_content_creates_version_with_parent(db_initialized):
    """update_content 写新版本，parent 指向当前版本。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterContentUpdate, ChapterCreate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1, content="v1"))
        original_vid = c.current_version_id

    async with get_session() as session:
        svc = ChapterService(session)
        v2 = await svc.update_content(
            c.id,
            ChapterContentUpdate(content="v2 - new content", trigger="user_edit", prompt=None),
        )
        c2 = await svc.get(c.id)

    assert v2.parent_version_id == original_vid
    assert v2.trigger == "user_edit"
    assert v2.word_count == len("v2 - new content")
    assert c2.current_version_id == v2.id
    assert c2.word_count == v2.word_count


@pytest.mark.asyncio
async def test_update_content_chains_versions(db_initialized):
    """多次 update_content 应链接成版本链。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterContentUpdate, ChapterCreate
    from src.services.chapter_service import ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1, content="v1"))

    async with get_session() as session:
        svc = ChapterService(session)
        v2 = await svc.update_content(c.id, ChapterContentUpdate(content="v2", trigger="rewrite"))
        v3 = await svc.update_content(
            c.id, ChapterContentUpdate(content="v3 - llm", trigger="llm_generate")
        )

    async with get_session() as session:
        svc = ChapterService(session)
        versions = await svc.list_versions(c.id)
        c_final = await svc.get(c.id)

    # list_versions 按时间倒序：v3, v2, v1
    assert [v.id for v in versions] == [v3.id, v2.id, c.current_version_id]
    # parent 链
    assert v3.parent_version_id == v2.id
    assert v2.parent_version_id == c.current_version_id  # 最初的初始版本
    # current 应是 v3
    assert c_final.current_version_id == v3.id
    assert c_final.word_count == len("v3 - llm")


@pytest.mark.asyncio
async def test_update_content_rejects_invalid_trigger(db_initialized):
    """非法 trigger 抛 ValidationError。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterContentUpdate, ChapterCreate
    from src.services.chapter_service import ChapterService, ChapterValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1))

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(ChapterValidationError, match="Invalid trigger"):
            await svc.update_content(c.id, ChapterContentUpdate(content="x", trigger="random"))


@pytest.mark.asyncio
async def test_update_content_404(db_initialized):
    """update_content 不存在章节抛 NotFound。"""
    from src.db import get_session
    from src.schemas.chapter import ChapterContentUpdate
    from src.services.chapter_service import ChapterNotFoundError, ChapterService

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(ChapterNotFoundError):
            await svc.update_content(9999, ChapterContentUpdate(content="x"))


@pytest.mark.asyncio
async def test_delete_chapter_cascades_versions(db_initialized):
    """delete 后 versions 也应被清。"""
    from sqlalchemy import select

    from src.db import get_session
    from src.models.chapter import ChapterVersion
    from src.schemas.chapter import ChapterContentUpdate, ChapterCreate
    from src.services.chapter_service import ChapterNotFoundError, ChapterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = ChapterService(session)
        c = await svc.create(ChapterCreate(novel_id=nid, chapter_number=1, content="x"))
        await svc.update_content(c.id, ChapterContentUpdate(content="y", trigger="user_edit"))

    async with get_session() as session:
        svc = ChapterService(session)
        await svc.delete(c.id)

    async with get_session() as session:
        svc = ChapterService(session)
        with pytest.raises(ChapterNotFoundError):
            await svc.get(c.id)

    async with get_session() as session:
        stmt = select(ChapterVersion).where(ChapterVersion.chapter_id == c.id)
        result = await session.execute(stmt)
        assert list(result.scalars()) == []


@pytest.mark.asyncio
async def test_delete_idempotent(db_initialized):
    """delete 不存在不报错。"""
    from src.db import get_session
    from src.services.chapter_service import ChapterService

    async with get_session() as session:
        svc = ChapterService(session)
        await svc.delete(9999)


# ===== API 端点测试 =====


@pytest.mark.asyncio
async def test_api_create_chapter(db_initialized):
    """POST /novels/{nid}/chapters 应 201 + 资源。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/novels/{nid}/chapters",
            json={"novel_id": nid, "chapter_number": 1, "title": "第一章"},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == "第一章"
    assert data["chapter_number"] == 1


@pytest.mark.asyncio
async def test_api_create_chapter_path_body_mismatch(db_initialized):
    """路径和 body novel_id 不一致应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/novels/{nid}/chapters",
            json={"novel_id": nid + 1, "chapter_number": 1},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_list_chapters_by_novel(db_initialized):
    """GET /novels/{nid}/chapters 应只返回该作品。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    n1 = await _create_novel(db_initialized, name="n1")
    n2 = await _create_novel(db_initialized, name="n2")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/novels/{n1}/chapters",
            json={"novel_id": n1, "chapter_number": 1, "title": "A"},
        )
        await client.post(
            f"/novels/{n2}/chapters",
            json={"novel_id": n2, "chapter_number": 1, "title": "B"},
        )
        resp = await client.get(f"/novels/{n1}/chapters")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "A"


@pytest.mark.asyncio
async def test_api_get_chapter_404(db_initialized):
    """GET /chapters/9999 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/chapters/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_content_creates_version(db_initialized):
    """POST /chapters/{id}/content 应写新版本。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(
                f"/novels/{nid}/chapters",
                json={
                    "novel_id": nid,
                    "chapter_number": 1,
                    "title": "x",
                    "content": "v1 content",
                },
            )
        ).json()
        cid = c["id"]
        original_vid = c["current_version_id"]

        resp = await client.post(
            f"/chapters/{cid}/content",
            json={"content": "v2 - rewritten", "trigger": "rewrite"},
        )
    assert resp.status_code == 201, resp.text
    v = resp.json()
    assert v["parent_version_id"] == original_vid
    assert v["trigger"] == "rewrite"
    assert v["content"] == "v2 - rewritten"

    # 查 chapter 应能看到 word_count 变了
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c2 = (await client.get(f"/chapters/{cid}")).json()
    assert c2["word_count"] == len("v2 - rewritten")


@pytest.mark.asyncio
async def test_api_list_versions(db_initialized):
    """GET /chapters/{id}/versions 应按时间倒序。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(
                f"/novels/{nid}/chapters",
                json={"novel_id": nid, "chapter_number": 1, "content": "v1"},
            )
        ).json()
        cid = c["id"]
        await client.post(
            f"/chapters/{cid}/content",
            json={"content": "v2", "trigger": "user_edit"},
        )
        await client.post(
            f"/chapters/{cid}/content",
            json={"content": "v3", "trigger": "llm_generate"},
        )
        resp = await client.get(f"/chapters/{cid}/versions")
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 3
    assert versions[0]["trigger"] == "llm_generate"
    assert versions[1]["trigger"] == "user_edit"
    assert versions[2]["trigger"] == "user_create"


@pytest.mark.asyncio
async def test_api_get_version(db_initialized):
    """GET /chapters/{id}/versions/{vid} 应返回单个版本。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(
                f"/novels/{nid}/chapters",
                json={"novel_id": nid, "chapter_number": 1, "content": "v1"},
            )
        ).json()
        cid = c["id"]
        vid = c["current_version_id"]

        resp = await client.get(f"/chapters/{cid}/versions/{vid}")
    assert resp.status_code == 200
    v = resp.json()
    assert v["id"] == vid
    assert v["content"] == "v1"


@pytest.mark.asyncio
async def test_api_delete_chapter(db_initialized):
    """DELETE /chapters/{id} 应 204；再 GET 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(
                f"/novels/{nid}/chapters",
                json={"novel_id": nid, "chapter_number": 1},
            )
        ).json()
        cid = c["id"]

        del_resp = await client.delete(f"/chapters/{cid}")
    assert del_resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(f"/chapters/{cid}")
    assert get_resp.status_code == 404
