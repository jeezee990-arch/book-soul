"""测试 Outline 业务服务（Phase 1.4）。

覆盖：
- create (complete / freedom)
- get / list / update / delete
- outline_type 唯一性（作品内同 type 冲突）
- structure 子模型校验（complete / freedom）
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


COMPLETE_STRUCT = {
    "outline_type": "complete",
    "volumes": [
        {
            "name": "第一卷",
            "summary": "凡人篇",
            "chapters": [
                {
                    "title": "第一章 韩立出生",
                    "summary": "少年灵根被测",
                    "key_events": ["灵根测试", "入七玄门"],
                },
                {
                    "title": "第二章 入门",
                    "key_events": [],
                },
            ],
        },
        {
            "name": "第二卷",
            "chapters": [{"title": "第三章 外出历练"}],
        },
    ],
    "overall_theme": "凡人修仙的热血与孤独",
}

FREEDOM_STRUCT = {
    "outline_type": "freedom",
    "summary": "一个凡人修仙的热血故事",
    "key_beats": ["灵根测试", "拜入宗门", "修为提升"],
    "themes": ["成长", "孤独", "热血"],
}


# ===== Service 单元测试 =====


@pytest.mark.asyncio
async def test_create_complete_outline(db_initialized):
    """创建完整版大纲。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        data = OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
        outline = await svc.create(data)

    assert outline.id is not None
    assert outline.outline_type == "complete"
    # structure 应被注入 outline_type
    assert outline.structure["outline_type"] == "complete"
    assert len(outline.structure["volumes"]) == 2


