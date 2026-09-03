"""API 路由包。"""

from fastapi import APIRouter

from .llm import router as llm_router
from .main import router as main_router

# 顶层聚合 router
router = APIRouter()
router.include_router(main_router)
router.include_router(llm_router)
