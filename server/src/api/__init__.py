"""API 路由包。"""

from fastapi import APIRouter

from .characters import combined_router as characters_router
from .llm import router as llm_router
from .main import router as main_router
from .novels import router as novels_router

# 顶层聚合 router
router = APIRouter()
router.include_router(main_router)
router.include_router(llm_router)
router.include_router(novels_router)
router.include_router(characters_router)
