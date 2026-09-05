"""备份 / 恢复 REST 端点（Phase 7.4）。

端点：
- GET  /backup/export      返回 zip 字节流（trigger 浏览器下载）
- POST /backup/import      上传 zip（base64 in body）→ 恢复
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..core.config import settings
from ..services.backup_service import BackupError, export_backup, import_backup

router = APIRouter(prefix="/backup", tags=["backup"])


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zip_b64: str = Field(min_length=1, description="zip 文件的 base64 编码")
    overwrite: bool = Field(default=True, description="是否覆盖现有数据")


class ImportResponse(BaseModel):
    files: int
    manifest_present: bool
    db_backed_up: bool


@router.get(
    "/export",
    summary="导出 data_dir 为 zip 字节流（base64 包装 JSON 返回）",
)
def export_backup_endpoint() -> dict[str, str]:
    try:
        data = export_backup(settings.data_dir)
    except BackupError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {
        "filename": "book-soul-backup.zip",
        "mime": "application/zip",
        "content_b64": base64.b64encode(data).decode("ascii"),
    }


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="从 zip 恢复（base64 in body）",
)
def import_backup_endpoint(req: ImportRequest) -> ImportResponse:
    try:
        zip_bytes = base64.b64decode(req.zip_b64, validate=True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid base64: {e}") from e
    try:
        result = import_backup(settings.data_dir, zip_bytes, overwrite=req.overwrite)
    except BackupError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return ImportResponse(**result)


__all__ = ["router"]
