"""API 路由包。"""

from fastapi import APIRouter

from .backup import router as backup_router
from .chapter_generation import router as chapter_generation_router
from .chapter_versioning import router as chapter_versioning_router
from .chapters import combined_router as chapters_router
from .characters import combined_router as characters_router
from .chat import router as chat_router
from .export import router as export_router
from .inspirations import router as inspirations_router
from .llm import router as llm_router
from .main import router as main_router
from .novels import router as novels_router
from .outlines import generation_router
from .outlines import router as outlines_router
from .quality import router as quality_router
from .scanner import router as scanner_router
from .settings import router as settings_router
from .skills import router as skills_router
from .wordbanks import router as wordbanks_router

# 顶层聚合 router
router = APIRouter()
router.include_router(main_router)
router.include_router(llm_router)
router.include_router(novels_router)
router.include_router(characters_router)
router.include_router(chapters_router)
router.include_router(chapter_generation_router)
router.include_router(chapter_versioning_router)
router.include_router(outlines_router)
router.include_router(inspirations_router)
router.include_router(settings_router)
router.include_router(wordbanks_router)
router.include_router(export_router)
router.include_router(quality_router)
router.include_router(scanner_router)
router.include_router(skills_router)
router.include_router(backup_router)
router.include_router(chat_router)
router.include_router(generation_router)
