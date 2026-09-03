"""测试 Inspiration 业务服务（Phase 1.5）。

覆盖：
- create：5 种 type + 通用 vs 作品
- get / list（novel_id / type / tag 过滤）
- update（部分更新 + 改 type 触发 content 重新校验）
- delete 幂等
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


KW_CONTENT = {"words": ["修仙", "废柴", "逆袭"]}
PLOT_CONTENT = {"summary": "主角身世之谜", "beats": ["幼年目睹灭门", "多年后追查"]}
SNIPPET_CONTENT = {"text": "剑气如虹，一剑破万法。"}
IMAGE_CONTENT = {"description": "云海之巅，一人独立"}
NOTE_CONTENT = {"text": "地铁上想到的灵感"}


# ===== Service 单元测试 =====


@pytest.mark.asyncio
async def test_create_keyword_inspiration_no_novel(db_initialized):
    """通用灵感（novel_id=None） + keyword type。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        data = InspirationCreate(type="keyword", content=KW_CONTENT, tags=["热门"])
        inspiration = await svc.create(data)

    assert inspiration.id is not None
    assert inspiration.novel_id is None
    assert inspiration.type == "keyword"
    assert inspiration.content == KW_CONTENT
    assert inspiration.tags == ["热门"]


@pytest.mark.asyncio
async def test_create_all_types_with_novel(db_initialized):
    """5 种 type 都能创建。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    nid = await _create_novel(db_initialized)
    contents = [
        ("keyword", KW_CONTENT),
        ("plot", PLOT_CONTENT),
        ("snippet", SNIPPET_CONTENT),
        ("image", IMAGE_CONTENT),
        ("note", NOTE_CONTENT),
    ]
    async with get_session() as session:
        svc = InspirationService(session)
        ids = []
        for t, c in contents:
            data = InspirationCreate(novel_id=nid, type=t, content=c, source=f"src-{t}")
            ins = await svc.create(data)
            ids.append(ins.id)
            assert ins.type == t
            assert ins.content == c
            assert ins.source == f"src-{t}"

    # 5 个都创建成功
    assert len(set(ids)) == 5


@pytest.mark.asyncio
async def test_create_rejects_invalid_type(db_initialized):
    """非法 type 由 service 校验抛 ValidationError。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService, InspirationValidationError

    async with get_session() as session:
        svc = InspirationService(session)
        data = InspirationCreate(type="random", content=NOTE_CONTENT)
        with pytest.raises(InspirationValidationError, match="Invalid type"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_rejects_mismatched_content(db_initialized):
    """type=keyword 但 content 是 note 形状应被 service 拒。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService, InspirationValidationError

    async with get_session() as session:
        svc = InspirationService(session)
        data = InspirationCreate(type="keyword", content=NOTE_CONTENT)
        with pytest.raises(InspirationValidationError, match="Invalid content"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_rejects_missing_novel(db_initialized):
    """novel_id 不存在应抛 NovelNotFoundError。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService, NovelNotFoundError

    async with get_session() as session:
        svc = InspirationService(session)
        data = InspirationCreate(novel_id=9999, type="note", content=NOTE_CONTENT)
        with pytest.raises(NovelNotFoundError):
            await svc.create(data)


@pytest.mark.asyncio
async def test_get_inspiration_returns(db_initialized):
    """get 已存在返回。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    async with get_session() as session:
        svc = InspirationService(session)
        fetched = await svc.get(c.id)
    assert fetched.id == c.id


@pytest.mark.asyncio
async def test_get_inspiration_404(db_initialized):
    """get 不存在抛 NotFound。"""
    from src.db import get_session
    from src.services.inspiration_service import InspirationNotFoundError, InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        with pytest.raises(InspirationNotFoundError):
            await svc.get(9999)


@pytest.mark.asyncio
async def test_list_filters(db_initialized):
    """按 novel_id / type / tag 过滤。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = InspirationService(session)
        # 通用 1 条 + 作品 3 条（2 关键字 + 1 片段）
        await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))
        await svc.create(
            InspirationCreate(
                novel_id=nid, type="keyword", content=KW_CONTENT, tags=["热门", "修仙"]
            )
        )
        await svc.create(
            InspirationCreate(
                novel_id=nid, type="keyword", content={"words": ["另一个"]}, tags=["修仙"]
            )
        )
        await svc.create(InspirationCreate(novel_id=nid, type="snippet", content=SNIPPET_CONTENT))

    async with get_session() as session:
        svc = InspirationService(session)
        all_ = await svc.list_all()
        n1_only = await svc.list_all(novel_id=nid)
        n1_kw = await svc.list_all(novel_id=nid, inspiration_type="keyword")
        tagged = await svc.list_all(tag="热门")
        # novel_id=None 语义：不过滤（返回所有，包括通用和作品）
        no_filter = await svc.list_all(novel_id=None)
        # 作品灵感数（查指定 novel_id）

    assert len(all_) == 4
    assert len(no_filter) == 4  # novel_id=None 不过滤
    assert len(n1_only) == 3
    assert len(n1_kw) == 2
    assert len(tagged) == 1  # 含 "热门" 的 1 条


