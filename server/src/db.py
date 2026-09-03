"""数据库初始化与引擎管理。

Phase 0 阶段只做：
- 解析数据目录
- 准备 SQLite 数据库文件
- 暴露 ``engine`` 和 ``SessionLocal`` 工厂

实际的表结构由 Phase 1 的 models/ 提供，Phase 1 会补充 ``Base.metadata.create_all``。
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

from .core.config import settings

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
    """应用启动时调用：准备数据目录，校验 DB 可达。

    Phase 0 阶段不创建表（表模型在 Phase 1 引入）。仅验证目录与连接。
    """
    data_dir = _ensure_data_dir()
    logger.info("DB init: data_dir={}, db_path={}", data_dir, settings.db_path)

    # 试探一次连接（不执行 SQL，只确认引擎可用）
    try:
        async with engine.connect() as conn:
            await conn.run_sync(lambda _sync_conn: None)
        logger.info("DB engine OK: {}", _DB_URL)
    except Exception as e:  # noqa: BLE001
        logger.error("DB engine failed: {}", e)
        raise


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """便捷 session 上下文管理器（业务代码用 with 块即可）。"""
    async with SessionLocal() as session:
        yield session
