"""测试 Novel 业务服务（Phase 1.1）。

覆盖：
- create / get / list / update / delete
- 过滤（genre / status）
- 错误路径（NotFound / Validation）
- API 端点（通过 ASGITransport）
"""

from __future__ import annotations

import pytest

# ===== Service 单元测试 =====


@pytest.mark.asyncio
async def test_create_novel_minimal(db_initialized):
    """只填 name + genre 应能创建，其他用默认值。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        data = NovelCreate(name="我的小说", genre="xuanhuan")
        novel = await svc.create(data)

    assert novel.id is not None
    assert novel.name == "我的小说"
    assert novel.genre == "xuanhuan"
    assert novel.status == "draft"
    assert novel.outline_mode is None
    assert novel.imported is False
    assert novel.read_only is False
    assert novel.created_at is not None
    assert novel.updated_at is not None


@pytest.mark.asyncio
async def test_create_novel_full_fields(db_initialized):
    """填全所有字段。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        data = NovelCreate(
            name="都市",
            genre="dushi",
            style="现代",
            description="一个都市故事",
            status="writing",
            outline_mode="freedom",
            file_path="C:/books/dushi.txt",
            imported=True,
            read_only=False,
        )
        novel = await svc.create(data)

    assert novel.style == "现代"
    assert novel.status == "writing"
    assert novel.outline_mode == "freedom"
    assert novel.file_path == "C:/books/dushi.txt"
    assert novel.imported is True


