"""API 路由包。"""

from fastapi import APIRouter

from .main import router as main_router

# 顶层聚合 router
router = APIRouter()
router.include_router(main_router)
