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


# 正文片段的 kind
KIND_TEXT = "text"
# 思考片段的 kind（``<think>...</think>`` 内部）
KIND_THINK = "think"


class ThinkSplitter:
    """把 LLM 的流式输出拆成「正文」和「思考」两路。

    为什么需要（2026-10-24）
    ----------------------
    推理模型（minimax / 部分 mimo）会先吐一整段 ``<think>...</think>``
    再开始吐正文。以前各 service 都是这么写的::

        if "<think>" in delta and "</think>" not in delta:
            continue          # 直接丢掉

    问题有两个：

    1. **思考期是空窗**。思考可能持续好几秒，这段时间前端一个字都收不到，
       用户看到的就是"卡住不动"（2026-10-24 用户反馈）。
    2. **判断不严谨**：一个 delta 里同时含 ``<think>`` 和 ``</think>`` 时，
       整个 chunk（包括思考内容）都会被当成正文吐出去。

    用法::

        splitter = ThinkSplitter()
        async for delta in stream:
            for kind, text in splitter.feed(delta):
                if kind == KIND_THINK:
                    ...   # 思考内容 —— 转成 "thinking" 事件给前端做提示
                else:
                    ...   # 正文
    """

    def __init__(self) -> None:
        self._in_think = False

    @property
    def in_think(self) -> bool:
        """当前是否处于思考块内部。"""
        return self._in_think

    def feed(self, delta: str) -> list[tuple[str, str]]:
        """喂入一个 delta，返回拆出来的 ``(kind, text)`` 片段列表。

        :param delta: 上游推来的原始文本片段
        :return: 形如 ``[("text", "正文"), ("think", "思考")]`` 的列表（顺序即出现顺序）
        """
        parts: list[tuple[str, str]] = []
        buf = delta
        while buf:
            if self._in_think:
                end = buf.find("</think>")
                if end == -1:
                    parts.append((KIND_THINK, buf))
                    buf = ""
                else:
                    parts.append((KIND_THINK, buf[:end]))
                    buf = buf[end + len("</think>") :]
                    self._in_think = False
            else:
                start = buf.find("<think>")
                if start == -1:
                    parts.append((KIND_TEXT, buf))
                    buf = ""
                else:
                    if start > 0:
                        parts.append((KIND_TEXT, buf[:start]))
                    buf = buf[start + len("<think>") :]
                    self._in_think = True
        return [(kind, text) for kind, text in parts if text]
