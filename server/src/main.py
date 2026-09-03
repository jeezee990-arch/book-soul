"""Book Soul 后端服务入口。

启动方式（在 ``server/`` 目录下）：
    uv run python -m src.main

或者（项目根目录）：
    uv run --directory server python -m src.main
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from .api import router as api_router
from .core.config import settings
from .db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时初始化 DB，关闭时记录日志。"""
    logger.info("Starting Book Soul server (host={}, port={})", settings.book_soul_host, settings.book_soul_port)
    await init_db()
    try:
        yield
    finally:
        logger.info("Shutting down Book Soul server")


app = FastAPI(
    title="Book Soul",
    description="AI 辅助小说写作桌面应用 - 后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

# 挂载 API 路由
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.book_soul_host,
        port=settings.book_soul_port,
        reload=False,
    )
