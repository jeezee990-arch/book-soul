"""测试素材库管理能力（2026-10-29）。

覆盖：
- title / pinned 字段读写（PATCH）
- 列表置顶优先
- 批量删除
- reorder 后排序正确
- 新 schema 字段的 422 校验
- 既有库（无新列）首次启动自动补列 + 幂等
"""

from __future__ import annotations

import sqlite3

import pytest

NOTE_CONTENT = {"text": "地铁上想到的灵感"}
KW_CONTENT = {"words": ["修仙", "废柴"]}


# ===== 字段读写 =====


@pytest.mark.asyncio
async def test_update_title_and_pinned(db_initialized):
    """PATCH 能改 title 和 pinned。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate, InspirationUpdate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    async with get_session() as session:
        svc = InspirationService(session)
        u = await svc.update(c.id, InspirationUpdate(title="剑与霜", pinned=True))

    assert u.title == "剑与霜"
    assert u.pinned is True
    assert u.sort_order == 0


@pytest.mark.asyncio
async def test_title_can_be_cleared(db_initialized):
    """title 传 None 会清空（前端退回派生摘要标签）。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate, InspirationUpdate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        c = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT, title="旧名字"))

    async with get_session() as session:
        svc = InspirationService(session)
        u = await svc.update(c.id, InspirationUpdate(title=None))

    assert u.title is None


@pytest.mark.asyncio
async def test_api_patch_pinned_and_title(db_initialized):
    """PATCH /inspirations/{id} 能改置顶和标题。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        ).json()
        resp = await client.patch(
            f"/inspirations/{c['id']}",
            json={"title": "新标题", "pinned": True},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "新标题"
    assert data["pinned"] is True


@pytest.mark.asyncio
async def test_api_rejects_too_long_title(db_initialized):
    """title 超过 200 字应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        ).json()
        resp = await client.patch(f"/inspirations/{c['id']}", json={"title": "x" * 201})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_rejects_unknown_field(db_initialized):
    """InspirationUpdate 是 extra=forbid：未知字段应 422。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        ).json()
        resp = await client.patch(f"/inspirations/{c['id']}", json={"nope": 1})
    assert resp.status_code == 422


# ===== 列表排序 =====


@pytest.mark.asyncio
async def test_list_puts_pinned_first(db_initialized):
    """置顶项排在最前。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate, InspirationUpdate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        a = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))
        b = await svc.create(InspirationCreate(type="keyword", content=KW_CONTENT))
        # 把 a 置顶
        await svc.update(a.id, InspirationUpdate(pinned=True))

    async with get_session() as session:
        svc = InspirationService(session)
        listed = await svc.list_all()

    assert [i.id for i in listed] == [a.id, b.id]
    assert listed[0].pinned is True


@pytest.mark.asyncio
async def test_list_sorts_by_sort_order(db_initialized):
    """sort_order 小的排前面。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        ids = []
        for _ in range(3):
            ins = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))
            ids.append(ins.id)

    async with get_session() as session:
        svc = InspirationService(session)
        # 重排成倒序
        await svc.reorder(list(reversed(ids)))

    async with get_session() as session:
        svc = InspirationService(session)
        listed = await svc.list_all()

    assert [i.id for i in listed] == list(reversed(ids))


# ===== 批量删除 =====


@pytest.mark.asyncio
async def test_batch_delete_removes_rows(db_initialized):
    """批量删除返回实际删除条数。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        ids = []
        for _ in range(3):
            ins = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))
            ids.append(ins.id)

    async with get_session() as session:
        svc = InspirationService(session)
        deleted = await svc.batch_delete(ids[:2])

    assert deleted == 2

    async with get_session() as session:
        svc = InspirationService(session)
        remaining = await svc.list_all()
    assert [i.id for i in remaining] == [ids[2]]


@pytest.mark.asyncio
async def test_batch_delete_ignores_missing_ids(db_initialized):
    """不存在的 id 不计入删除条数，也不报错。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        ins = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    async with get_session() as session:
        svc = InspirationService(session)
        deleted = await svc.batch_delete([ins.id, 99999, ins.id])

    assert deleted == 1


@pytest.mark.asyncio
async def test_api_batch_delete(db_initialized):
    """POST /inspirations/batch-delete 应返回 deleted 条数。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ids = []
        for _ in range(3):
            c = (
                await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
            ).json()
            ids.append(c["id"])

        resp = await client.post("/inspirations/batch-delete", json={"ids": ids[:2]})

    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] == 2


