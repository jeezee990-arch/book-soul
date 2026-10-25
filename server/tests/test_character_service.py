"""测试 Character 业务服务（Phase 1.2）。

覆盖：
- create / get / list / update / delete
- update_growth：growth_arc 追加 + 新版本 + parent 链
- list_versions / get_version
- 过滤（novel_id / role / is_active）
- 错误路径（NotFound / Validation / FK）
- API 端点（通过 ASGITransport）
"""

from __future__ import annotations

import pytest

# ===== helpers =====


async def _create_novel(db_initialized, **kwargs):
    """在 db_initialized 环境里建一个 Novel，返回 id。"""
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
async def test_create_character_minimal(db_initialized):
    """只填必填字段应能创建。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        data = CharacterCreate(novel_id=nid, name="韩立", role="主角")
        character = await svc.create(data)

    assert character.id is not None
    assert character.novel_id == nid
    assert character.name == "韩立"
    assert character.role == "主角"
    assert character.is_active is True
    assert character.current_version_id is not None


@pytest.mark.asyncio
async def test_create_character_full_fields(db_initialized):
    """填全所有字段。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        data = CharacterCreate(
            novel_id=nid,
            name="南宫婉",
            role="正派",
            basic_info="掩月宗长老",
            personality="温柔果断",
            habits="喜静",
            thinking="因果分明",
            relationships="韩立道侣",
        )
        character = await svc.create(data)

    assert character.basic_info == "掩月宗长老"
    assert character.personality == "温柔果断"
    assert character.relationships == "韩立道侣"


@pytest.mark.asyncio
async def test_create_character_rejects_invalid_role(db_initialized):
    """非法 role 应抛 ValidationError。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService, CharacterValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        data = CharacterCreate(novel_id=nid, name="x", role="酱油")
        with pytest.raises(CharacterValidationError, match="Invalid role"):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_character_rejects_missing_novel(db_initialized):
    """novel_id 不存在应抛 NovelNotFoundError。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService, NovelNotFoundError

    async with get_session() as session:
        svc = CharacterService(session)
        data = CharacterCreate(novel_id=9999, name="x")
        with pytest.raises(NovelNotFoundError):
            await svc.create(data)


@pytest.mark.asyncio
async def test_create_initial_version(db_initialized):
    """创建后应有 1 个 initial 版本，parent_version_id 为 None。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        character = await svc.create(CharacterCreate(novel_id=nid, name="A"))

    async with get_session() as session:
        svc = CharacterService(session)
        versions = await svc.list_versions(character.id)

    assert len(versions) == 1
    v = versions[0]
    assert v.change_reason == "initial"
    assert v.parent_version_id is None
    assert v.character_id == character.id
    assert v.snapshot["name"] == "A"


@pytest.mark.asyncio
async def test_get_character_returns(db_initialized):
    """get 已存在返回。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="B"))

    async with get_session() as session:
        svc = CharacterService(session)
        fetched = await svc.get(c.id)
    assert fetched.name == "B"


@pytest.mark.asyncio
async def test_get_character_not_found(db_initialized):
    """get 不存在抛 NotFound。"""
    from src.db import get_session
    from src.services.character_service import CharacterNotFoundError, CharacterService

    async with get_session() as session:
        svc = CharacterService(session)
        with pytest.raises(CharacterNotFoundError):
            await svc.get(9999)


@pytest.mark.asyncio
async def test_list_all_filters(db_initialized):
    """按 novel_id / role / is_active 过滤。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService

    n1 = await _create_novel(db_initialized, name="小说1")
    n2 = await _create_novel(db_initialized, name="小说2")
    async with get_session() as session:
        svc = CharacterService(session)
        await svc.create(CharacterCreate(novel_id=n1, name="A1", role="主角"))
        await svc.create(CharacterCreate(novel_id=n1, name="A2", role="反派"))
        await svc.create(CharacterCreate(novel_id=n2, name="B1", role="主角", is_active=False))

    async with get_session() as session:
        svc = CharacterService(session)
        all_n1 = await svc.list_all(novel_id=n1)
        only_main = await svc.list_all(novel_id=n1, role="主角")
        only_active = await svc.list_all(novel_id=n1, is_active=True)
        cross_novel_main = await svc.list_all(role="主角")
        b1 = await svc.list_all(novel_id=n2, role="主角", is_active=False)

    assert len(all_n1) == 2
    assert len(only_main) == 1 and only_main[0].name == "A1"
    assert len(only_active) == 2
    assert len(cross_novel_main) == 2
    assert len(b1) == 1 and b1[0].name == "B1"


@pytest.mark.asyncio
async def test_get_active_characters(db_initialized):
    """get_active_characters 只返回 is_active=True。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        await svc.create(CharacterCreate(novel_id=nid, name="活"))
        await svc.create(CharacterCreate(novel_id=nid, name="死", is_active=False))

    async with get_session() as session:
        svc = CharacterService(session)
        active = await svc.get_active_characters(nid)
    assert len(active) == 1
    assert active[0].name == "活"


