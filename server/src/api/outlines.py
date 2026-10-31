"""大纲 REST 端点（Phase 1.4 + Phase 3.4 生成）。

端点（全部嵌套在 novel 下，outline 强绑定 novel）：
- POST   /novels/{novel_id}/outlines              创建
- GET    /novels/{novel_id}/outlines              列表（filter: outline_type）
- GET    /novels/{novel_id}/outlines/{oid}        详情
- PATCH  /novels/{novel_id}/outlines/{oid}        部分更新
- DELETE /novels/{novel_id}/outlines/{oid}        删除（幂等）

Phase 3.4：基于剧情生成大纲（自动建 novel + 生成 + 入库）
- POST   /novels/outlines/generate                生成大纲（不入参 novel_id）

错误映射：
- OutlineNotFoundError / NovelNotFoundError -> 404
- OutlineValidationError / OutlineTypeConflictError -> 422
- OutlineGenerationError -> 500（LLM 失败）/ 422（结构错）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.outline import (
    OutlineContinueRequest,
    OutlineCreate,
    OutlineGenerationRequest,
    OutlineGenerationResponse,
    OutlineRead,
    OutlineUpdate,
)
from ..services.outline_continuation import OutlineContinuationService
from ..services.outline_generator import (
    OutlineGenerationError,
    OutlineGenerator,
)
from ..services.outline_service import (
    NovelNotFoundError,
    OutlineNotFoundError,
    OutlineService,
    OutlineTypeConflictError,
    OutlineValidationError,
)
from ._stream_helpers import ndjson_line, ndjson_response

router = APIRouter(prefix="/novels/{novel_id}/outlines", tags=["outlines"])


def get_service(session: AsyncSession = Depends(get_db)) -> OutlineService:
    return OutlineService(session)


@router.post(
    "",
    response_model=OutlineRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建大纲（complete / freedom）",
)
async def create_outline(
    novel_id: int,
    payload: OutlineCreate,
    service: OutlineService = Depends(get_service),
) -> OutlineRead:
    if payload.novel_id != novel_id:
        raise HTTPException(status_code=422, detail="novel_id in path and body must match")
    try:
        outline = await service.create(payload)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (OutlineValidationError, OutlineTypeConflictError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return OutlineRead.model_validate(outline)


@router.get(
    "",
    response_model=list[OutlineRead],
    summary="列出某作品的大纲（可按 type 过滤）",
)
async def list_outlines(
    novel_id: int,
    outline_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: OutlineService = Depends(get_service),
) -> list[OutlineRead]:
    try:
        await service._ensure_novel_exists(novel_id)
        outlines = await service.list_all(
            novel_id=novel_id,
            outline_type=outline_type,
            limit=limit,
            offset=offset,
        )
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OutlineValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [OutlineRead.model_validate(o) for o in outlines]


@router.get(
    "/{outline_id}",
    response_model=OutlineRead,
    summary="获取大纲详情",
)
async def get_outline(
    novel_id: int,
    outline_id: int,
    service: OutlineService = Depends(get_service),
) -> OutlineRead:
    try:
        outline = await service.get(outline_id)
    except OutlineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if outline.novel_id != novel_id:
        # 大纲存在但不属于该作品 → 404
        raise HTTPException(status_code=404, detail=f"Outline {outline_id} not in novel {novel_id}")
    return OutlineRead.model_validate(outline)


@router.patch(
    "/{outline_id}",
    response_model=OutlineRead,
    summary="部分更新大纲",
)
async def update_outline(
    novel_id: int,
    outline_id: int,
    payload: OutlineUpdate,
    service: OutlineService = Depends(get_service),
) -> OutlineRead:
    try:
        outline = await service.get(outline_id)
        if outline.novel_id != novel_id:
            raise OutlineNotFoundError(outline_id)
        updated = await service.update(outline_id, payload)
    except OutlineNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OutlineValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return OutlineRead.model_validate(updated)


@router.delete(
    "/{outline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除大纲（幂等，不存在或不属于该作品都返 204）",
)
async def delete_outline(
    novel_id: int,
    outline_id: int,
    service: OutlineService = Depends(get_service),
) -> None:
    try:
        outline = await service.get(outline_id)
    except OutlineNotFoundError:
        return  # 不存在 → 幂等 204
    if outline.novel_id != novel_id:
        return  # 不属于该作品 → 幂等 204
    await service.delete(outline_id)


# ===== AI 辅助续写大纲（基于已有大纲 + 已写章节）=====


@router.post(
    "/{outline_id}/continue/stream",
    summary="AI 辅助续写大纲（ndjson；新增卷追加到原大纲末尾）",
)
async def continue_outline_stream(
    novel_id: int,
    outline_id: int,
    payload: OutlineContinueRequest,
    session: AsyncSession = Depends(get_db),
):
    """续写已有大纲：接着已写章节往下生成后续卷章。

    ⚠️ 前置校验放在**开流之前** —— 流一旦开始，HTTP 状态码就锁死了，
    错误只能塞进流内（前端要能区分"请求没发出去"和"生成到一半失败"）。
    """
    from ..models.outline import Outline

    outline = await session.get(Outline, outline_id)
    if outline is None or outline.novel_id != novel_id:
        raise HTTPException(status_code=404, detail=f"Outline {outline_id} not found")
    if outline.outline_type == "freedom":
        raise HTTPException(status_code=422, detail="创作型大纲（freedom）不支持续写")

    service = OutlineContinuationService(session)

    async def gen():
        async for event in service.stream_continue(
            novel_id,
            outline_id,
            volume_count=payload.volume_count,
            chapters_per_volume=payload.chapters_per_volume,
            words_per_chapter=payload.words_per_chapter,
            keywords=payload.keywords,
            user_extra=payload.user_extra,
        ):
            yield ndjson_line(event)

    return ndjson_response(gen())


# ===== Phase 3.4：基于剧情生成大纲（自动建 novel）=====

# 独立 router（不嵌在 novel_id 路径下，因为 novel 是自动建的）
generation_router = APIRouter(prefix="/novels/outlines", tags=["outlines"])


def get_generator(session: AsyncSession = Depends(get_db)) -> OutlineGenerator:
    return OutlineGenerator(session)


@generation_router.post(
    "/generate",
    response_model=OutlineGenerationResponse,
    summary="基于剧情生成大纲（自动建 novel + 调 LLM + 入库）",
)
async def generate_outline(
    payload: OutlineGenerationRequest,
    generator: OutlineGenerator = Depends(get_generator),
) -> OutlineGenerationResponse:
    try:
        result = await generator.generate(
            genre=payload.genre,
            plot_summary=payload.plot_summary,
            keywords=payload.keywords or [],
            novel_name=payload.novel_name,
            novel_id=payload.novel_id,
            outline_type=payload.outline_type,
            user_extra=payload.user_extra,
            total_chapters=payload.total_chapters,
            chapters_per_volume=payload.chapters_per_volume,
            words_per_chapter=payload.words_per_chapter,
        )
    except OutlineGenerationError as e:
        # LLM 失败 / 结构错 → 500（业务可重试）；参数错由 Pydantic 422 拦
        raise HTTPException(status_code=500, detail=str(e)) from e
    return OutlineGenerationResponse(**result)


@generation_router.post(
    "/generate/stream",
    summary="流式生成大纲（ndjson；token 实时 + 最后入库）",
)
async def generate_outline_stream(
    payload: OutlineGenerationRequest,
    generator: OutlineGenerator = Depends(get_generator),
):
    """流式端点：边生成边推 token；解析 + 入库在最后完成。

    协议见 :mod:`src.api._stream_helpers`。
    """

    async def gen():
        async for event in generator.stream_generate(
            genre=payload.genre,
            plot_summary=payload.plot_summary,
            keywords=payload.keywords or [],
            novel_name=payload.novel_name,
            novel_id=payload.novel_id,
            outline_type=payload.outline_type,
            user_extra=payload.user_extra,
            total_chapters=payload.total_chapters,
            chapters_per_volume=payload.chapters_per_volume,
            words_per_chapter=payload.words_per_chapter,
        ):
            yield ndjson_line(event)

    return ndjson_response(gen())