@pytest.mark.asyncio
async def test_update_inspiration_partial(db_initialized):
    """update 只改指定字段。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate, InspirationUpdate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT, source="src1"))

    async with get_session() as session:
        svc = InspirationService(session)
        u = await svc.update(c.id, InspirationUpdate(tags=["新tag"], content={"text": "新内容"}))

    assert u.tags == ["新tag"]
    assert u.content == {"text": "新内容"}
    assert u.source == "src1"  # 未改
    assert u.type == "note"  # 未改


@pytest.mark.asyncio
async def test_update_type_triggers_content_revalidation(db_initialized):
    """改 type 时如果新 content 不匹配新 type 应被拒。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate, InspirationUpdate
    from src.services.inspiration_service import InspirationService, InspirationValidationError

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    # 想改成 keyword 但 content 还是 note 形状 → 拒
    async with get_session() as session:
        svc = InspirationService(session)
        with pytest.raises(InspirationValidationError, match="Invalid content"):
            await svc.update(
                c.id,
                InspirationUpdate(type="keyword", content={"text": "wrong shape"}),
            )


@pytest.mark.asyncio
async def test_update_novel_id_404(db_initialized):
    """update 改 novel_id 为不存在应 404。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate, InspirationUpdate
    from src.services.inspiration_service import InspirationService, NovelNotFoundError

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    async with get_session() as session:
        svc = InspirationService(session)
        with pytest.raises(NovelNotFoundError):
            await svc.update(c.id, InspirationUpdate(novel_id=9999))


@pytest.mark.asyncio
async def test_delete_inspiration(db_initialized):
    """delete 后 get NotFound。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import (
        InspirationNotFoundError,
        InspirationService,
    )

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    async with get_session() as session:
        svc = InspirationService(session)
        await svc.delete(c.id)

    async with get_session() as session:
        svc = InspirationService(session)
        with pytest.raises(InspirationNotFoundError):
            await svc.get(c.id)


@pytest.mark.asyncio
async def test_delete_idempotent(db_initialized):
    """delete 不存在不报错。"""
    from src.db import get_session
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        await svc.delete(9999)


# ===== API 端点测试 =====


@pytest.mark.asyncio
async def test_api_create_inspiration_no_novel(db_initialized):
    """POST /inspirations 不带 novel_id 应 201。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/inspirations",
            json={"type": "keyword", "content": KW_CONTENT, "tags": ["热门"]},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["novel_id"] is None
    assert data["type"] == "keyword"
    assert data["content"] == KW_CONTENT


@pytest.mark.asyncio
async def test_api_create_inspiration_with_novel(db_initialized):
    """带 novel_id 应 201。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/inspirations",
            json={
                "novel_id": nid,
                "type": "plot",
                "content": PLOT_CONTENT,
                "source": "读 XX 时想到",
            },
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["novel_id"] == nid
    assert data["source"] == "读 XX 时想到"


@pytest.mark.asyncio
async def test_api_create_422_on_bad_content(db_initialized):
    """content 形状错配应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # type=keyword 但 content 是 note 形状
        resp = await client.post(
            "/inspirations",
            json={"type": "keyword", "content": {"text": "wrong"}},
        )
    assert resp.status_code == 422
    assert "Invalid content" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_create_404_on_missing_novel(db_initialized):
    """novel_id 不存在应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/inspirations",
            json={"novel_id": 9999, "type": "note", "content": NOTE_CONTENT},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_list_inspirations(db_initialized):
    """GET /inspirations 默认按 created_at 倒序。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        await client.post("/inspirations", json={"type": "keyword", "content": KW_CONTENT})
        resp = await client.get("/inspirations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_api_list_filter_by_type(db_initialized):
    """按 type 过滤。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        await client.post("/inspirations", json={"type": "keyword", "content": KW_CONTENT})
        resp = await client.get("/inspirations", params={"type": "keyword"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "keyword"


@pytest.mark.asyncio
async def test_api_get_inspiration_404(db_initialized):
    """GET /inspirations/9999 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/inspirations/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_inspiration(db_initialized):
    """PATCH 改 tags 应成功。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        ).json()
        cid = c["id"]

        resp = await client.patch(
            f"/inspirations/{cid}",
            json={"tags": ["新tag1", "新tag2"]},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tags"] == ["新tag1", "新tag2"]


@pytest.mark.asyncio
async def test_api_delete_inspiration(db_initialized):
    """DELETE 应 204；再 GET 应 404；再 DELETE 应 204（幂等）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        ).json()
        cid = c["id"]

        del1 = await client.delete(f"/inspirations/{cid}")
    assert del1.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(f"/inspirations/{cid}")
        del2 = await client.delete(f"/inspirations/{cid}")
    assert get_resp.status_code == 404
    assert del2.status_code == 204
