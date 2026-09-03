"""人物卡 REST 端点（Phase 1.2）。

端点：
- POST   /novels/{novel_id}/characters                  创建
- GET    /novels/{novel_id}/characters                  列表（filter: role, is_active）
- GET    /characters/{character_id}                     详情
- PATCH  /characters/{character_id}                     部分更新
- DELETE /characters/{character_id}                     删除（幂等）
- POST   /characters/{character_id}/growth              记录性格变化
- GET    /characters/{character_id}/versions            版本历史
- GET    /characters/{character_id}/versions/{vid}      单个版本

错误映射：
- CharacterNotFoundError / NovelNotFoundError -> 404
- CharacterValidationError -> 422
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.character import (
    CharacterCreate,
    CharacterGrowthUpdate,
    CharacterRead,
    CharacterUpdate,
    CharacterVersionRead,
)
from ..services.character_service import (
    CharacterNotFoundError,
    CharacterService,
    CharacterValidationError,
    NovelNotFoundError,
)

router = APIRouter(tags=["characters"])


def get_service(session: AsyncSession = Depends(get_db)) -> CharacterService:
    return CharacterService(session)


# ===== 嵌套在 novel 下的端点 =====
@router.post(
    "/novels/{novel_id}/characters",
    response_model=CharacterRead,
    status_code=status.HTTP_201_CREATED,
    summary="在某作品下创建人物卡",
)
async def create_character(
    novel_id: int,
    payload: CharacterCreate,
    service: CharacterService = Depends(get_service),
) -> CharacterRead:
    if payload.novel_id != novel_id:
        # 路径和 body 不一致 → 422
        raise HTTPException(status_code=422, detail="novel_id in path and body must match")
    try:
        character = await service.create(payload)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CharacterValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return CharacterRead.model_validate(character)


@router.get(
    "/novels/{novel_id}/characters",
    response_model=list[CharacterRead],
    summary="列出某作品的人物卡（可按 role/is_active 过滤）",
)
async def list_characters(
    novel_id: int,
    role: str | None = Query(default=None, description="按角色定位过滤"),
    is_active: bool | None = Query(default=None, description="按活跃状态过滤"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CharacterService = Depends(get_service),
) -> list[CharacterRead]:
    try:
        # 校验作品存在
        await service._ensure_novel_exists(novel_id)
        characters = await service.list_all(
            novel_id=novel_id, role=role, is_active=is_active, limit=limit, offset=offset
        )
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CharacterValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [CharacterRead.model_validate(c) for c in characters]


# ===== 顶层 character 端点 =====
character_router = APIRouter(tags=["characters"])


@character_router.get(
    "/characters/{character_id}",
    response_model=CharacterRead,
    summary="获取人物卡详情",
)
async def get_character(
    character_id: int,
    service: CharacterService = Depends(get_service),
) -> CharacterRead:
    try:
        character = await service.get(character_id)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return CharacterRead.model_validate(character)


@character_router.patch(
    "/characters/{character_id}",
    response_model=CharacterRead,
    summary="部分更新人物卡",
)
async def update_character(
    character_id: int,
    payload: CharacterUpdate,
    service: CharacterService = Depends(get_service),
) -> CharacterRead:
    try:
        character = await service.update(character_id, payload)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CharacterValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return CharacterRead.model_validate(character)


@character_router.delete(
    "/characters/{character_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除人物卡（幂等，级联删 versions）",
)
async def delete_character(
    character_id: int,
    service: CharacterService = Depends(get_service),
) -> None:
    await service.delete(character_id)


@character_router.post(
    "/characters/{character_id}/growth",
    response_model=CharacterVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="记录一次性格/状态变化（自动追加 growth_arc + 新版本）",
)
async def record_growth(
    character_id: int,
    payload: CharacterGrowthUpdate,
    service: CharacterService = Depends(get_service),
) -> CharacterVersionRead:
    try:
        version = await service.update_growth(character_id, payload)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return CharacterVersionRead.model_validate(version)


@character_router.get(
    "/characters/{character_id}/versions",
    response_model=list[CharacterVersionRead],
    summary="查看人物卡版本历史（按时间倒序）",
)
async def list_character_versions(
    character_id: int,
    service: CharacterService = Depends(get_service),
) -> list[CharacterVersionRead]:
    try:
        versions = await service.list_versions(character_id)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [CharacterVersionRead.model_validate(v) for v in versions]


@character_router.get(
    "/characters/{character_id}/versions/{version_id}",
    response_model=CharacterVersionRead,
    summary="获取单个版本",
)
async def get_character_version(
    character_id: int,
    version_id: int,
    service: CharacterService = Depends(get_service),
) -> CharacterVersionRead:
    try:
        version = await service.get_version(character_id, version_id)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return CharacterVersionRead.model_validate(version)


# 把两层 router 都挂到顶层（一个 tags 下）
# 注意：/novels/{novel_id}/characters 已经包含在第一个 router 里
# 而 /characters/{...} 在第二个 router 里
# 合并后再统一挂到 FastAPI
combined_router = APIRouter(tags=["characters"])
combined_router.include_router(router)
combined_router.include_router(character_router)
