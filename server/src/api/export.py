"""多格式导出 REST 端点（Phase 4.7）。

端点：
- GET /novels/{id}/export?format=md     markdown（JSON 形式：filename + content）
- GET /novels/{id}/export?format=html   HTML（JSON 形式）
- GET /novels/{id}/export?format=docx   Word（依赖 python-docx；未装时 501）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.novel import Novel
from ..services.character_service import NovelNotFoundError
from ..services.export_docx import WordExportUnavailableError, build_docx_bytes
from ..services.export_service import NovelExportService

router = APIRouter(prefix="/novels", tags=["export"])


class ExportFileResponse(BaseModel):
    """通用导出响应：filename + base64 编码内容。"""

    filename: str
    mime: str
    content_b64: str


_FORMAT_MIME: dict[str, str] = {
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
}


@router.get(
    "/{novel_id}/export",
    response_model=ExportFileResponse,
    summary="多格式导出：md / html / docx",
)
async def export_novel(
    novel_id: int,
    fmt: str = Query(default="md", alias="format", pattern="^(md|html|docx)$"),
    session: AsyncSession = Depends(get_db),
) -> ExportFileResponse:
    """多格式导出。

    md / html：返回 JSON（含 base64 内容）；前端用 ``fetch`` + ``atob`` + ``Blob`` 下载。
    docx：当前依赖 python-docx；未装时 501。
    """
    import base64

    novel = await session.get(Novel, novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail=f"Novel {novel_id} not found")
    safe_name = _safe_filename(novel.name) or f"novel-{novel_id}"

    exporter = NovelExportService(session)
    if fmt == "md":
        try:
            text = await exporter.export_markdown(novel_id)
        except NovelNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return ExportFileResponse(
            filename=f"{safe_name}.md",
            mime=_FORMAT_MIME["md"],
            content_b64=base64.b64encode(text.encode("utf-8")).decode("ascii"),
        )
    if fmt == "html":
        try:
            text = await exporter.export_html(novel_id)
        except NovelNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return ExportFileResponse(
            filename=f"{safe_name}.html",
            mime=_FORMAT_MIME["html"],
            content_b64=base64.b64encode(text.encode("utf-8")).decode("ascii"),
        )
    if fmt == "docx":
        try:
            data = build_docx_bytes(novel_id, session)
        except WordExportUnavailableError as e:
            raise HTTPException(status_code=501, detail=str(e)) from e
        return ExportFileResponse(
            filename=f"{safe_name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content_b64=base64.b64encode(data).decode("ascii"),
        )
    # 理论不可达（Query pattern 已限制）
    raise HTTPException(status_code=422, detail=f"Unsupported format: {fmt}")


def _safe_filename(name: str) -> str:
    """去文件名非法字符（Windows 友好）。"""
    import re

    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
    return cleaned.strip()


__all__ = ["router"]