@pytest.mark.asyncio
async def test_update_character_partial(db_initialized):
    """update 只改指定字段。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate, CharacterUpdate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(
            CharacterCreate(novel_id=nid, name="orig", role="主角", personality="p1")
        )

    async with get_session() as session:
        svc = CharacterService(session)
        u = await svc.update(c.id, CharacterUpdate(name="new", role="反派"))

    assert u.name == "new"
    assert u.role == "反派"
    assert u.personality == "p1"  # 未改


@pytest.mark.asyncio
async def test_update_character_rejects_invalid_role(db_initialized):
    """update 给非法 role 应抛 ValidationError。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate, CharacterUpdate
    from src.services.character_service import CharacterService, CharacterValidationError

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="x"))

    async with get_session() as session:
        svc = CharacterService(session)
        with pytest.raises(CharacterValidationError, match="Invalid role"):
            await svc.update(c.id, CharacterUpdate(role="酱油"))


@pytest.mark.asyncio
async def test_update_character_does_not_create_version(db_initialized):
    """update 普通字段不应创建新版本。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate, CharacterUpdate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="x"))

    async with get_session() as session:
        svc = CharacterService(session)
        await svc.update(c.id, CharacterUpdate(name="y"))
        versions = await svc.list_versions(c.id)

    assert len(versions) == 1  # 还是只有 initial


@pytest.mark.asyncio
async def test_update_growth_appends_arc_and_creates_version(db_initialized):
    """update_growth 追加 growth_arc + 改 personality + 新版本。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate, CharacterGrowthUpdate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="A", personality="p1"))
        original_vid = c.current_version_id

    async with get_session() as session:
        svc = CharacterService(session)
        new_v = await svc.update_growth(
            c.id,
            CharacterGrowthUpdate(
                event="经历师门被灭，性格大变",
                new_personality="p2（冷漠）",
            ),
        )
        # 重新读 character
        c2 = await svc.get(c.id)

    # growth_arc 应追加一行
    assert c2.growth_arc is not None
    assert "经历师门被灭" in c2.growth_arc
    assert c2.personality == "p2（冷漠）"
    # 当前版本变了
    assert c2.current_version_id != original_vid
    assert c2.current_version_id == new_v.id
    # 新版本元数据
    assert new_v.change_reason == "event_trigger"
    assert new_v.trigger_event == "经历师门被灭，性格大变"
    assert new_v.parent_version_id == original_vid
    assert new_v.snapshot["personality"] == "p2（冷漠）"


