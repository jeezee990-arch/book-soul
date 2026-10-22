"""顶层 API 路由注册（健康检查 / ping）。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from loguru import logger

from ..core.config import settings

router = APIRouter(tags=["health"])


@router.get("/ping", summary="健康检查")
async def ping(request: Request) -> dict[str, str]:
    """返回服务状态。

    阶段 0 端点：仅用于验证 FastAPI 启动正常。

    注意：回报的是**实际绑定端口**，不是配置里的默认端口。
    桌面版由 Tauri 分配随机端口，配置值与实际值可能不同。
    """
    logger.debug("ping hit")
    port = getattr(request.app.state, "actual_port", settings.book_soul_port)
    return {
        "status": "ok",
        "app": "book-soul",
        "host": settings.book_soul_host,
        "port": str(port),
    }
