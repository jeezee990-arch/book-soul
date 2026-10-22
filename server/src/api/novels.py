"""作品 REST 端点（Phase 1.1 + Phase 3.8 导出 md）。

端点：
- POST   /novels                          创建
- GET    /novels                          列表（支持 ?genre= &status= 过滤）
- GET    /novels/{id}                     详情
- PATCH  /novels/{id}                     部分更新
- DELETE /novels/{id}                     删除（幂等）
- GET    /novels/{id}/export-md           导出完整 markdown（Phase 3.8）

错误映射：
- NovelNotFoundError -> 404
- NovelValidationError -> 422（业务校验失败，与 Pydantic 422 区分用 detail 字段）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.novel import Novel
from ..schemas.novel import NovelCreate, NovelRead, NovelUpdate
from ..services.export_service import NovelExportService
from ..services.novel_service import (
    NovelNotFoundError,
    NovelService,
    NovelValidationError,
)


class ExportMdResponse(BaseModel):
    """导出 markdown 响应（JSON 形式便于 Tauri 序列化；前端再转 Blob 下载）。"""

    filename: str
    content: str


router = APIRouter(prefix="/novels", tags=["novels"])


def get_service(session: AsyncSession = Depends(get_db)) -> NovelService:
    """FastAPI 依赖：从 session 构造 service。"""
    return NovelService(session)


@router.post(
    "",
    response_model=NovelRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建作品",
)
async def create_novel(
    payload: NovelCreate,
    service: NovelService = Depends(get_service),
) -> NovelRead:
    try:
        novel = await service.create(payload)
    except NovelValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return NovelRead.model_validate(novel)


@router.get(
    "",
    response_model=list[NovelRead],
    summary="列出作品（支持 genre/status 过滤）",
)
async def list_novels(
    genre: str | None = Query(default=None, description="按题材过滤"),
    status_filter: str | None = Query(default=None, alias="status", description="按状态过滤"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: NovelService = Depends(get_service),
) -> list[NovelRead]:
    try:
        novels = await service.list_all(
            genre=genre, status=status_filter, limit=limit, offset=offset
        )
    except NovelValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return [NovelRead.model_validate(n) for n in novels]


@router.get(
    "/{novel_id}",
    response_model=NovelRead,
    summary="获取作品详情",
)
async def get_novel(
    novel_id: int,
    service: NovelService = Depends(get_service),
) -> NovelRead:
    try:
        novel = await service.get(novel_id)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return NovelRead.model_validate(novel)


@router.patch(
    "/{novel_id}",
    response_model=NovelRead,
    summary="部分更新作品",
)
async def update_novel(
    novel_id: int,
    payload: NovelUpdate,
    service: NovelService = Depends(get_service),
) -> NovelRead:
    try:
        novel = await service.update(novel_id, payload)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NovelValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return NovelRead.model_validate(novel)


@router.delete(
    "/{novel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除作品（幂等）",
)
async def delete_novel(
    novel_id: int,
    service: NovelService = Depends(get_service),
) -> None:
    await service.delete(novel_id)


@router.get(
    "/{novel_id}/export-md",
    response_model=ExportMdResponse,
    summary="Phase 3.8：导出作品为 markdown（作品名 + 大纲 + 人物卡）",
)
async def export_novel_markdown(
    novel_id: int,
    session: AsyncSession = Depends(get_db),
) -> ExportMdResponse:
    try:
        exporter = NovelExportService(session)
        md = await exporter.export_markdown(novel_id)
    except NovelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # 文件名用作品名（去非法字符）
    novel = await session.get(Novel, novel_id)
    safe_name = _safe_filename(novel.name) if novel else f"novel-{novel_id}"
    return ExportMdResponse(filename=f"{safe_name}.md", content=md)


def _safe_filename(name: str) -> str:
    """去文件名非法字符（Windows 友好）。"""
    import re

    # Windows 不允许: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
    return cleaned.strip() or "untitled"
