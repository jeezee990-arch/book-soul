"""Alembic env 配置（async + 我们自己的 engine）。

要点：
- 用 ``Base.metadata`` 作为 target_metadata（从 src.models 导入所有 model 后自动挂上）
- sqlalchemy.url 从 ``src.core.config.settings.db_path`` 动态构造
- 支持离线（offline）模式生成 SQL
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 触发模型注册
from src import models as _models  # noqa: F401
from src.core.config import settings
from src.models.base import Base

# 这是 Alembic Config 对象
config = context.config

# 注入真实 DB URL
_db_url = f"sqlite+aiosqlite:///{settings.db_path.as_posix()}"
config.set_main_option("sqlalchemy.url", _db_url)

# 解释 logging 配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据（所有 ORM 模型的元数据）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连 DB。"""
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式：连 DB 跑 migration。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
