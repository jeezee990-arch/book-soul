"""单阶段大纲生成（一次调用出完整结构）。

适用范围
--------
只有 ``freedom``（创作型：散文 + 关键节拍 + 主题）走这条路径 —— 它本来就不是
"卷 → 章"结构，分两阶段没有意义。

``complete`` / ``semi_open`` 走两阶段（见
:mod:`src.services.outline_two_phase`）：阶段一骨架、阶段二各卷并行补细节。

为什么单独一个文件
------------------
:mod:`src.services.outline_generator` 要同时容纳"两阶段编排 + 入库 + 单阶段兜底"，
会超过 AGENTS.md 的 500 行上限。把单阶段拆出来，两个文件都短。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, Protocol

from loguru import logger

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.formatting import extract_json_object, strip_thinking
from ..core.llm.partial_json import parse_partial_json
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..core.llm.thinking import thinking_event
from .outline_errors import OutlineGenerationError

__all__ = ["stream_single_phase"]
# 增量解析节流
PARTIAL_PARSE_MIN_CHARS = 150
PARTIAL_PARSE_MAX_INTERVAL = 0.3


class SinglePhaseOutlineError(OutlineGenerationError):
    """单阶段大纲生成失败。"""


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口。"""

    provider: str

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any: ...


def _count_chapters(structure: dict[str, Any]) -> int:
    """统计结构里的章节数（给前端显示"已生成 N 章"）。"""
    volumes = structure.get("volumes")
    if not isinstance(volumes, list):
        return 0
    total = 0
    for volume in volumes:
        if isinstance(volume, dict) and isinstance(volume.get("chapters"), list):
            total += len(volume["chapters"])
    return total


async def stream_single_phase(
    llm: _LLMClientLike,
    *,
    prompt_template: str,
    genre: str,
    plot_summary: str,
    keywords: list[str] | None = None,
    outline_type: str = "freedom",
    user_extra: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """一次调用生成完整大纲结构（流式）。

    :param prompt_template: 已经加载好的 prompt 模板（含 ``{genre}`` / ``{plot}`` / ``{keywords}`` 占位符）
    :raises SinglePhaseOutlineError: LLM 调用失败 / JSON 解析失败
    """
    kw_str = ", ".join(keywords or []) if keywords else "（无）"
    extra_block = ""
    if user_extra.strip():
        extra_block = f"\n\n【作者个人想法（请在生成时参考，但不要照搬）】\n{user_extra.strip()}\n"
    full_prompt = (
        prompt_template.format(genre=genre, plot=plot_summary, keywords=kw_str) + extra_block
    )

    full_text = ""
    splitter = ThinkSplitter()
    t0 = time.monotonic()
    first_delta_at: float | None = None
    last_parsed_len = 0
    last_parse_at = t0
    last_partial: dict[str, Any] | None = None
    try:
        stream = await llm.chat(
            [ChatMessage("user", full_prompt)],
            temperature=0.7,
            stream=True,
        )
        async for delta in stream:  # type: ignore[attr-defined]
            if not delta:
                continue
            for kind, text in splitter.feed(delta):
                if kind == KIND_THINK:
                    yield thinking_event(text)
                    continue
                full_text += text
                if first_delta_at is None:
                    first_delta_at = time.monotonic()
                now = time.monotonic()
                if (
                    last_partial is None
                    or len(full_text) - last_parsed_len >= PARTIAL_PARSE_MIN_CHARS
                    or now - last_parse_at >= PARTIAL_PARSE_MAX_INTERVAL
                ):
                    last_parsed_len = len(full_text)
                    last_parse_at = now
                    partial = parse_partial_json(full_text)
                    if partial and partial != last_partial:
                        last_partial = partial
                        yield {
                            "event": "partial",
                            "structure": partial,
                            "chapters_done": _count_chapters(partial),
                        }
    except Exception as e:  # noqa: BLE001
        logger.error("outline LLM stream failed: {}", describe_llm_error(e))
        raise SinglePhaseOutlineError(describe_llm_error(e)) from e

    # 流结束：再解析一次，把最后写完的部分补发出去
    final_partial = parse_partial_json(full_text)
    if final_partial and final_partial != last_partial:
        yield {
            "event": "partial",
            "structure": final_partial,
            "chapters_done": _count_chapters(final_partial),
        }

    cleaned = strip_thinking(full_text)
    if not cleaned:
        raise SinglePhaseOutlineError("LLM returned empty")
    try:
        structure = extract_json_object(cleaned)
    except ValueError as e:
        raise SinglePhaseOutlineError(f"JSON parse failed: {e}") from e

    yield {
        "event": "structure_ready",
        "structure": structure,
        "first_delta_sec": (round(first_delta_at - t0, 2) if first_delta_at is not None else None),
    }