@pytest.mark.asyncio
async def test_create_novel_rejects_invalid_status(db_initialized):
    """非法 status 应抛 NovelValidationError。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService, NovelValidationError

    async with get_session() as session:
        svc = NovelService(session)
        data = NovelCreate(name="bad", genre="xuanhuan", status="not_a_status")
        with pytest.raises(NovelValidationError, match="Invalid status"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_novel_rejects_invalid_outline_mode(db_initialized):
    """非法 outline_mode 应抛 NovelValidationError。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService, NovelValidationError

    async with get_session() as session:
        svc = NovelService(session)
        data = NovelCreate(name="bad", genre="xuanhuan", outline_mode="random")
        with pytest.raises(NovelValidationError, match="Invalid outline_mode"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_get_novel_returns_instance(db_initialized):
    """get 已存在的 id 应返回对象。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        created = await svc.create(NovelCreate(name="n", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        fetched = await svc.get(created.id)
    assert fetched.id == created.id
    assert fetched.name == "n"


@pytest.mark.asyncio
async def test_get_novel_raises_not_found(db_initialized):
    """get 不存在的 id 应抛 NovelNotFoundError。"""
    from src.db import get_session
    from src.services.novel_service import NovelNotFoundError, NovelService

    async with get_session() as session:
        svc = NovelService(session)
        with pytest.raises(NovelNotFoundError):
            await svc.get(9999)


@pytest.mark.asyncio
async def test_list_all_empty(db_initialized):
    """空表应返回空 list。"""
    from src.db import get_session
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        result = await svc.list_all()
    assert result == []


@pytest.mark.asyncio
async def test_list_all_returns_all_when_no_filter(db_initialized):
    """无过滤时应返回全部。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        for name in ("a", "b", "c"):
            await svc.create(NovelCreate(name=name, genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        result = await svc.list_all()
    assert len(result) == 3
    assert [n.name for n in result] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_list_all_filters_by_genre(db_initialized):
    """genre 过滤只返回匹配的。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        await svc.create(NovelCreate(name="xh1", genre="xuanhuan"))
        await svc.create(NovelCreate(name="xh2", genre="xuanhuan"))
        await svc.create(NovelCreate(name="ds1", genre="dushi"))

    async with get_session() as session:
        svc = NovelService(session)
        xh = await svc.list_all(genre="xuanhuan")
        ds = await svc.list_all(genre="dushi")
    assert len(xh) == 2
    assert len(ds) == 1
    assert ds[0].name == "ds1"


@pytest.mark.asyncio
async def test_list_all_filters_by_status(db_initialized):
    """status 过滤。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        await svc.create(NovelCreate(name="d1", genre="xuanhuan", status="draft"))
        await svc.create(NovelCreate(name="w1", genre="xuanhuan", status="writing"))

    async with get_session() as session:
        svc = NovelService(session)
        writing = await svc.list_all(status="writing")
    assert len(writing) == 1
    assert writing[0].name == "w1"


@pytest.mark.asyncio
async def test_update_novel_partial(db_initialized):
    """update 只改指定字段。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate, NovelUpdate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        created = await svc.create(NovelCreate(name="orig", genre="xuanhuan", style="古典"))

    async with get_session() as session:
        svc = NovelService(session)
        updated = await svc.update(created.id, NovelUpdate(name="new", status="writing"))

    assert updated.name == "new"
    assert updated.status == "writing"
    assert updated.style == "古典"  # 未改，保持原值
    assert updated.genre == "xuanhuan"


@pytest.mark.asyncio
async def test_update_novel_raises_not_found(db_initialized):
    """update 不存在的 id 应抛 NovelNotFoundError。"""
    from src.db import get_session
    from src.schemas.novel import NovelUpdate
    from src.services.novel_service import NovelNotFoundError, NovelService

    async with get_session() as session:
        svc = NovelService(session)
        with pytest.raises(NovelNotFoundError):
            await svc.update(9999, NovelUpdate(name="x"))


@pytest.mark.asyncio
async def test_update_novel_rejects_invalid_status(db_initialized):
    """update 给非法 status 应抛 NovelValidationError。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate, NovelUpdate
    from src.services.novel_service import NovelService, NovelValidationError

    async with get_session() as session:
        svc = NovelService(session)
        created = await svc.create(NovelCreate(name="n", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        with pytest.raises(NovelValidationError, match="Invalid status"):
            await svc.update(created.id, NovelUpdate(status="bad"))


@pytest.mark.asyncio
async def test_delete_novel(db_initialized):
    """delete 后再 get 应 NotFound。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelNotFoundError, NovelService

    async with get_session() as session:
        svc = NovelService(session)
        created = await svc.create(NovelCreate(name="del", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        await svc.delete(created.id)

    async with get_session() as session:
        svc = NovelService(session)
        with pytest.raises(NovelNotFoundError):
            await svc.get(created.id)


@pytest.mark.asyncio
async def test_delete_novel_idempotent(db_initialized):
    """delete 不存在的 id 不应抛错（幂等）。"""
    from src.db import get_session
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        # 不存在也应正常返回
        await svc.delete(9999)


# ===== API 端点测试 =====


@pytest.mark.asyncio
async def test_api_create_novel(db_initialized):
    """POST /novels 应返回 201 + 资源。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/novels",
            json={"name": "API 小说", "genre": "xuanhuan"},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "API 小说"
    assert data["genre"] == "xuanhuan"
    assert data["status"] == "draft"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_api_create_novel_validation_422(db_initialized):
    """缺 name 应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/novels", json={"genre": "xuanhuan"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_list_novels_empty(db_initialized):
    """GET /novels 空表应返回 []。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/novels")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_api_list_novels_with_filter(db_initialized):
    """GET /novels?genre=x 应只返回匹配的。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/novels", json={"name": "xh", "genre": "xuanhuan"})
        await client.post("/novels", json={"name": "ds", "genre": "dushi"})
        resp = await client.get("/novels", params={"genre": "dushi"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "ds"


@pytest.mark.asyncio
async def test_api_get_novel_404(db_initialized):
    """GET /novels/{id} 不存在应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/novels/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_novel(db_initialized):
    """PATCH /novels/{id} 应只改指定字段。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = (
            await client.post(
                "/novels",
                json={"name": "orig", "genre": "xuanhuan", "style": "古典"},
            )
        ).json()
        nid = created["id"]

        resp = await client.patch(f"/novels/{nid}", json={"status": "writing"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "orig"  # 未改
    assert data["status"] == "writing"
    assert data["style"] == "古典"


@pytest.mark.asyncio
async def test_api_delete_novel(db_initialized):
    """DELETE /novels/{id} 应返回 204；再 GET 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = (
            await client.post("/novels", json={"name": "to-del", "genre": "xuanhuan"})
        ).json()
        nid = created["id"]

        del_resp = await client.delete(f"/novels/{nid}")
    assert del_resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(f"/novels/{nid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_api_delete_nonexistent_is_idempotent(db_initialized):
    """DELETE 不存在应 204（幂等）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/novels/9999")
    assert resp.status_code == 204
