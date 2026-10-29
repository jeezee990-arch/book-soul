"""数据库初始化与引擎管理。

模块 0.6 起：
- 暴露 ``engine`` / ``SessionLocal`` / ``Base``
- ``init_db()`` 创建 ``Base.metadata`` 里的所有表（首次启动）
- 后续 schema 变更走 alembic（``alembic upgrade head``）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from loguru import logger
from sqlalchemy import Column, event
from sqlalchemy.dialects import sqlite
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql.elements import TextClause

# 触发模型注册（每个 model 文件 import 后会被挂到 Base.metadata）
from . import models as _models  # noqa: F401
from .core.config import settings
from .models.base import Base

# ===== 引擎与 Session 工厂 =====
# 路径必须用绝对路径，并把 Windows 反斜杠转成 aiosqlite 能识别的正斜杠
_DB_URL = f"sqlite+aiosqlite:///{settings.db_path.as_posix()}"

engine = create_async_engine(
    _DB_URL,
    echo=False,
    future=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """打开 SQLite 的外键约束（SQLite **默认是关的**）。

    为什么必须开（2026-10-29 实测事故）
    ----------------------------------
    SQLite 为了历史兼容，``PRAGMA foreign_keys`` 默认为 **OFF**。
    关着的时候，ORM 里写的 ``ondelete="CASCADE"`` / ``"SET NULL"``
    **完全不生效** —— 删掉一本作品，它的章节、人物卡、大纲全留在库里。

    更糟的是 SQLite 会**复用**被删掉的最大 id（模型里的 id 没有
    ``AUTOINCREMENT``），于是"重建作品"会拿到同一个 id，
    上一部作品遗留的章节就**串进了新作品**：

    实测：删掉 novel 4 → 重建得到 novel 4 → 建章节直接 422
    ``Chapter number 1 already exists in novel 4``
    （冲突的是**上一部作品**留下的章节）。

    开启约束后，删作品会级联清掉子表，不再留孤儿、不再串号。
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _ensure_data_dir() -> Path:
    """确保数据目录存在。"""
    data_dir = settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# ===== 幂等补列（2026-10-29）=====
#
# 背景：``Base.metadata.create_all`` **只建表，不加列**。既有库（用户已经在用）
# 的表缺少后来新增的列，光靠 create_all 补不上，ORM 查这列会直接报
# "no such column" —— 整个接口 500。
#
# ⚠️ 这里**不硬编码**要补哪几列，而是**从 ORM 元数据自动推导**：
#   任何表新增列 → 启动时自动补上，不用记得回来改这里。
#   （以前只硬编码了 inspirations 的三列，结果 novels 新增的
#    outline_mode / file_path / imported / read_only 全都漏了，
#    旧库用户打开应用直接 500 —— 2026-10-29 巡检实测。）
#
# ⚠️ SQLite **不支持** ``ADD COLUMN IF NOT EXISTS``，必须先查列再决定要不要 ALTER。
#
# SQLite 的 ``ALTER TABLE ADD COLUMN`` 限制：
# - 不能加 PRIMARY KEY / UNIQUE 列（会重建表）
# - NOT NULL 列必须带非空默认值
# 违反这两条的列**跳过并告警**（宁可不加，也不能让启动失败）。


def _sqlite_type_ddl(col: Column) -> str:
    """把 ORM 列类型编译成 SQLite 的 DDL 类型片段。

    :param col: ORM 列
    :return: DDL 类型名（``VARCHAR`` / ``INTEGER`` / ``BOOLEAN`` …）
    """
    return col.type.compile(dialect=sqlite.dialect())


def _server_default_literal(col: Column) -> str | None:
    """取列的 server_default 字面量（用于 ``NOT NULL`` 列补列）。

    渲染规则**必须与 SQLAlchemy 的 ``CreateTable`` 一致**，否则同一个库里
    一张表是 ``create_all`` 建的（``DEFAULT 'draft'``）、另一张是 ALTER 补的
    （``DEFAULT draft``），``sqlite_master.sql`` 文本对不上，将来做 schema
    diff 会误判成"列变了"。

    :param col: ORM 列
    :return: SQL 字面量（如 ``0`` / ``'draft'``）；没有可用默认值时返回 None
    """
    default = col.server_default
    if default is None:
        return None
    # ``DefaultClause('0', for_update=False)`` → 取它的 arg（Python 值）
    arg = getattr(default, "arg", None)
    if arg is None:
        return None
    # ``server_default=sa.text("0")`` → arg 是 TextClause，本身就是 SQL 片段，
    # 原样输出（不能加引号）。注意 DefaultClause **没有** .text 属性，
    # 早先按 .text 取值的那一分支永远不命中（死代码）。
    if isinstance(arg, TextClause):
        return str(arg.text)
    # bool 要先判（``isinstance(True, int)`` 为真）
    if isinstance(arg, bool):
        return "1" if arg else "0"
    if isinstance(arg, (int, float)):
        return str(arg)
    if isinstance(arg, str):
        # 字符串加单引号并转义内部单引号（与 SQLAlchemy 渲染一致）
        return "'" + arg.replace("'", "''") + "'"
    return None


