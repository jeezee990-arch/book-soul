"""章节生成 / 重写 REST 端点（Phase 4.3 / 4.4 流式）。

端点：
- POST /chapters/{chapter_id}/generate     流式生成（ndjson）
- POST /chapters/{chapter_id}/rewrite      流式选区 / 全文重写（ndjson）

流式协议（ndjson，每行一个 JSON 对象）：
- 成功增量：``{"text": "<delta>"}``
- 终止：``{"done": true, "provider": "mimo", "model": "..."}``
- 错误：``{"error": "<msg>"}``
- 客户端按行 split 即可

注意：
- 不在端点层写 ChapterVersion；流式失败时不需要回滚 DB
- 客户端拿到完整文本后调 PATCH /chapters/{id}/content 写版本（trigger="llm_generate" / "rewrite"）
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas.chapter import ChapterGenerateRequest, ChapterRewriteRequest
from ..services.chapter_generator import (
    ChapterGenerationError,
    ChapterGenerator,
)
from ..services.chapter_rewriter import ChapterRewriteError, ChapterRewriter
from ..services.chapter_service import ChapterService

router = APIRouter(tags=["chapters"])


def _gen_service(session: AsyncSession = Depends(get_db)) -> ChapterGenerator:
    return ChapterGenerator(session)


def _rewrite_service(session: AsyncSession = Depends(get_db)) -> ChapterRewriter:
    return ChapterRewriter(session)


def _ndjson(payload: dict[str, Any]) -> bytes:
    """构造 ndjson 一行。"""
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


async def _stream_chapter_generate(
    chapter_id: int,
    payload: ChapterGenerateRequest,
    session: AsyncSession,
) -> AsyncIterator[bytes]:
    """生成 ndjson 流。"""
    gen = ChapterGenerator(session)
    provider = "unknown"
    model = ""
    try:
        # 预检：章节存在
        await ChapterService(session).get(chapter_id)
    except Exception as e:  # noqa: BLE001
        yield _ndjson({"error": str(e)})
        return

    try:
        async for delta in gen.stream_generate(
            chapter_id=chapter_id,
            user_prompt=payload.user_prompt or "",
            target_word_count=payload.target_word_count,
        ):
            yield _ndjson({"text": delta})
        # 收尾帧
        try:
            llm = gen._get_llm()  # noqa: SLF001 - 偷一下 provider 名
            provider = str(getattr(llm, "provider", "unknown") or "unknown")
            model = str(getattr(llm, "model", "") or "")
        except Exception:  # noqa: BLE001
            pass
        yield _ndjson({"done": True, "provider": provider, "model": model})
    except ChapterGenerationError as e:
        yield _ndjson({"error": str(e)})
    except Exception as e:  # noqa: BLE001
        yield _ndjson({"error": f"unexpected: {e!s}"})


@router.post(
    "/chapters/{chapter_id}/generate",
    summary="流式生成章节正文（ndjson）",
    response_class=StreamingResponse,
)
async def generate_chapter_stream(
    chapter_id: int,
    payload: ChapterGenerateRequest,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """流式生成。

    返回 ``application/x-ndjson``，每行一个 JSON：
    - ``{"text": "..."}``：增量文本
    - ``{"done": true, "provider": "...", "model": "..."}``：收尾
    - ``{"error": "..."}``：失败
    """
    return StreamingResponse(
        _stream_chapter_generate(chapter_id, payload, session),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_chapter_rewrite(
    chapter_id: int,
    payload: ChapterRewriteRequest,
    session: AsyncSession,
) -> AsyncIterator[bytes]:
    """重写 ndjson 流。"""
    rewriter = ChapterRewriter(session)
    try:
        await ChapterService(session).get(chapter_id)
    except Exception as e:  # noqa: BLE001
        yield _ndjson({"error": str(e)})
        return

    try:
        async for delta in rewriter.stream_rewrite(
            chapter_id=chapter_id,
            original_text=payload.original_text,
            user_prompt=payload.user_prompt,
        ):
            yield _ndjson({"text": delta})
        yield _ndjson({"done": True})
    except ChapterRewriteError as e:
        yield _ndjson({"error": str(e)})
    except Exception as e:  # noqa: BLE001
        yield _ndjson({"error": f"unexpected: {e!s}"})


@router.post(
    "/chapters/{chapter_id}/rewrite",
    summary="流式选区 / 全文重写（ndjson）",
    response_class=StreamingResponse,
)
async def rewrite_chapter_stream(
    chapter_id: int,
    payload: ChapterRewriteRequest,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """流式重写选区或全文。

    返回 ``application/x-ndjson``，每行一个 JSON。
    """
    return StreamingResponse(
        _stream_chapter_rewrite(chapter_id, payload, session),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
