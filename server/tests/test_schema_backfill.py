"""启动时的**通用**补列机制（2026-10-29 巡检）。

背景
----
``Base.metadata.create_all`` **只建表，不加列**。既有库（用户已经在用）
缺后来新增的列 → ORM 查询直接报 ``no such column`` → 接口 500。

实测事故：``init_db`` 以前只硬编码补 ``inspirations`` 的三列，
结果 ``novels`` 后来新增的 ``outline_mode`` / ``file_path`` / ``imported`` /
``read_only`` 全都漏了 —— 旧库用户打开应用整个列表页 500。

现在改成**从 ORM 元数据自动推导**：任何表新增列，启动时自动补上。

这些测试不依赖 conftest 的 ``db_initialized`` —— 它们要自己造一个"旧 schema"的库。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

# 旧版 novels 表（缺 outline_mode / file_path / imported / read_only 四列）
OLD_NOVELS_DDL = """
CREATE TABLE novels (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    genre VARCHAR(50) NOT NULL,
    style VARCHAR(50),
    description VARCHAR(2000),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
)
"""

# 旧版 inspirations 表（缺 title / pinned / sort_order 三列）
OLD_INSPIRATIONS_DDL = """
CREATE TABLE inspirations (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER,
    type VARCHAR(20) NOT NULL,
    content JSON NOT NULL,
    source VARCHAR(50),
    tags JSON NOT NULL,
    created_at DATETIME NOT NULL
)
"""


def _table_cols(db_path: Path, table: str) -> set[str]:
    """读一张表的列名集合。"""
    conn = sqlite3.connect(db_path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _make_old_db(db_path: Path) -> None:
    """造一个"旧 schema"的库（表在、列少）。"""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(OLD_NOVELS_DDL)
        conn.execute(OLD_INSPIRATIONS_DDL)
        conn.execute(
            "INSERT INTO novels (name, genre, status, created_at, updated_at) "
            "VALUES ('旧书', 'xuanhuan', 'draft', '2026-01-01 00:00:00', "
            "'2026-01-01 00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()


def test_init_db_backfills_missing_columns(temp_db: Path) -> None:
    """init_db 要把 ORM 里有、旧库里没有的列全补上。"""
    import asyncio

    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _make_old_db(db_path)

    asyncio.run(init_db())

    novels_cols = _table_cols(db_path, "novels")
    assert "outline_mode" in novels_cols
    assert "file_path" in novels_cols
    assert "imported" in novels_cols
    assert "read_only" in novels_cols

    insp_cols = _table_cols(db_path, "inspirations")
    assert "title" in insp_cols
    assert "pinned" in insp_cols
    assert "sort_order" in insp_cols


def test_backfill_is_idempotent(temp_db: Path) -> None:
    """补列是幂等的：连跑两次不报错，列不重复。"""
    import asyncio

    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _make_old_db(db_path)

    asyncio.run(init_db())
    first = _table_cols(db_path, "novels")
    asyncio.run(init_db())
    second = _table_cols(db_path, "novels")

    assert first == second


def test_backfill_preserves_existing_rows(temp_db: Path) -> None:
    """补列不能把既有行的数据弄丢。"""
    import asyncio

    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _make_old_db(db_path)

    asyncio.run(init_db())

    conn = sqlite3.connect(db_path)
    try:
        rows = list(conn.execute("SELECT name, genre, status, imported, read_only FROM novels"))
    finally:
        conn.close()

    assert len(rows) == 1
    name, genre, status, imported, read_only = rows[0]
    assert name == "旧书"
    assert genre == "xuanhuan"
    assert status == "draft"
    # NOT NULL 且带默认值的列 → 既有行拿到默认值 0（不是 NULL）
    assert imported == 0
    assert read_only == 0


def test_backfill_not_null_column_gets_default(temp_db: Path) -> None:
    """NOT NULL + server_default 的列补上后，既有行必须是默认值。"""
    import asyncio

    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _make_old_db(db_path)

    asyncio.run(init_db())

    conn = sqlite3.connect(db_path)
    try:
        # imported 是 NOT NULL DEFAULT 0 —— 不能是 NULL
        bad = list(conn.execute("SELECT COUNT(*) FROM novels WHERE imported IS NULL"))
    finally:
        conn.close()

    assert bad[0][0] == 0


@pytest.mark.parametrize("table", ["novels", "inspirations"])
def test_no_missing_columns_after_init(temp_db: Path, table: str) -> None:
    """补列之后，ORM 里的每一列都必须在库里存在。"""
    import asyncio

    from src.db import init_db
    from src.models.base import Base

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _make_old_db(db_path)

    asyncio.run(init_db())

    existing = _table_cols(db_path, table)
    expected = {c.name for c in Base.metadata.tables[table].columns}
    assert expected <= existing


# ===== DDL 渲染一致性（2026-10-29 复核加固）=====
#
# 补列手拼的 DDL 必须与 SQLAlchemy ``CreateTable`` 的渲染一致，
# 否则同一个库里一张表是 create_all 建的、另一张是 ALTER 补的，
# ``sqlite_master.sql`` 文本对不上 → 将来做 schema diff 会误判成"列变了"。


def test_server_default_literal_matches_sqlalchemy_rendering() -> None:
    """字符串默认值要加单引号（与 SQLAlchemy 的 DEFAULT 'draft' 一致）。"""
    from src.db import _server_default_literal
    from src.models.base import Base

    novels = Base.metadata.tables["novels"].columns
    # server_default="draft" → SQLAlchemy 渲染成 DEFAULT 'draft'
    assert _server_default_literal(novels["status"]) == "'draft'"
    # server_default="0" → SQLAlchemy 渲染成 DEFAULT '0'
    assert _server_default_literal(novels["imported"]) == "'0'"
    # read_only 同样是 server_default="0"
    assert _server_default_literal(novels["read_only"]) == "'0'"

    insp = Base.metadata.tables["inspirations"].columns
    assert _server_default_literal(insp["pinned"]) == "'0'"
    assert _server_default_literal(insp["sort_order"]) == "'0'"


def test_column_ddl_matches_sqlalchemy_type() -> None:
    """补列用的类型名要和 SQLAlchemy 编译出来的一致。"""
    from src.db import _column_ddl
    from src.models.base import Base

    novels = Base.metadata.tables["novels"].columns
    assert _column_ddl(novels["status"]) == "VARCHAR(20) NOT NULL DEFAULT 'draft'"
    assert _column_ddl(novels["imported"]) == "BOOLEAN NOT NULL DEFAULT '0'"


def test_foreign_key_column_can_be_backfilled() -> None:
    """可空的外键列要能补上（SQLite 允许 ADD COLUMN 带 REFERENCES）。

    早先的实现把所有外键列都跳过 → 旧库缺该列时 ORM 报
    "no such column" → 接口 500，正是本机制要消灭的故障。
    """
    from src.db import _column_ddl
    from src.models.base import Base

    insp = Base.metadata.tables["inspirations"].columns
    assert insp["novel_id"].foreign_keys
    ddl = _column_ddl(insp["novel_id"])
    assert ddl is not None
    assert "REFERENCES novels(id)" in ddl
    # 可空列不能带 NOT NULL（SQLite 要求带 REFERENCES 的新列默认值为 NULL）
    assert "NOT NULL" not in ddl


def test_not_null_column_without_default_is_skipped() -> None:
    """NOT NULL 且没有 server_default 的列补不了 → 跳过（并由调用方记 error）。"""
    from src.db import _column_ddl
    from src.models.base import Base

    novels = Base.metadata.tables["novels"].columns
    # novels.name 是 NOT NULL 且没有 server_default
    assert novels["name"].nullable is False
    assert novels["name"].server_default is None
    assert _column_ddl(novels["name"]) is None


def test_text_clause_server_default_is_supported() -> None:
    """``server_default=sa.text("0")`` 要能渲染出字面量（早先是死代码）。"""
    from sqlalchemy import Column, Integer, text

    from src.db import _column_ddl, _server_default_literal

    col = Column("flag", Integer, nullable=False, server_default=text("0"))
    assert _server_default_literal(col) == "0"
    assert _column_ddl(col) == "INTEGER NOT NULL DEFAULT 0"


# ===== 补列失败不许拖垮启动 =====


class _FakeDialect:
    name = "sqlite"


class _FakeResult:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


class _FakeConn:
    """假连接：模拟"所有列都在，除了指定那一列"。

    :param missing: 要故意缺失的列，形如 ``("novels", "outline_mode")``
    :param fail_on: 执行到含此关键字的 SQL 时抛异常
    """

    def __init__(self, missing: tuple[str, str] | None = None, fail_on: str | None = None):
        from src.models.base import Base

        self.dialect = _FakeDialect()
        self._missing = missing
        self._fail_on = fail_on
        self.executed: list[str] = []
        self._all_cols: dict[str, list[str]] = {
            t.name: [c.name for c in t.columns] for t in Base.metadata.sorted_tables
        }
        if missing:
            table, col = missing
            self._all_cols[table] = [c for c in self._all_cols[table] if c != col]

    def exec_driver_sql(self, sql: str) -> _FakeResult:
        self.executed.append(sql)
        if self._fail_on and self._fail_on in sql:
            raise RuntimeError("simulated ALTER failure")
        if sql.startswith("PRAGMA table_info("):
            table = sql[len("PRAGMA table_info(") : -1]
            cols = self._all_cols.get(table, [])
            rows = [(i, c, "TEXT", 0, None, 0) for i, c in enumerate(cols)]
            return _FakeResult(rows)
        return _FakeResult([])


def test_backfill_failure_does_not_break_startup() -> None:
    """某一列补不上（ALTER 报错）时，只记日志，不抛异常 —— 应用必须能起来。"""
    from src.db import _ensure_missing_columns

    conn = _FakeConn(missing=("novels", "outline_mode"), fail_on="ADD COLUMN outline_mode")
    _ensure_missing_columns(conn)  # 不抛异常即通过

    # 确实尝试补了
    assert any("ADD COLUMN outline_mode" in s for s in conn.executed)


def test_backfill_skips_unsupported_columns_but_continues() -> None:
    """补不了的列（外键/PK）跳过，其余列照常补 —— 不能因为一列失败就全停。"""
    from src.db import _ensure_missing_columns

    conn = _FakeConn(missing=("novels", "outline_mode"))
    _ensure_missing_columns(conn)

    assert any("ADD COLUMN outline_mode" in s for s in conn.executed)


def test_locked_database_does_not_break_startup() -> None:
    """DB 被别的进程独占时，PRAGMA 抛 "database is locked" 也不能让后端起不来。

    早先的 try/except 只包了 ALTER，PRAGMA 在 try 外 ——
    实测会被 ``OperationalError: database is locked`` 打穿，直达
    ``init_db()`` → FastAPI lifespan → **整个后端启动失败**，
    而此时 create_all 其实已经成功、schema 是好的。
    """
    from src.db import _ensure_missing_columns

    conn = _FakeConn(missing=("novels", "outline_mode"), fail_on="PRAGMA table_info")
    _ensure_missing_columns(conn)  # 不抛异常即通过

    # 表读不到时不能瞎补列
    assert not any("ADD COLUMN" in s for s in conn.executed)


def test_real_sqlite_backfills_foreign_key_column(temp_db: Path) -> None:
    """端到端：旧库缺外键列时，真实 SQLite 要能补上，且带 REFERENCES 约束。

    这是 verifier 实证的故障链：
    旧库缺 ``inspirations.novel_id`` → 补列被跳过 → ORM 查这列报
    ``no such column`` → 整个灵感列表接口 500。
    """
    import asyncio

    from src.db import init_db

    db_path = temp_db
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 造一个**连外键列都没有**的旧 inspirations 表
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE inspirations (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                type VARCHAR(20) NOT NULL,
                content JSON NOT NULL,
                source VARCHAR(50),
                tags JSON NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    # 先确认旧库里确实没有 novel_id
    assert "novel_id" not in _table_cols(db_path, "inspirations")

    asyncio.run(init_db())

    # 补上了
    assert "novel_id" in _table_cols(db_path, "inspirations")

    # 真实 SQLite 接受带 REFERENCES 的 ADD COLUMN
    conn = sqlite3.connect(db_path)
    try:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='inspirations'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert "REFERENCES novels(id)" in ddl
