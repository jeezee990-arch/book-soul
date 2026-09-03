"""灵感 REST 端点（Phase 1.5）。

端点：
- POST   /inspirations              创建（novel_id 可空）
- GET    /inspirations              列表（filter: novel_id, type, tag）
- GET    /inspirations/{id}         详情
- PATCH  /inspirations/{id}         部分更新
- DELETE /inspirations/{id}         删除（幂等）

错误映射：
- InspirationNotFoundError / NovelNotFoundError -> 404
- InspirationValidationError -> 422
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.inspiration import (
    InspirationCreate,
    InspirationRead,
    InspirationUpdate,
)
from ..services.inspiration_service import (
    InspirationNotFoundError,
    InspirationService,
    InspirationValidationError,
    NovelNotFoundError,
)

router = APIRouter(prefix="/inspirations", tags=["inspirations"])


def get_service(session: AsyncSession = Depends(get_db)) -> InspirationService:
    return InspirationService(session)


@router.post(
    "",
    response_model=InspirationRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建灵感（novel_id 可空，content 按 type 校验）",
)
async def create_inspiration(
    payload: InspirationCreate,
    service: InspirationService = Depends(get_service),
) -> InspirationRead:
    try:
        inspiration = await service.create(payload)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InspirationValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return InspirationRead.model_validate(inspiration)


@router.get(
    "",
    response_model=list[InspirationRead],
    summary="列出灵感（filter: novel_id, type, tag）",
)
async def list_inspirations(
    novel_id: int | None = Query(default=None, description="按作品 id 过滤（None=仅通用）"),
    type_filter: str | None = Query(default=None, alias="type", description="按类型过滤"),
    tag: str | None = Query(default=None, description="按 tag 过滤（精确匹配）"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: InspirationService = Depends(get_service),
) -> list[InspirationRead]:
    try:
        inspirations = await service.list_all(
            novel_id=novel_id,
            inspiration_type=type_filter,
            tag=tag,
            limit=limit,
            offset=offset,
        )
    except InspirationValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [InspirationRead.model_validate(i) for i in inspirations]


@router.get(
    "/{inspiration_id}",
    response_model=InspirationRead,
    summary="获取灵感详情",
)
async def get_inspiration(
    inspiration_id: int,
    service: InspirationService = Depends(get_service),
) -> InspirationRead:
    try:
        inspiration = await service.get(inspiration_id)
    except InspirationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return InspirationRead.model_validate(inspiration)


@router.patch(
    "/{inspiration_id}",
    response_model=InspirationRead,
    summary="部分更新灵感",
)
async def update_inspiration(
    inspiration_id: int,
    payload: InspirationUpdate,
    service: InspirationService = Depends(get_service),
) -> InspirationRead:
    try:
        inspiration = await service.update(inspiration_id, payload)
    except InspirationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InspirationValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return InspirationRead.model_validate(inspiration)


@router.delete(
    "/{inspiration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除灵感（幂等）",
)
async def delete_inspiration(
    inspiration_id: int,
    service: InspirationService = Depends(get_service),
) -> None:
    try:
        await service.delete(inspiration_id)
    except InspirationNotFoundError:
        return  # 幂等
