"""章节版本控制 REST 端点（Phase 4.6）。

端点：
- GET    /chapters/{chapter_id}/versions/{vid}/diff
            查询与 parent 的 diff（默认）；可用 ?other_id=xx 对比任意两版
- POST   /chapters/{chapter_id}/versions/{vid}/rollback
            软回滚：把目标版本内容设为当前内容，生成新版本（parent=当前最新）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.versioning.version_tree import (
    VersionNotFoundError,
    VersionTree,
)
from ..db import get_db
from ..schemas.chapter import ChapterVersionRead

router = APIRouter(tags=["chapters"])


class DiffStats(BaseModel):
    added: int
    removed: int


class DiffResponse(BaseModel):
    chapter_id: int
    from_version_id: int | None
    to_version_id: int
    diff: str
    stats: DiffStats


class RollbackResponse(BaseModel):
    """软回滚返回新版本。"""

    model_config = ConfigDict(from_attributes=True)

    new_version: ChapterVersionRead
    rolled_back_to: int


@router.get(
    "/chapters/{chapter_id}/versions/{version_id}/diff",
    response_model=DiffResponse,
    summary="查看版本的 diff（默认与 parent；可用 ?other_id= 对比任意两版）",
)
async def get_version_diff(
    chapter_id: int,
    version_id: int,
    other_id: int | None = Query(default=None, description="对比基准版本；省略则与 parent 对比"),
    session: AsyncSession = Depends(get_db),
) -> DiffResponse:
    tree = VersionTree(session, chapter_id=chapter_id)
    from ..core.versioning.diff import diff_stats
    from ..models.chapter import ChapterVersion

    if other_id is not None:
        diff = await tree.diff_between(other_id, version_id)
        from_id = other_id
    else:
        version = await session.get(ChapterVersion, version_id)
        if version is None or version.chapter_id != chapter_id:
            raise HTTPException(status_code=404, detail=f"Version {version_id} not in chapter {chapter_id}")
        diff = await tree.diff_with_parent(version_id)
        from_id = version.parent_version_id
    return DiffResponse(
        chapter_id=chapter_id,
        from_version_id=from_id,
        to_version_id=version_id,
        diff=diff,
        stats=DiffStats(**diff_stats(diff)),
    )


@router.post(
    "/chapters/{chapter_id}/versions/{version_id}/rollback",
    response_model=RollbackResponse,
    summary="软回滚到指定版本（生成新版本，parent=当前最新）",
)
async def rollback_version(
    chapter_id: int,
    version_id: int,
    session: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    tree = VersionTree(session, chapter_id=chapter_id)
    try:
        new_version = await tree.rollback(version_id)
    except VersionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RollbackResponse(
        new_version=ChapterVersionRead.model_validate(new_version),
        rolled_back_to=version_id,
    )


__all__ = ["router"]
