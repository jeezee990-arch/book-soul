"""Quality check REST 端点（Phase 5.2/5.3/5.4）。

端点：
- POST /novels/{novel_id}/chapters/{chapter_id}/quality
    对单章节做 5 维度并行质检，返回 QualityReport
- POST /novels/{novel_id}/chapters/{chapter_id}/quality/stream
    流式版：5 维度并行调用 LLM，逐个完成即推送（ndjson）

错误映射：
- QualityCheckError -> 422（参数错）/ 404（chapter/novel 不存在）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.quality import QualityReportRead
from ..services.quality_service import QualityCheckError, QualityService
from ._stream_helpers import ndjson_line, ndjson_response

router = APIRouter(tags=["quality"])


def get_service(session: AsyncSession = Depends(get_db)) -> QualityService:
    return QualityService(session)


@router.post(
    "/novels/{novel_id}/chapters/{chapter_id}/quality",
    response_model=QualityReportRead,
    summary="对单章节做 5 维度质检（writing / logic / pacing / consistency / genre）",
)
async def check_chapter_quality(
    novel_id: int,
    chapter_id: int,
    service: QualityService = Depends(get_service),
) -> QualityReportRead:
    try:
        report = await service.check_chapter(novel_id, chapter_id)
    except QualityCheckError as e:
        msg = str(e)
        if "not found" in msg.lower() or "not in novel" in msg:
            raise HTTPException(status_code=404, detail=msg) from e
        raise HTTPException(status_code=422, detail=msg) from e
    return QualityReportRead(
        chapter_id=report.chapter_id,
        novel_id=report.novel_id,
        chapter_title=report.chapter_title,
        genre=report.genre,
        total_score=report.total_score,
        dimension_scores=report.dimension_scores,
        dimension_results=[
            {
                "dimension": r.dimension,
                "score": r.score,
                "issues": [
                    {
                        "type": i.type,
                        "character": i.character,
                        "quote": i.quote,
                        "problem": i.problem,
                        "suggestion": i.suggestion,
                    }
                    for i in r.issues
                ],
                "suggestions": r.suggestions,
                "error": r.error,
            }
            for r in report.dimension_results
        ],
        issues=[
            {
                "type": i.type,
                "character": i.character,
                "quote": i.quote,
                "problem": i.problem,
                "suggestion": i.suggestion,
            }
            for i in report.issues
        ],
        suggestions=report.suggestions,
        provider=report.provider,
        model=report.model,
    )


# ===== 流式版本（Phase 性能优化）=====


@router.post(
    "/novels/{novel_id}/chapters/{chapter_id}/quality/stream",
    summary="流式质检（5 维度并行；逐维度完成即推送）",
)
async def check_chapter_quality_stream(
    novel_id: int,
    chapter_id: int,
    service: QualityService = Depends(get_service),
):
    """流式端点：5 维度 LLM **并行**调，单个完成即推事件。

    协议见 :mod:`src.api._stream_helpers`。
    """

    async def gen():
        async for event in service.stream_check_chapter(novel_id, chapter_id):
            yield ndjson_line(event)

    return ndjson_response(gen())


__all__ = ["router"]