@pytest.mark.asyncio
async def test_api_batch_delete_requires_ids(db_initialized):
    """ids 为空数组应 422（Pydantic min_length=1）。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/inspirations/batch-delete", json={"ids": []})
    assert resp.status_code == 422


# ===== reorder =====


@pytest.mark.asyncio
async def test_reorder_assigns_sort_order(db_initialized):
    """reorder 按下标赋 sort_order。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        ids = []
        for _ in range(3):
            ins = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))
            ids.append(ins.id)

    async with get_session() as session:
        svc = InspirationService(session)
        ordered = await svc.reorder([ids[2], ids[0], ids[1]])

    assert [i.id for i in ordered] == [ids[2], ids[0], ids[1]]
    assert [i.sort_order for i in ordered] == [0, 1, 2]


@pytest.mark.asyncio
async def test_reorder_persists_across_sessions(db_initialized):
    """重排后重新开 session 读取，顺序仍是新的（重启后不丢）。"""
    from src.db import get_session
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    async with get_session() as session:
        svc = InspirationService(session)
        ids = []
        for _ in range(3):
            ins = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))
            ids.append(ins.id)

    new_order = [ids[1], ids[2], ids[0]]
    async with get_session() as session:
        svc = InspirationService(session)
        await svc.reorder(new_order)

    async with get_session() as session:
        svc = InspirationService(session)
        listed = await svc.list_all()

    assert [i.id for i in listed] == new_order


@pytest.mark.asyncio
async def test_api_reorder(db_initialized):
    """POST /inspirations/reorder 应返回按新顺序排列的列表。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ids = []
        for _ in range(3):
            c = (
                await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
            ).json()
            ids.append(c["id"])

        new_order = list(reversed(ids))
        resp = await client.post("/inspirations/reorder", json={"ids": new_order})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert [i["id"] for i in data["items"]] == new_order
    assert [i["sort_order"] for i in data["items"]] == [0, 1, 2]


@pytest.mark.asyncio
async def test_api_reorder_skips_missing_ids(db_initialized):
    """reorder 里不存在的 id 自动跳过，不报错。"""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = (
            await client.post("/inspirations", json={"type": "note", "content": NOTE_CONTENT})
        ).json()
        resp = await client.post("/inspirations/reorder", json={"ids": [99999, c["id"]]})
    assert resp.status_code == 200, resp.text
    assert [i["id"] for i in resp.json()["items"]] == [c["id"]]


# ===== 既有库升级 =====

_OLD_INSPIRATIONS_DDL = """
CREATE TABLE inspirations (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER,
    type VARCHAR(20) NOT NULL DEFAULT 'note',
    content JSON NOT NULL,
    source VARCHAR(500),
    tags JSON NOT NULL DEFAULT '[]',
    created_at DATETIME NOT NULL
)
"""


def _table_columns(db_path) -> set[str]:
    """读某张表的列名集合。"""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("PRAGMA table_info(inspirations)").fetchall()
    finally:
        conn.close()
    return {row[1] for row in rows}


def _create_legacy_table(db_path) -> None:
    """造一个"旧版" inspirations 表（无 title/pinned/sort_order）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_OLD_INSPIRATIONS_DDL)
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_init_db_upgrades_legacy_table(temp_db):
    """既有库（无 title/pinned/sort_order）启动后自动补列。"""
    from src.db import init_db

    _create_legacy_table(temp_db)

    assert "title" not in _table_columns(temp_db)

    await init_db()

    columns = _table_columns(temp_db)
    assert {"title", "pinned", "sort_order"} <= columns


@pytest.mark.asyncio
async def test_init_db_is_idempotent(temp_db):
    """重复启动不报错（补列逻辑必须幂等）。"""
    from src.db import init_db

    _create_legacy_table(temp_db)

    await init_db()
    await init_db()  # 第二次：列已存在，不应报 "duplicate column"

    assert {"title", "pinned", "sort_order"} <= _table_columns(temp_db)


@pytest.mark.asyncio
async def test_legacy_db_usable_through_orm(temp_db):
    """补列后 ORM 能正常读写（默认值正确）。"""
    from src.db import get_session, init_db
    from src.schemas.inspiration import InspirationCreate
    from src.services.inspiration_service import InspirationService

    _create_legacy_table(temp_db)

    await init_db()

    async with get_session() as session:
        svc = InspirationService(session)
        ins = await svc.create(InspirationCreate(type="note", content=NOTE_CONTENT))

    assert ins.pinned is False
    assert ins.sort_order == 0
    assert ins.title is None