def _foreign_key_ref(col: Column) -> str:
    """取列的外键引用片段（`` REFERENCES novels(id)``）。

    SQLite 的 ``ALTER TABLE ADD COLUMN`` **允许**加带 REFERENCES 的列，
    前提是该列默认值是 NULL（否则 SQLite 直接报错）。
    所以可空的外键列能正常补上，列本身带 REFERENCES 约束。

    ⚠️ SQLAlchemy 的 ``target_fullname`` 是点号形式（``novels.id``），
    而 SQLite 的 REFERENCES 语法要的是 ``novels(id)`` —— 必须转换，
    否则 ALTER 会报语法错误。

    :param col: ORM 列
    :return: DDL 片段；没有外键时返回空串
    """
    if not col.foreign_keys:
        return ""
    fk = list(col.foreign_keys)[0]
    target = fk.target_fullname
    if "." in target:
        table_name, column_name = target.rsplit(".", 1)
        return f" REFERENCES {table_name}({column_name})"
    return f" REFERENCES {target}"


def _column_ddl(col: Column) -> str | None:
    """拼一列的 DDL 片段；不能安全补列时返回 None。

    :param col: ORM 列
    :return: DDL 片段；补不了时返回 None
    """
    if col.primary_key or col.unique:
        # SQLite 的 ADD COLUMN 不支持 PRIMARY KEY / UNIQUE
        # （UNIQUE 隐含唯一索引，加不上）
        return None
    ddl = _sqlite_type_ddl(col)
    if col.nullable:
        # 可空列：类型 + 外键引用（外键列必须是可空的，
        # SQLite 要求"带 REFERENCES 的新列默认值必须是 NULL"）
        return ddl + _foreign_key_ref(col)
    literal = _server_default_literal(col)
    if literal is None:
        # NOT NULL 又没有默认值 → 加了会把既有行填成 NULL（SQLite 直接报错）
        # ⚠️ 本项目主流写法是 NOT NULL 且**没有** server_default
        # （novels.name / characters.role / outlines.structure …）。
        # 那些列是建表时就有的，不会成为"缺失列"；
        # 但**将来新增** NOT NULL 列时必须同时加 server_default，
        # 否则旧库永远补不上 → ORM 报 no such column → 接口 500。
        return None
    # NOT NULL 列不能带 REFERENCES（SQLite 限制），只给类型 + 默认值
    return f"{ddl} NOT NULL DEFAULT {literal}"


def _ensure_missing_columns(sync_conn) -> None:
    """给既有表补上 ORM 里新增的列（幂等、通用）。

    在同步连接上跑（``conn.run_sync``），这样可以直接用同步 API 读 PRAGMA 结果。

    只针对 SQLite —— 其他方言交给 alembic 处理。

    :param sync_conn: 同步 SQLAlchemy 连接
    """
    if sync_conn.dialect.name != "sqlite":
        return
    for table in Base.metadata.sorted_tables:
        # ⚠️ PRAGMA 也要保护：DB 文件被另一进程独占（另一个实例、
        # 杀软扫描、备份工具）时，PRAGMA 会抛 "database is locked"。
        # 这时 create_all 其实已经成功、schema 是好的 —— 补列只是锦上添花，
        # 不能因为读不到列信息就让整个后端起不来。
        try:
            rows = sync_conn.exec_driver_sql(f"PRAGMA table_info({table.name})").fetchall()
        except Exception as e:  # noqa: BLE001
            logger.error(
                "DB schema upgrade: cannot inspect table {} ({}), skipping",
                table.name,
                e,
            )
            continue
        if not rows:
            # 表还没建（create_all 之后不该出现，保险起见直接跳过）
            continue
        existing = {r[1] for r in rows}
        for col in table.columns:
            if col.name in existing:
                continue
            ddl = _column_ddl(col)
            if ddl is None:
                # ⚠️ error 而不是 warning：这一列永远补不上 → ORM 查这列会报
                # "no such column" → 接口 500。必须让开发者看见。
                logger.error(
                    "DB schema upgrade: CANNOT backfill {}.{} "
                    "(SQLite 不能安全地补这一列：NOT NULL 且没有 server_default / "
                    "PRIMARY KEY / UNIQUE)。该列在旧库中会一直缺失，"
                    "请给模型加 server_default 或走 alembic 迁移。",
                    table.name,
                    col.name,
                )
                continue
            # 迁移层补列允许原生 SQL（业务层禁字符串拼接，这里是 DDL 不是查询）
            try:
                sync_conn.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}")
            except Exception as e:  # noqa: BLE001
                # 补列失败不能拖垮启动（"宁可不加，也不能让应用起不来"）
                logger.error(
                    "DB schema upgrade: failed to add {}.{} ({})",
                    table.name,
                    col.name,
                    e,
                )
                continue
            logger.info("DB schema upgrade: added {}.{} column", table.name, col.name)


