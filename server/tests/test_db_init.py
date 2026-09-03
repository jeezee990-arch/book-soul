"""测试 db.py：init_db 建表 + get_session 上下文 + Novel 增删改查。

temp_db fixture 见 tests/conftest.py。
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_init_db_creates_db_file(temp_db):
    """init_db 应创建 db 文件 + novels 表。"""
    from src.db import init_db

    await init_db()
    assert temp_db.is_file()

    # 验证 novels 表存在
    from src.db import engine

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert "novels" in tables


@pytest.mark.asyncio
async def test_init_db_idempotent(temp_db):
    """多次 init_db 不应抛错。"""
    from src.db import init_db

    await init_db()
    await init_db()  # 第二次不应报错


@pytest.mark.asyncio
async def test_get_session_yields_session(temp_db):
    """get_session 应 yield 一个 AsyncSession。"""
    from src.db import get_session, init_db

    await init_db()
    async with get_session() as session:
        # 能执行一个最简单的查询
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_novel_crud_roundtrip(temp_db):
    """Novel 表的增删改查能跑通。"""
    from src.db import get_session, init_db
    from src.models import Novel

    await init_db()

    # create
    async with get_session() as session:
        novel = Novel(name="测试小说", genre="xuanhuan", style="古典", description="test")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id
        assert novel_id is not None
        assert novel.name == "测试小说"
        assert novel.status == "draft"
        # 自动维护的时间戳
        assert novel.created_at is not None
        assert novel.updated_at is not None

    # read
    async with get_session() as session:
        from sqlalchemy import select

        stmt = select(Novel).where(Novel.id == novel_id)
        result = await session.execute(stmt)
        fetched = result.scalar_one()
        assert fetched.name == "测试小说"
        assert fetched.genre == "xuanhuan"


@pytest.mark.asyncio
async def test_novel_timestamps_update_on_modify(temp_db):
    """修改 Novel 后 updated_at 应改变。"""
    import asyncio

    from sqlalchemy import select

    from src.db import get_session, init_db
    from src.models import Novel

    await init_db()

    async with get_session() as session:
        novel = Novel(name="时间戳测试", genre="dushi")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        original_updated = novel.updated_at
        novel_id = novel.id

    # 等待 1 秒确保时间戳能变化
    await asyncio.sleep(1.1)

    async with get_session() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        result = await session.execute(stmt)
        novel = result.scalar_one()
        novel.name = "改名"
        await session.commit()
        await session.refresh(novel)
        assert novel.updated_at > original_updated
