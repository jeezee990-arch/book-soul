"""API 路由包。"""

from fastapi import APIRouter

from .chapters import combined_router as chapters_router
from .characters import combined_router as characters_router
from .inspirations import router as inspirations_router
from .llm import router as llm_router
from .main import router as main_router
from .novels import router as novels_router
from .outlines import router as outlines_router
from .settings import router as settings_router

# 顶层聚合 router
router = APIRouter()
router.include_router(main_router)
router.include_router(llm_router)
router.include_router(novels_router)
router.include_router(characters_router)
router.include_router(chapters_router)
router.include_router(outlines_router)
router.include_router(inspirations_router)
router.include_router(settings_router)