def _purge_orphan_rows(sync_conn) -> None:
    """清理"父行已删"的历史遗留孤儿行。

    外键约束是**后来**才打开的，之前删掉的作品留下的子行还躺在库里。
    这些行在任何列表里都看不到（所有查询都按 ``novel_id`` 过滤），
    但会造成两个麻烦：

    1. SQLite 复用被删掉的作品 id 时，旧章节会**串进新作品**；
    2. 数据库无限膨胀。

    处理规则按外键的 ``ondelete`` 语义走（从 ORM 元数据自动推导，不硬编码）：

    - ``CASCADE``：父行没了子行也没意义 → **删掉**
    - ``SET NULL``：父行没了只该脱离关系，**数据本身要保留** → 置 NULL
      （例如 ``inspirations.novel_id`` —— 素材是用户写的，不能因为
      删了作品就一起删掉）

    :param sync_conn: 同步 SQLAlchemy 连接
    """
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                parent = fk.column.table
                ondelete = (fk.ondelete or "").upper()
                if ondelete == "CASCADE":
                    sql = (
                        f"DELETE FROM {table.name} "
                        f"WHERE {col.name} IS NOT NULL "
                        f"AND {col.name} NOT IN (SELECT id FROM {parent.name})"
                    )
                elif ondelete == "SET NULL":
                    sql = (
                        f"UPDATE {table.name} SET {col.name} = NULL "
                        f"WHERE {col.name} IS NOT NULL "
                        f"AND {col.name} NOT IN (SELECT id FROM {parent.name})"
                    )
                else:
                    continue
                result = sync_conn.exec_driver_sql(sql)
                removed = result.rowcount or 0
                if removed:
                    logger.info(
                        "DB cleanup: purged {} orphan row(s) in {}.{}",
                        removed,
                        table.name,
                        col.name,
                    )


async def init_db() -> None:
    """应用启动时调用：准备数据目录 + 创建表 + 补列 + 校验连接。

    Phase 0 阶段用 ``Base.metadata.create_all`` 兜底（首次启动建表）。
    Phase 1 起改走 alembic migration；但 alembic 未接入启动流程，
    所以这里额外做一次**幂等补列**，保证既有库不会因为缺列而崩。
    """
    data_dir = _ensure_data_dir()
    logger.info("DB init: data_dir={}, db_path={}", data_dir, settings.db_path)

    # 1) 创建表（仅对未存在的；已存在则忽略）+ 幂等补列 + 清孤儿
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.run_sync(_ensure_missing_columns)
        except Exception as e:  # noqa: BLE001
            # 补列是"锦上添花"：create_all 已经建好表了，
            # 补列失败只影响"旧库缺新列"这一个场景，不能让整个应用起不来。
            logger.error("DB schema upgrade: backfill failed ({})", e)
        try:
            await conn.run_sync(_purge_orphan_rows)
        except Exception as e:  # noqa: BLE001
            logger.error("DB cleanup: purge orphans failed ({})", e)
    logger.info("DB tables ready: {}", list(Base.metadata.tables))

    # 2) 校验连接
    try:
        async with engine.connect() as conn:
            await conn.run_sync(lambda _sync_conn: None)
        logger.info("DB engine OK: {}", _DB_URL)
    except Exception as e:  # noqa: BLE001
        logger.error("DB engine failed: {}", e)
        raise


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """便捷 session 上下文管理器（业务/测试代码用 ``async with`` 块即可）。"""
    async with SessionLocal() as session:
        yield session


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI yield-based dependency。

    不用 ``@asynccontextmanager``：包装后的 ``_AsyncGeneratorContextManager`` 类型
    不支持 FastAPI 依赖注入系统的迭代协议。改成普通 async generator，
    FastAPI 的 ``Depends(get_db)`` 会自动按 generator-based dependency 处理。

    调用方仍用 ``async with SessionLocal()`` 模式；``Depends(get_db)`` 自动关闭。
    """
    async with SessionLocal() as session:
        yield session
