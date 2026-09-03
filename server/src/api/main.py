"""顶层 API 路由注册（健康检查 / ping）。"""

from __future__ import annotations

from fastapi import APIRouter
from loguru import logger

from ..core.config import settings

router = APIRouter(tags=["health"])


@router.get("/ping", summary="健康检查")
async def ping() -> dict[str, str]:
    """返回服务状态。

    阶段 0 端点：仅用于验证 FastAPI 启动正常。
    """
    logger.debug("ping hit")
    return {
        "status": "ok",
        "app": "book-soul",
        "host": settings.book_soul_host,
        "port": str(settings.book_soul_port),
    }
