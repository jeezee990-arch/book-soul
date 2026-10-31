"""作品管理能力测试（2026-10-30：命名 + 排序 + 重名保护）。

背景
----
用户实测反馈三件事：

1. 「开新书」程序自动命的名字跟素材库里已有的作品重名时，**新书存不进素材库**；
2. 素材库（作品 Tab）没有右键菜单，也没有删除 / 排序 / 重命名。

第 1 条的根因是后端大纲生成「按书名 upsert」：名字撞上就复用旧书，
旧书的大纲被冲掉、新书根本没入库。这里锁住新契约：

- 素材库里**同一时间只能有一本同名作品**（创建 / 改名撞名 → 409）
- 需要自动避开重名的场景（程序自动命名）→ 加序号（``X`` → ``X 2``）
- 作品列表支持**手动排序**（``sort_order``），并持久化

覆盖：
- service：重名检测 / unique_name / reorder / 列表排序
- API：POST 重名 409 / PATCH 改名 409 / POST /novels/reorder
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ===== service 单元测试 =====


@pytest.mark.asyncio
async def test_create_novel_rejects_duplicate_name(db_initialized: Path) -> None:
    """同名作品不能再建第二本。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelNameConflictError, NovelService

    async with get_session() as session:
        svc = NovelService(session)
        await svc.create(NovelCreate(name="同名书", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        with pytest.raises(NovelNameConflictError, match="同名书"):
            await svc.create(NovelCreate(name="同名书", genre="xuanhuan"))


@pytest.mark.asyncio
async def test_update_novel_rejects_duplicate_name(db_initialized: Path) -> None:
    """改名撞上别的书 → 冲突错误；原名保持不变。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate, NovelUpdate
    from src.services.novel_service import NovelNameConflictError, NovelService

    async with get_session() as session:
        svc = NovelService(session)
        a = await svc.create(NovelCreate(name="甲书", genre="xuanhuan"))
        b = await svc.create(NovelCreate(name="乙书", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        with pytest.raises(NovelNameConflictError):
            await svc.update(b.id, NovelUpdate(name="甲书"))

    async with get_session() as session:
        svc = NovelService(session)
        assert (await svc.get(b.id)).name == "乙书"
        assert (await svc.get(a.id)).name == "甲书"


@pytest.mark.asyncio
async def test_update_novel_same_name_allowed(db_initialized: Path) -> None:
    """改成自己的名字不算冲突（大小写之外的完全同名）。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate, NovelUpdate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        a = await svc.create(NovelCreate(name="自改名", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        updated = await svc.update(a.id, NovelUpdate(name="自改名"))
        assert updated.name == "自改名"


@pytest.mark.asyncio
async def test_unique_name_avoids_taken_names(db_initialized: Path) -> None:
    """unique_name：被占了就加序号，一直加到没人用为止。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        await svc.create(NovelCreate(name="修仙新作", genre="xuanhuan"))
        await svc.create(NovelCreate(name="修仙新作 2", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        assert await svc.unique_name("修仙新作") == "修仙新作 3"
        assert await svc.unique_name("全新书") == "全新书"


@pytest.mark.asyncio
async def test_reorder_sets_sort_order(db_initialized: Path) -> None:
    """reorder：sort_order = 下标；列表按新顺序返回。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        a = await svc.create(NovelCreate(name="A", genre="xuanhuan"))
        b = await svc.create(NovelCreate(name="B", genre="xuanhuan"))
        c = await svc.create(NovelCreate(name="C", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        ordered = await svc.reorder([c.id, a.id, b.id])
        assert [n.id for n in ordered] == [c.id, a.id, b.id]

    async with get_session() as session:
        svc = NovelService(session)
        listed = await svc.list_all()
        assert [n.id for n in listed] == [c.id, a.id, b.id]
        assert [n.sort_order for n in listed] == [0, 1, 2]


@pytest.mark.asyncio
async def test_reorder_keeps_missing_items_at_the_end(db_initialized: Path) -> None:
    """没在列表里的作品要排到后面（否则 sort_order=0 会跳到最前面）。"""
    from src.db import get_session
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with get_session() as session:
        svc = NovelService(session)
        a = await svc.create(NovelCreate(name="A", genre="xuanhuan"))
        b = await svc.create(NovelCreate(name="B", genre="xuanhuan"))
        c = await svc.create(NovelCreate(name="C", genre="xuanhuan"))

    async with get_session() as session:
        svc = NovelService(session)
        await svc.reorder([c.id, a.id])  # b 不在列表里

    async with get_session() as session:
        svc = NovelService(session)
        listed = await svc.list_all()
        assert [n.id for n in listed] == [c.id, a.id, b.id]
        assert listed[-1].id == b.id


# ===== API 端点测试 =====


@pytest.mark.asyncio
async def test_api_create_novel_duplicate_409(db_initialized: Path) -> None:
    """POST /novels 重名 → 409（前端据此提示"已有同名作品"）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/novels", json={"name": "重复名", "genre": "xuanhuan"})
        second = await client.post("/novels", json={"name": "重复名", "genre": "xuanhuan"})

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert "重复名" in second.json()["detail"]


@pytest.mark.asyncio
async def test_api_rename_novel(db_initialized: Path) -> None:
    """PATCH /novels/{id} 改名应生效（素材库右键重命名走的就是它）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/novels", json={"name": "旧名字", "genre": "xuanhuan"})
        novel_id = created.json()["id"]
        resp = await client.patch(f"/novels/{novel_id}", json={"name": "新名字"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "新名字"


@pytest.mark.asyncio
async def test_api_rename_novel_conflict_409(db_initialized: Path) -> None:
    """改名撞名 → 409，且不改动原名。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/novels", json={"name": "占用名", "genre": "xuanhuan"})
        second = await client.post("/novels", json={"name": "另一本", "genre": "xuanhuan"})
        novel_id = second.json()["id"]
        resp = await client.patch(f"/novels/{novel_id}", json={"name": "占用名"})
        after = await client.get(f"/novels/{novel_id}")

    assert resp.status_code == 409, resp.text
    assert after.json()["name"] == "另一本"


@pytest.mark.asyncio
async def test_api_reorder_novels(db_initialized: Path) -> None:
    """POST /novels/reorder → 顺序持久化，GET /novels 按新顺序返回。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = (await client.post("/novels", json={"name": "A", "genre": "xuanhuan"})).json()
        b = (await client.post("/novels", json={"name": "B", "genre": "xuanhuan"})).json()
        c = (await client.post("/novels", json={"name": "C", "genre": "xuanhuan"})).json()

        resp = await client.post("/novels/reorder", json={"ids": [c["id"], b["id"], a["id"]]})
        assert resp.status_code == 200, resp.text
        assert [i["id"] for i in resp.json()["items"]] == [c["id"], b["id"], a["id"]]

        listed = await client.get("/novels")
        assert [n["id"] for n in listed.json()] == [c["id"], b["id"], a["id"]]
        assert [n["sort_order"] for n in listed.json()] == [0, 1, 2]


@pytest.mark.asyncio
async def test_api_delete_novel(db_initialized: Path) -> None:
    """DELETE /novels/{id} → 204，之后列表里没有了。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/novels", json={"name": "待删", "genre": "xuanhuan"})
        novel_id = created.json()["id"]
        resp = await client.delete(f"/novels/{novel_id}")
        listed = await client.get("/novels")

    assert resp.status_code == 204, resp.text
    assert listed.json() == []
