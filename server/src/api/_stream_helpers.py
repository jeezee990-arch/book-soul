"""流式端点的 ndjson 助手（Phase 性能优化 / 流式输出简化）。

所有流式端点（``/inspirations/generate-plot/stream``、``/novels/outlines/generate/stream``、
``/novels/{id}/characters/generate-from-outline/stream``）
都用这套事件协议。

事件类型（统一 ``event`` 字段 + 业务字段）：
- ``{"event": "start", "phase": "..."}``           — 流开始 / 阶段开始
- ``{"event": "delta", "phase": "...", "text": "..."}`` — 增量文本
- ``{"event": "version_start", "index": 1}``      — 多版本流的某版本开始
- ``{"event": "version_done", "index": 1, "summary": "..."}`` — 某版本完成
- ``{"event": "done", "novel_id": ..., "novel_name": ..., "structure": {...}, "provider": "...", "model": "..."}`` — 整流完成
- ``{"event": "error", "message": "..."}``         — 失败

约定：
- ``event`` 字段恒存在；其它字段视场景而定
- 客户端按行解析（前端 ``streams.ts`` 已支持）
- 失败必须用 ``{"event": "error", "message": "..."}``，不要用别的事件名
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse


def ndjson_line(payload: dict[str, Any]) -> bytes:
    """构造 ndjson 一行（UTF-8 + 末尾换行）。"""
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def ndjson_response(
    generator: AsyncIterator[bytes],
    *,
    cache_control: str = "no-cache",
) -> StreamingResponse:
    """包装一个 async generator 为 ``application/x-ndjson`` 响应。

    关键 headers：
    - ``X-Accel-Buffering: no``  → 关掉 nginx 等反向代理的缓冲
    - ``Cache-Control: no-cache`` → 浏览器/CDN 不缓存
    """
    return StreamingResponse(
        generator,
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": cache_control,
            "X-Accel-Buffering": "no",
        },
    )


def stream_done_payload(
    *,
    provider: str = "",
    model: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """构造统一的 ``done`` 帧。"""
    payload: dict[str, Any] = {"event": "done", "provider": provider, "model": model}
    payload.update(extra)
    return payload


def stream_error_payload(message: str) -> dict[str, Any]:
    """构造统一的 ``error`` 帧。"""
    return {"event": "error", "message": message}


__all__ = [
    "ndjson_line",
    "ndjson_response",
    "stream_done_payload",
    "stream_error_payload",
]