@pytest.mark.asyncio
async def test_create_freedom_outline(db_initialized):
    """创建创作型大纲。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        data = OutlineCreate(novel_id=nid, outline_type="freedom", structure=FREEDOM_STRUCT)
        outline = await svc.create(data)

    assert outline.outline_type == "freedom"
    assert outline.structure["summary"] == FREEDOM_STRUCT["summary"]
    assert outline.structure["key_beats"] == FREEDOM_STRUCT["key_beats"]


@pytest.mark.asyncio
async def test_create_rejects_invalid_type(db_initialized):
    """非法 outline_type 由 service 校验抛 OutlineValidationError。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService, OutlineValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        data = OutlineCreate(novel_id=nid, outline_type="random", structure=COMPLETE_STRUCT)
        with pytest.raises(OutlineValidationError, match="Invalid outline_type"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_rejects_mismatched_structure_type(db_initialized):
    """outline_type=complete 但 structure 是 freedom 形状由 service 校验。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService, OutlineValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        # complete 结构必须有 volumes；freedom 形状不匹配
        data = OutlineCreate(novel_id=nid, outline_type="complete", structure=FREEDOM_STRUCT)
        with pytest.raises(OutlineValidationError, match="Invalid structure"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_rejects_missing_novel(db_initialized):
    """novel_id 不存在抛 NovelNotFoundError。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import NovelNotFoundError, OutlineService

    async with get_session() as session:
        svc = OutlineService(session)
        data = OutlineCreate(novel_id=9999, outline_type="complete", structure=COMPLETE_STRUCT)
        with pytest.raises(NovelNotFoundError):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_rejects_duplicate_type_in_same_novel(db_initialized):
    """同作品内同 type 不应重复。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import (
        OutlineService,
        OutlineTypeConflictError,
    )

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        await svc.create(
            OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
        )

    async with get_session() as session:
        svc = OutlineService(session)
        with pytest.raises(OutlineTypeConflictError):
            await svc.create(
                OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
            )


@pytest.mark.asyncio
async def test_create_allows_different_types_in_same_novel(db_initialized):
    """同作品内可同时有 complete 和 freedom 两种大纲。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        o1 = await svc.create(
            OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
        )
        o2 = await svc.create(
            OutlineCreate(novel_id=nid, outline_type="freedom", structure=FREEDOM_STRUCT)
        )

    assert o1.id != o2.id
    assert {o1.outline_type, o2.outline_type} == {"complete", "freedom"}


@pytest.mark.asyncio
async def test_get_outline_returns(db_initialized):
    """get 已存在返回。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        c = await svc.create(
            OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
        )

    async with get_session() as session:
        svc = OutlineService(session)
        fetched = await svc.get(c.id)
    assert fetched.id == c.id


@pytest.mark.asyncio
async def test_get_outline_404(db_initialized):
    """get 不存在抛 NotFound。"""
    from src.db import get_session
    from src.services.outline_service import OutlineNotFoundError, OutlineService

    async with get_session() as session:
        svc = OutlineService(session)
        with pytest.raises(OutlineNotFoundError):
            await svc.get(9999)


@pytest.mark.asyncio
async def test_list_all_filters(db_initialized):
    """按 novel_id / outline_type 过滤。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import OutlineService

    n1 = await _create_novel(db_initialized, name="n1")
    n2 = await _create_novel(db_initialized, name="n2")
    async with get_session() as session:
        svc = OutlineService(session)
        await svc.create(
            OutlineCreate(novel_id=n1, outline_type="complete", structure=COMPLETE_STRUCT)
        )
        await svc.create(
            OutlineCreate(novel_id=n1, outline_type="freedom", structure=FREEDOM_STRUCT)
        )
        await svc.create(
            OutlineCreate(novel_id=n2, outline_type="complete", structure=COMPLETE_STRUCT)
        )

    async with get_session() as session:
        svc = OutlineService(session)
        all_n1 = await svc.list_all(novel_id=n1)
        all_complete = await svc.list_all(outline_type="complete")
        n1_complete = await svc.list_all(novel_id=n1, outline_type="complete")

    assert len(all_n1) == 2
    assert len(all_complete) == 2
    assert len(n1_complete) == 1


@pytest.mark.asyncio
async def test_update_outline_partial(db_initialized):
    """update 只改指定字段。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate, OutlineUpdate
    from src.services.outline_service import OutlineService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        c = await svc.create(
            OutlineCreate(novel_id=nid, outline_type="freedom", structure=FREEDOM_STRUCT)
        )

    async with get_session() as session:
        svc = OutlineService(session)
        new_struct = {"summary": "改后的大纲", "key_beats": ["新节拍"]}
        u = await svc.update(c.id, OutlineUpdate(structure=new_struct))

    assert u.structure["summary"] == "改后的大纲"
    assert u.outline_type == "freedom"  # 未改


@pytest.mark.asyncio
async def test_update_rejects_invalid_type(db_initialized):
    """update 改非法 outline_type 抛 ValidationError。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate, OutlineUpdate
    from src.services.outline_service import OutlineService, OutlineValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        c = await svc.create(
            OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
        )

    async with get_session() as session:
        svc = OutlineService(session)
        with pytest.raises(OutlineValidationError, match="Invalid outline_type"):
            await svc.update(c.id, OutlineUpdate(outline_type="random"))


@pytest.mark.asyncio
async def test_delete_outline(db_initialized):
    """delete 后再 get 应 NotFound。"""
    from src.db import get_session
    from src.schemas.outline import OutlineCreate
    from src.services.outline_service import (
        OutlineNotFoundError,
        OutlineService,
    )

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = OutlineService(session)
        c = await svc.create(
            OutlineCreate(novel_id=nid, outline_type="complete", structure=COMPLETE_STRUCT)
        )

    async with get_session() as session:
        svc = OutlineService(session)
        await svc.delete(c.id)

    async with get_session() as session:
        svc = OutlineService(session)
        with pytest.raises(OutlineNotFoundError):
            await svc.get(c.id)


@pytest.mark.asyncio
async def test_delete_idempotent(db_initialized):
    """delete 不存在不报错。"""
    from src.db import get_session
    from src.services.outline_service import OutlineService

    async with get_session() as session:
        svc = OutlineService(session)
        await svc.delete(9999)


# ===== API 端点测试 =====


@pytest.mark.asyncio
async def test_api_create_complete_outline(db_initialized):
    """POST 应 201 + 资源。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/novels/{nid}/outlines",
            json={"novel_id": nid, "outline_type": "complete", "structure": COMPLETE_STRUCT},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["outline_type"] == "complete"
    assert len(data["structure"]["volumes"]) == 2


@pytest.mark.asyncio
async def test_api_create_freedom_outline(db_initialized):
    """freedom 大纲。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/novels/{nid}/outlines",
            json={"novel_id": nid, "outline_type": "freedom", "structure": FREEDOM_STRUCT},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["outline_type"] == "freedom"
    assert data["structure"]["summary"] == FREEDOM_STRUCT["summary"]


@pytest.mark.asyncio
async def test_api_create_422_on_bad_structure(db_initialized):
    """structure 形状不匹配 outline_type 应 422（service 校验）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # outline_type=complete 但 structure 缺 volumes
        resp = await client.post(
            f"/novels/{nid}/outlines",
            json={
                "novel_id": nid,
                "outline_type": "complete",
                "structure": {"summary": "x", "key_beats": []},  # freedom 形状
            },
        )
    assert resp.status_code == 422
    # 错误信息应来自 service
    detail = resp.json()["detail"]
    assert "Invalid structure" in detail


@pytest.mark.asyncio
async def test_api_create_404_on_missing_novel(db_initialized):
    """novel_id 不存在应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/novels/9999/outlines",
            json={"novel_id": 9999, "outline_type": "complete", "structure": COMPLETE_STRUCT},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_create_422_on_duplicate_type(db_initialized):
    """同 type 重复创建应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/novels/{nid}/outlines",
            json={"novel_id": nid, "outline_type": "complete", "structure": COMPLETE_STRUCT},
        )
        resp = await client.post(
            f"/novels/{nid}/outlines",
            json={"novel_id": nid, "outline_type": "complete", "structure": COMPLETE_STRUCT},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_list_outlines_by_novel(db_initialized):
    """GET 应只返回该作品的大纲。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    n1 = await _create_novel(db_initialized, name="n1")
    n2 = await _create_novel(db_initialized, name="n2")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/novels/{n1}/outlines",
            json={"novel_id": n1, "outline_type": "complete", "structure": COMPLETE_STRUCT},
        )
        await client.post(
            f"/novels/{n2}/outlines",
            json={"novel_id": n2, "outline_type": "complete", "structure": COMPLETE_STRUCT},
        )
        resp = await client.get(f"/novels/{n1}/outlines")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_api_get_outline_404(db_initialized):
    """GET /novels/{nid}/outlines/9999 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/novels/{nid}/outlines/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_get_outline_wrong_novel_404(db_initialized):
    """大纲存在但路径 novel_id 不对 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    n1 = await _create_novel(db_initialized, name="n1")
    n2 = await _create_novel(db_initialized, name="n2")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        o = (
            await client.post(
                f"/novels/{n1}/outlines",
                json={"novel_id": n1, "outline_type": "complete", "structure": COMPLETE_STRUCT},
            )
        ).json()
        oid = o["id"]

        # 用 n2 的路径查 n1 的大纲
        resp = await client.get(f"/novels/{n2}/outlines/{oid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_outline(db_initialized):
    """PATCH 改 structure 应成功。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        o = (
            await client.post(
                f"/novels/{nid}/outlines",
                json={"novel_id": nid, "outline_type": "freedom", "structure": FREEDOM_STRUCT},
            )
        ).json()
        oid = o["id"]

        resp = await client.patch(
            f"/novels/{nid}/outlines/{oid}",
            json={"structure": {"summary": "改后", "key_beats": ["新节拍"]}},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["structure"]["summary"] == "改后"


@pytest.mark.asyncio
async def test_api_delete_outline(db_initialized):
    """DELETE 应 204；再 GET 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        o = (
            await client.post(
                f"/novels/{nid}/outlines",
                json={"novel_id": nid, "outline_type": "complete", "structure": COMPLETE_STRUCT},
            )
        ).json()
        oid = o["id"]

        del_resp = await client.delete(f"/novels/{nid}/outlines/{oid}")
    assert del_resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(f"/novels/{nid}/outlines/{oid}")
    assert get_resp.status_code == 404