@pytest.mark.asyncio
async def test_update_growth_multiple_events_chain(db_initialized):
    """多次 growth 事件应链接成版本链，list_versions 按时间倒序。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate, CharacterGrowthUpdate
    from src.services.character_service import CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="X"))

    async with get_session() as session:
        svc = CharacterService(session)
        v1 = await svc.update_growth(
            c.id, CharacterGrowthUpdate(event="事件1", new_personality="p1")
        )
        v2 = await svc.update_growth(c.id, CharacterGrowthUpdate(event="事件2", new_habits="独行"))

    async with get_session() as session:
        svc = CharacterService(session)
        versions = await svc.list_versions(c.id)
        c_final = await svc.get(c.id)

    assert len(versions) == 3  # initial + 2 events
    # list_versions 按 created_at desc, id desc；最新是 v2
    assert versions[0].id == v2.id
    assert versions[1].id == v1.id
    # parent 链：v2 -> v1 -> initial
    assert v2.parent_version_id == v1.id
    assert v1.parent_version_id is not None  # 指向 initial
    # current 应是 v2
    assert c_final.current_version_id == v2.id
    # growth_arc 应有两行
    assert c_final.growth_arc.count("\n") == 1  # 两行
    assert "事件1" in c_final.growth_arc
    assert "事件2" in c_final.growth_arc


@pytest.mark.asyncio
async def test_update_growth_404(db_initialized):
    """update_growth 不存在人物应 404。"""
    from src.db import get_session
    from src.schemas.character import CharacterGrowthUpdate
    from src.services.character_service import CharacterNotFoundError, CharacterService

    async with get_session() as session:
        svc = CharacterService(session)
        with pytest.raises(CharacterNotFoundError):
            await svc.update_growth(9999, CharacterGrowthUpdate(event="x", new_personality="p"))


@pytest.mark.asyncio
async def test_delete_character_cascades_versions(db_initialized):
    """delete 后 list_versions 应 NotFound；versions 表里也应被清。"""
    from sqlalchemy import select

    from src.db import get_session
    from src.models.character import CharacterVersion
    from src.schemas.character import CharacterCreate, CharacterGrowthUpdate
    from src.services.character_service import CharacterNotFoundError, CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="X"))
        await svc.update_growth(c.id, CharacterGrowthUpdate(event="e", new_personality="p"))

    async with get_session() as session:
        svc = CharacterService(session)
        await svc.delete(c.id)

    # character 已无
    async with get_session() as session:
        svc = CharacterService(session)
        with pytest.raises(CharacterNotFoundError):
            await svc.get(c.id)

    # versions 也应被级联清空
    async with get_session() as session:
        stmt = select(CharacterVersion).where(CharacterVersion.character_id == c.id)
        result = await session.execute(stmt)
        assert list(result.scalars()) == []


@pytest.mark.asyncio
async def test_delete_idempotent(db_initialized):
    """delete 不存在不报错。"""
    from src.db import get_session
    from src.services.character_service import CharacterService

    async with get_session() as session:
        svc = CharacterService(session)
        await svc.delete(9999)


@pytest.mark.asyncio
async def test_get_version_not_found(db_initialized):
    """get_version 找不到版本应 NotFound。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterNotFoundError, CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c = await svc.create(CharacterCreate(novel_id=nid, name="X"))

    async with get_session() as session:
        svc = CharacterService(session)
        with pytest.raises(CharacterNotFoundError):
            await svc.get_version(c.id, 9999)


@pytest.mark.asyncio
async def test_get_version_wrong_character(db_initialized):
    """version 存在但属于别的 character 应 NotFound。"""
    from src.db import get_session
    from src.schemas.character import CharacterCreate
    from src.services.character_service import CharacterNotFoundError, CharacterService

    nid = await _create_novel(db_initialized)
    async with get_session() as session:
        svc = CharacterService(session)
        c1 = await svc.create(CharacterCreate(novel_id=nid, name="A"))
        c2 = await svc.create(CharacterCreate(novel_id=nid, name="B"))

    # c1 的版本不属于 c2
    async with get_session() as session:
        svc = CharacterService(session)
        with pytest.raises(CharacterNotFoundError):
            await svc.get_version(c2.id, c1.current_version_id)


# ===== API 端点测试 =====


