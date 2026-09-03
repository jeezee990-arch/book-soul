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


async def init_db() -> None:
    """应用启动时调用：准备数据目录 + 创建表 + 校验连接。

    Phase 0 阶段用 ``Base.metadata.create_all`` 兜底（首次启动建表）。
    Phase 1 起改走 alembic migration。
    """
    data_dir = _ensure_data_dir()
    logger.info("DB init: data_dir={}, db_path={}", data_dir, settings.db_path)

    # 1) 创建表（仅对未存在的；已存在则忽略）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
