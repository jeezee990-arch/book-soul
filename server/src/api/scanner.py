"""本地扫描 REST 端点（Phase 6.3）。

端点：
- POST /scanner/scan   body: {"path": "D:/novels"} → 返回 DetectedNovel 列表
- POST /scanner/import body: {"dir_path": "...", "genre": "xiuxian"} → 导入为 novel

注：scanner 是文件 IO 密集，用 sync def（在 FastAPI threadpool 跑）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..core.scanner.novel_detector import DetectedNovel
from ..core.scanner.novel_importer import NovelImportError, import_detected_novel
from ..core.scanner.novel_scanner import scan_directory
from ..db import get_session

router = APIRouter(prefix="/scanner", tags=["scanner"])


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=1000, description="要扫描的根目录")
    max_depth: int = Field(default=3, ge=0, le=5, description="最大递归深度")


class ScanResponse(BaseModel):
    novels: list[dict[str, Any]]


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dir_path: str = Field(min_length=1, max_length=1000)
    genre: str = Field(default="xiuxian", max_length=50)


class ImportResponse(BaseModel):
    novel_id: int
    name: str
    chapter_count: int


def _detected_to_dict(d: DetectedNovel) -> dict[str, Any]:
    return {
        "dir_path": d.dir_path,
        "title": d.title,
        "chapter_count": d.chapter_count,
        "total_words": d.total_words,
        "chapters": [
            {
                "title": c.title,
                "path": c.path,
                "word_count": c.word_count,
                "preview": c.preview,
            }
            for c in d.chapters
        ],
    }


@router.post(
    "/scan",
    response_model=ScanResponse,
    summary="扫描根目录，返回所有疑似小说（Phase 6.3）",
)
def scan(req: ScanRequest) -> ScanResponse:
    try:
        novels = scan_directory(req.path, max_depth=req.max_depth)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}") from e
    return ScanResponse(novels=[_detected_to_dict(d) for d in novels])


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="把检测到的小说目录导入为 novel + chapters（read_only）",
)
async def import_novel(req: ImportRequest) -> ImportResponse:
    # 验证路径存在
    if not Path(req.dir_path).is_dir():
        raise HTTPException(status_code=422, detail=f"Not a directory: {req.dir_path}")

    # 重新 scan 一次拿最新 metadata（防止前端缓存过期）
    from ..core.scanner.novel_detector import extract_metadata

    try:
        detected = extract_metadata(req.dir_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if detected.chapter_count == 0:
        raise HTTPException(status_code=422, detail="No chapters found in directory")

    # 导入
    async with get_session() as session:
        try:
            novel = await import_detected_novel(session, detected, genre=req.genre)
        except NovelImportError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    return ImportResponse(
        novel_id=novel.id,
        name=novel.name,
        chapter_count=detected.chapter_count,
    )


__all__ = ["router"]
