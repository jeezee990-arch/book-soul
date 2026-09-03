"""共享 pytest fixtures。

- ``temp_db``：把数据目录切到 tmp_path，强制重建 src.* 模块（让 engine 用新路径）。
  Phase 0 的 test_db_init.py 也使用这个 fixture（从 inline 升级而来）。
- ``db_initialized``：基于 temp_db，调 init_db 建表（Phase 1 起 service 测试用）。
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture
def temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """把数据目录切到 tmp_path，强制重建 src.* 模块（让 engine 用新路径）。"""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("BOOK_SOUL_DATA_DIR", str(data_dir))

    # 卸载 src.* 全部子模块，让下次 import 时按新 env 重新构造
    to_remove = [name for name in sys.modules if name == "src" or name.startswith("src.")]
    for name in to_remove:
        del sys.modules[name]

    yield data_dir / "book-soul.db"

    # teardown：尝试清理 engine，避免事件循环冲突时静默跳过
    try:
        import asyncio

        from src import db as db_mod  # noqa: PLC0415

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return
            loop.run_until_complete(db_mod.engine.dispose())
        except RuntimeError:
            pass
    except Exception:  # noqa: BLE001
        pass


@pytest_asyncio.fixture
async def db_initialized(temp_db: Path) -> AsyncIterator[Path]:
    """在 temp_db 基础上跑 init_db 建表，返回 db 文件路径。"""
    from src.db import init_db  # noqa: PLC0415

    await init_db()
    yield temp_db