@pytest.mark.asyncio
async def test_api_create_character(db_initialized):
    """POST /novels/{nid}/characters 应 201 + 资源。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/novels/{nid}/characters",
            json={"novel_id": nid, "name": "韩立", "role": "主角"},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "韩立"
    assert data["role"] == "主角"
    assert data["current_version_id"] is not None


@pytest.mark.asyncio
async def test_api_create_character_path_body_mismatch(db_initialized):
    """路径和 body 的 novel_id 不一致应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/novels/{nid}/characters",
            json={"novel_id": nid + 1, "name": "X"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_update_character_with_growth_arc(db_initialized):
    """PATCH 人物卡（前端编辑表单的完整载荷）应 200。

    ⚠️ 2026-10-25 巡检（真 bug）：前端 ``CharacterCard`` 的编辑表单**一定**
    会带上 ``growth_arc``，而 ``CharacterUpdate`` schema 之前没有这个字段
    + ``extra="forbid"`` → PATCH 一律 422「额外字段不允许」→
    **连改个名字都保存不了**。
    """
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            f"/novels/{nid}/characters",
            json={"novel_id": nid, "name": "韩立", "role": "主角"},
        )
        cid = created.json()["id"]

        # 完全照抄前端 startEdit() 的载荷
        resp = await client.patch(
            f"/characters/{cid}",
            json={
                "name": "韩立",
                "role": "主角",
                "basic_info": None,
                "personality": None,
                "habits": None,
                "thinking": None,
                "relationships": None,
                "growth_arc": "从废材到飞升",
                "is_active": True,
            },
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["growth_arc"] == "从废材到飞升"


@pytest.mark.asyncio
async def test_api_list_characters_by_novel(db_initialized):
    """GET /novels/{nid}/characters 应只返回该作品。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    n1 = await _create_novel(db_initialized, name="n1")
    n2 = await _create_novel(db_initialized, name="n2")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/novels/{n1}/characters", json={"novel_id": n1, "name": "A"})
        await client.post(f"/novels/{n2}/characters", json={"novel_id": n2, "name": "B"})
        resp = await client.get(f"/novels/{n1}/characters")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "A"


@pytest.mark.asyncio
async def test_api_get_character_404(db_initialized):
    """GET /characters/9999 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/characters/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_update_character(db_initialized):
    """PATCH /characters/{id} 只改指定字段。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(
                f"/novels/{nid}/characters",
                json={"novel_id": nid, "name": "orig", "personality": "p1"},
            )
        ).json()
        cid = c["id"]
        resp = await client.patch(f"/characters/{cid}", json={"name": "new"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "new"
    assert data["personality"] == "p1"  # 未改


@pytest.mark.asyncio
async def test_api_record_growth(db_initialized):
    """POST /characters/{id}/growth 应追加 + 新版本。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(
                f"/novels/{nid}/characters",
                json={"novel_id": nid, "name": "A", "personality": "p1"},
            )
        ).json()
        cid = c["id"]
        original_vid = c["current_version_id"]

        resp = await client.post(
            f"/characters/{cid}/growth",
            json={"event": "师门被灭", "new_personality": "p2"},
        )
    assert resp.status_code == 201, resp.text
    v = resp.json()
    assert v["change_reason"] == "event_trigger"
    assert v["trigger_event"] == "师门被灭"
    assert v["parent_version_id"] == original_vid

    # 查 character 应能看到新 personality 和 arc
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c2 = (await client.get(f"/characters/{cid}")).json()
    assert c2["personality"] == "p2"
    assert "师门被灭" in c2["growth_arc"]


@pytest.mark.asyncio
async def test_api_list_versions(db_initialized):
    """GET /characters/{id}/versions 应按时间倒序返回。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(f"/novels/{nid}/characters", json={"novel_id": nid, "name": "A"})
        ).json()
        cid = c["id"]
        await client.post(
            f"/characters/{cid}/growth",
            json={"event": "e1", "new_personality": "p1"},
        )
        await client.post(
            f"/characters/{cid}/growth",
            json={"event": "e2", "new_habits": "h2"},
        )
        resp = await client.get(f"/characters/{cid}/versions")
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 3  # initial + 2 events
    # 最新的在最前
    assert versions[0]["trigger_event"] == "e2"
    assert versions[1]["trigger_event"] == "e1"
    assert versions[2]["change_reason"] == "initial"


@pytest.mark.asyncio
async def test_api_get_version(db_initialized):
    """GET /characters/{id}/versions/{vid} 应返回单个版本。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(f"/novels/{nid}/characters", json={"novel_id": nid, "name": "A"})
        ).json()
        cid = c["id"]
        vid = c["current_version_id"]

        resp = await client.get(f"/characters/{cid}/versions/{vid}")
    assert resp.status_code == 200
    v = resp.json()
    assert v["id"] == vid
    assert v["change_reason"] == "initial"


@pytest.mark.asyncio
async def test_api_delete_character(db_initialized):
    """DELETE /characters/{id} 应 204；再 GET 应 404。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    nid = await _create_novel(db_initialized)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post(f"/novels/{nid}/characters", json={"novel_id": nid, "name": "A"})
        ).json()
        cid = c["id"]

        del_resp = await client.delete(f"/characters/{cid}")
    assert del_resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(f"/characters/{cid}")
    assert get_resp.status_code == 404
