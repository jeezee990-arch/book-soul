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
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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


def _ensure_data_dir() -> Path:
    """确保数据目录存在。"""
    data_dir = settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# ===== 幂等补列（2026-10-29 素材库管理）=====
#
# 背景：``Base.metadata.create_all`` **只建表，不加列**。既有库（用户已经在用）
# 的 inspirations 表没有 title / pinned / sort_order 三列，光靠 create_all 补不上，
# ORM 查这列会直接报 "no such column"。
#
# 两条路都留着：
# 1. alembic 0007（``alembic upgrade head`` 时执行）
# 2. 这里的幂等补列（启动时自动执行 —— alembic 目前**没接入启动流程**）
#
# ⚠️ SQLite **不支持** ``ADD COLUMN IF NOT EXISTS``，必须先查列再决定要不要 ALTER。
_INSPIRATION_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("title", "VARCHAR(200)"),
    ("pinned", "BOOLEAN NOT NULL DEFAULT 0"),
    ("sort_order", "INTEGER NOT NULL DEFAULT 0"),
)


def _ensure_inspiration_columns(sync_conn) -> None:
    """给既有 inspirations 表补上缺失的列（幂等）。

    在同步连接上跑（``conn.run_sync``），这样可以直接用同步 API 读 PRAGMA 结果。

    只针对 SQLite —— 其他方言交给 alembic 处理。
    """
    if sync_conn.dialect.name != "sqlite":
        return
    rows = sync_conn.exec_driver_sql("PRAGMA table_info(inspirations)").fetchall()
    existing = {row[1] for row in rows}
    if not existing:
        # 表还没建（create_all 之后不该出现，保险起见直接跳过）
        return
    for name, ddl in _INSPIRATION_ADDED_COLUMNS:
        if name in existing:
            continue
        # 迁移层补列允许原生 SQL（业务层禁字符串拼接，这里是 DDL 不是查询）
        sync_conn.exec_driver_sql(f"ALTER TABLE inspirations ADD COLUMN {name} {ddl}")
        logger.info("DB schema upgrade: added inspirations.{} column", name)


async def init_db() -> None:
    """应用启动时调用：准备数据目录 + 创建表 + 补列 + 校验连接。

    Phase 0 阶段用 ``Base.metadata.create_all`` 兜底（首次启动建表）。
    Phase 1 起改走 alembic migration；但 alembic 未接入启动流程，
    所以这里额外做一次**幂等补列**，保证既有库不会因为缺列而崩。
    """
    data_dir = _ensure_data_dir()
    logger.info("DB init: data_dir={}, db_path={}", data_dir, settings.db_path)

    # 1) 创建表（仅对未存在的；已存在则忽略）+ 幂等补列
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_inspiration_columns)
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
