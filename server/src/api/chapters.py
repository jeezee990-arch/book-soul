"""章节 REST 端点（Phase 1.3）。

端点：
- POST   /novels/{novel_id}/chapters              创建（可选 content）
- GET    /novels/{novel_id}/chapters              列表（filter: status）
- GET    /chapters/{chapter_id}                   详情
- PATCH  /chapters/{chapter_id}                   部分更新（不含正文）
- DELETE /chapters/{chapter_id}                   删除（幂等，级联）
- POST   /chapters/{chapter_id}/content           写新版本（user_edit/rewrite/llm_generate）
- GET    /chapters/{chapter_id}/versions          版本历史
- GET    /chapters/{chapter_id}/versions/{vid}    单个版本

错误映射：
- ChapterNotFoundError / NovelNotFoundError -> 404
- ChapterValidationError / ChapterNumberConflictError -> 422
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.chapter import (
    ChapterContentUpdate,
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    ChapterVersionRead,
)
from ..services.chapter_service import (
    ChapterNotFoundError,
    ChapterNumberConflictError,
    ChapterService,
    ChapterValidationError,
    NovelNotFoundError,
)

router = APIRouter(tags=["chapters"])


def get_service(session: AsyncSession = Depends(get_db)) -> ChapterService:
    return ChapterService(session)


# ===== 嵌套在 novel 下的端点 =====
@router.post(
    "/novels/{novel_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
    summary="在某作品下创建章节（可选 content 写初始版本）",
)
async def create_chapter(
    novel_id: int,
    payload: ChapterCreate,
    service: ChapterService = Depends(get_service),
) -> ChapterRead:
    if payload.novel_id != novel_id:
        raise HTTPException(status_code=422, detail="novel_id in path and body must match")
    try:
        chapter = await service.create(payload)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ChapterValidationError, ChapterNumberConflictError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return ChapterRead.model_validate(chapter)


@router.get(
    "/novels/{novel_id}/chapters",
    response_model=list[ChapterRead],
    summary="列出某作品的章节（按 chapter_number 升序）",
)
async def list_chapters(
    novel_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ChapterService = Depends(get_service),
) -> list[ChapterRead]:
    try:
        await service._ensure_novel_exists(novel_id)
        chapters = await service.list_all(
            novel_id=novel_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ChapterValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [ChapterRead.model_validate(c) for c in chapters]


# ===== 顶层 chapter 端点 =====
chapter_router = APIRouter(tags=["chapters"])


@chapter_router.get(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    summary="获取章节详情",
)
async def get_chapter(
    chapter_id: int,
    service: ChapterService = Depends(get_service),
) -> ChapterRead:
    try:
        chapter = await service.get(chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChapterRead.model_validate(chapter)


@chapter_router.patch(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    summary="部分更新章节（title / outline / chapter_number / status）",
)
async def update_chapter(
    chapter_id: int,
    payload: ChapterUpdate,
    service: ChapterService = Depends(get_service),
) -> ChapterRead:
    try:
        chapter = await service.update(chapter_id, payload)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ChapterValidationError, ChapterNumberConflictError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return ChapterRead.model_validate(chapter)


@chapter_router.delete(
    "/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除章节（幂等，级联删 versions）",
)
async def delete_chapter(
    chapter_id: int,
    service: ChapterService = Depends(get_service),
) -> None:
    await service.delete(chapter_id)


@chapter_router.post(
    "/chapters/{chapter_id}/content",
    response_model=ChapterVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="写新版本（正文变更/重写/LLM 生成）",
)
async def update_chapter_content(
    chapter_id: int,
    payload: ChapterContentUpdate,
    service: ChapterService = Depends(get_service),
) -> ChapterVersionRead:
    try:
        version = await service.update_content(chapter_id, payload)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ChapterValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return ChapterVersionRead.model_validate(version)


@chapter_router.get(
    "/chapters/{chapter_id}/versions",
    response_model=list[ChapterVersionRead],
    summary="查看章节版本历史（按时间倒序）",
)
async def list_chapter_versions(
    chapter_id: int,
    service: ChapterService = Depends(get_service),
) -> list[ChapterVersionRead]:
    try:
        versions = await service.list_versions(chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [ChapterVersionRead.model_validate(v) for v in versions]


@chapter_router.get(
    "/chapters/{chapter_id}/versions/{version_id}",
    response_model=ChapterVersionRead,
    summary="获取单个版本",
)
async def get_chapter_version(
    chapter_id: int,
    version_id: int,
    service: ChapterService = Depends(get_service),
) -> ChapterVersionRead:
    try:
        version = await service.get_version(chapter_id, version_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ChapterVersionRead.model_validate(version)


# 合并两个 router
combined_router = APIRouter(tags=["chapters"])
combined_router.include_router(router)
combined_router.include_router(chapter_router)
