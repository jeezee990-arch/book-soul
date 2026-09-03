"""SSE（Server-Sent Events）流式响应解析。

OpenAI 兼容协议下，stream=true 时返回 ``text/event-stream``，格式：
```
data: {"id":"...","object":"chat.completion.chunk",...,"choices":[{"delta":{"content":"..."}}]}
data: {"id":"...","object":"chat.completion.chunk",...,"choices":[{"delta":{}}]}
data: [DONE]
```
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .base import LLMError


async def iter_sse_chunks(
    response: httpx.Response,
) -> AsyncIterator[dict[str, Any]]:
    """从 httpx 流式响应中解析 SSE chunk。

    每一行 ``data: <json>`` 被解析为 dict。``data: [DONE]`` 终止迭代。
    """
    async for line in response.aiter_lines():
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            break
        try:
            yield json.loads(payload)
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid SSE payload: {payload!r}") from e


def extract_delta_text(chunk: dict[str, Any]) -> str:
    """从单个 SSE chunk 提取 delta 文本。"""
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    return delta.get("content") or ""
