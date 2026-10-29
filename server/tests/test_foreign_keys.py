"""SQLite 外键约束 + 孤儿数据清理（2026-10-29 巡检发现）。

背景
----
SQLite 的 ``PRAGMA foreign_keys`` **默认是 OFF**（历史兼容原因）。
关着的时候，ORM 里写的 ``ondelete="CASCADE"`` / ``"SET NULL"``
**完全不生效** —— 删掉一本作品，它的章节、人物卡、大纲全留在库里。

更糟的是模型里的 id 没有 ``AUTOINCREMENT``，SQLite 会**复用**被删掉的
最大 id，于是"重建作品"拿到同一个 id，上一部作品遗留的章节就**串进了
新作品**。

实测：删掉 novel 4 → 重建得到 novel 4 → 建章节直接 422
``Chapter number 1 already exists in novel 4``
（冲突的是**上一部作品**留下的章节）。

这两条测试锁住"外键开启 + 级联删除 + 孤儿清理"的行为。
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest


def _cols(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _count(db_path: Path, sql: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def test_foreign_keys_pragma_is_on(temp_db: Path) -> None:
    """连接建立后 ``PRAGMA foreign_keys`` 必须是 ON。"""
    from src.db import engine, init_db

    async def _check() -> bool:
        await init_db()  # 顺带建目录（engine 建连时要求目录已存在）
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql("PRAGMA foreign_keys")
            return bool(result.scalar())

    assert asyncio.run(_check()) is True


def test_deleting_novel_cascades_to_chapters(temp_db: Path) -> None:
    """删作品要级联删掉它的章节 —— 不能留孤儿。"""
    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())

    # 造数据：作品 + 章节
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO novels (name, genre, status, created_at, updated_at) "
            "VALUES ('待删', 'xuanhuan', 'draft', '2026-01-01', '2026-01-01')"
        )
        novel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO chapters (novel_id, chapter_number, title, status, "
            "created_at, updated_at) "
            "VALUES (?, 1, '第一章', 'outline', '2026-01-01', '2026-01-01')",
            (novel_id,),
        )
        conn.commit()
    finally:
        conn.close()

    assert _count(db_path, "SELECT COUNT(*) FROM chapters") == 1

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
        conn.commit()
    finally:
        conn.close()

    assert _count(db_path, "SELECT COUNT(*) FROM chapters") == 0


def test_orphan_rows_are_purged_on_startup(temp_db: Path) -> None:
    """启动时要清掉"父行已删"的孤儿行。

    - CASCADE 的子行（chapters/characters/outlines）→ 删掉
    - SET NULL 的列（inspirations.novel_id）→ **置 NULL**，素材本身要保留
    """
    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())

    # 造孤儿：novel_id 指向不存在的作品
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO novels (name, genre, status, created_at, updated_at) "
            "VALUES ('留着的', 'xuanhuan', 'draft', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO chapters (novel_id, chapter_number, title, status, "
            "created_at, updated_at) "
            "VALUES (999, 1, '孤儿章', 'outline', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO inspirations (novel_id, type, content, tags, created_at) "
            "VALUES (999, 'idea', '{}', '[]', '2026-01-01')"
        )
        conn.commit()
    finally:
        conn.close()

    assert _count(db_path, "SELECT COUNT(*) FROM chapters WHERE novel_id = 999") == 1

    asyncio.run(init_db())

    # CASCADE → 孤儿章节被删
    assert _count(db_path, "SELECT COUNT(*) FROM chapters WHERE novel_id = 999") == 0
    # SET NULL → 素材还在，只是脱离了作品
    assert _count(db_path, "SELECT COUNT(*) FROM inspirations WHERE novel_id IS NULL") == 1
    # 正常作品的数据不受影响
    assert _count(db_path, "SELECT COUNT(*) FROM novels") == 1
    assert "novel_id" in _cols(db_path, "inspirations")


def test_purge_is_idempotent(temp_db: Path) -> None:
    """清理是幂等的 —— 连跑两次不报错、不误删。"""
    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO novels (name, genre, status, created_at, updated_at) "
            "VALUES ('留着', 'xuanhuan', 'draft', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO chapters (novel_id, chapter_number, title, status, "
            "created_at, updated_at) "
            "VALUES (999, 1, '孤儿章', 'outline', '2026-01-01', '2026-01-01')"
        )
        conn.commit()
    finally:
        conn.close()

    asyncio.run(init_db())
    asyncio.run(init_db())

    assert _count(db_path, "SELECT COUNT(*) FROM chapters WHERE novel_id = 999") == 0
    assert _count(db_path, "SELECT COUNT(*) FROM novels") == 1


@pytest.mark.parametrize("table", ["chapters", "characters", "outlines"])
def test_no_orphan_rows_after_init(temp_db: Path, table: str) -> None:
    """启动后不允许再有"父行不存在"的子行。"""
    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO novels (name, genre, status, created_at, updated_at) "
            "VALUES ('a', 'xuanhuan', 'draft', '2026-01-01', '2026-01-01')"
        )
        conn.commit()
    finally:
        conn.close()

    asyncio.run(init_db())

    assert (
        _count(
            db_path,
            f"SELECT COUNT(*) FROM {table} WHERE novel_id IS NOT NULL "
            f"AND novel_id NOT IN (SELECT id FROM novels)",
        )
        == 0
    )
