"""两阶段大纲生成（阶段一：卷章骨架 → 阶段二：各卷并行补细节）。

为什么拆两阶段（2026-10-25）
---------------------------
旧实现是**一次**调用让模型输出完整大纲（卷 + 章 + 概要 + 关键事件）。
实测 30 章的大纲要 **300 秒**：推理模型思考 135 秒 + 一次吐 1.2 万 token 165 秒。
而且 prompt 里把规模写死成"20-40 章"，作者在想法里写的"100 章"被无视。

现在拆成：

1. **阶段一（骨架）**：只规划卷名 + 章标题。输出量小 → 用户几十秒就能看到全书结构。
2. **阶段二（细节）**：每卷**并行**补章概要与关键事件。总耗时 ≈ 最慢的那一卷，
   而不是各卷之和。

阶段划分同时解决了两个问题：
- **速度**：总耗时从"一次吐 1.2 万 token"降到"小骨架 + 并行小补丁"。
- **规模可控**：章数是显式参数（:mod:`src.core.outline_scale`），
  写进 prompt 的硬性要求，不再被模板里的固定数字覆盖。

模块划分（2026-10-29，AGENTS.md §8.1 单文件 ≤ 500 行）
--------------------------------------------------
- :mod:`src.services.outline_skeleton` —— 阶段一（骨架生成 + 结构清洗）
- :mod:`src.services.outline_detail` —— 阶段二（分批 / 重试 / 兜底）
- **本模块** —— 只做编排（跑阶段一 → 跑阶段二 → 合并 → 发事件）

流式协议（本模块产出的事件）
--------------------------
- ``{"event": "skeleton", "structure": {...}, "chapters_done": N}`` —— 骨架完成
- ``{"event": "volume_start", "index": i, "name": "..."}`` —— 某卷开始细化
- ``{"event": "thinking", "index": i, "text": "..."}`` —— 某卷的模型思考
- ``{"event": "volume_done", "index": i, "volume": {...}}`` —— 某卷细化完成
- ``{"event": "volume_error", "index": i, "message": "..."}`` —— 某卷失败（**不影响其它卷**）
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from ..core.llm.base import ChatMessage, LLMClientLike, describe_llm_error
from ..core.llm.formatting import strip_thinking
from ..core.outline_scale import OutlineScale
from .outline_detail import VolumeDetailBuilder, placeholder_chapter
from .outline_errors import TwoPhaseOutlineError
from .outline_prompts import load_phase_prompt
from .outline_skeleton import SkeletonPhase, sanitize_skeleton

__all__ = [
    "TwoPhaseOutlineBuilder",
    "TwoPhaseOutlineError",
    "merge_volume_details",
    "sanitize_skeleton",
]

# 兼容旧引用：测试从本模块 import ``_load_phase_prompt``。
_load_phase_prompt = load_phase_prompt


def merge_volume_details(
    skeleton: dict[str, Any], enriched: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """把阶段二各卷的结果合并回骨架。

    ⚠️ 2026-10-29（需求7）：**失败的卷也要有内容**。旧实现直接保留骨架原样，
    于是那一卷的章节只剩标题（用户图7：CH01~CH14 只有标题）。现在给失败的卷
    补**占位概要**（明确标注"待细化"），保证任何一章都不会是空壳。

    :param skeleton: 阶段一的骨架
    :param enriched: ``卷下标 → 细化后的卷``（失败/缺失的卷用占位概要补）
    :return: 完整的大纲结构
    """
    volumes = skeleton.get("volumes") or []
    merged: list[dict[str, Any]] = []
    for index, volume in enumerate(volumes):
        detail = enriched.get(index)
        chapters = volume.get("chapters") or []
        if not isinstance(detail, dict):
            # 整卷失败 → 每章补占位概要（不留"只有标题"的空章节）
            placeholder_chapters = []
            for chapter in chapters:
                base = dict(chapter) if isinstance(chapter, dict) else {"title": str(chapter)}
                base.update(placeholder_chapter(base, volume))
                base.setdefault("key_events", [])
                placeholder_chapters.append(base)
            failed_volume = {k: v for k, v in volume.items() if k != "chapters"}
            failed_volume["chapters"] = placeholder_chapters
            merged.append(failed_volume)
            continue
        detail_chapters = detail.get("chapters") or []
        new_chapters: list[dict[str, Any]] = []
        for i, chapter in enumerate(chapters):
            base = dict(chapter)
            extra = (
                detail_chapters[i]
                if i < len(detail_chapters) and isinstance(detail_chapters[i], dict)
                else {}
            )
            summary = extra.get("summary")
            if isinstance(summary, str) and summary.strip():
                base["summary"] = summary.strip()
            events = extra.get("key_events")
            if isinstance(events, list):
                cleaned = [str(e).strip() for e in events if str(e).strip()]
                if cleaned:
                    base["key_events"] = cleaned
            base.setdefault("key_events", [])
            new_chapters.append(base)
        new_volume = {k: v for k, v in volume.items() if k != "chapters"}
        new_volume["chapters"] = new_chapters
        merged.append(new_volume)
    out = dict(skeleton)
    out["volumes"] = merged
    return out


class TwoPhaseOutlineBuilder:
    """两阶段大纲生成器（编排层）。

    职责边界：**只管生成结构**，不碰数据库、不建 novel。
    入库由 :class:`src.services.outline_generator.OutlineGenerator` 负责。
    """

    def __init__(
        self,
        llm: LLMClientLike,
        *,
        genre: str,
        plot_summary: str,
        keywords: list[str] | None = None,
        scale: OutlineScale,
        outline_type: str = "complete",
        user_extra: str = "",
        continue_context: dict[str, str] | None = None,
    ) -> None:
        self._llm = llm
        self._scale = scale
        self._skeleton = SkeletonPhase(
            llm,
            genre=genre,
            plot_summary=plot_summary,
            keywords=keywords,
            scale=scale,
            outline_type=outline_type,
            user_extra=user_extra,
            continue_context=continue_context,
        )
        self._detail = VolumeDetailBuilder(
            llm,
            genre=genre,
            plot_summary=plot_summary,
            scale=scale,
        )

    # ===== 阶段一 =====

    def _skeleton_prompt(self) -> str:
        """阶段一 prompt（薄封装；真正的拼装在 :class:`SkeletonPhase`）。"""
        return self._skeleton.prompt()

    async def stream_skeleton(self) -> AsyncIterator[dict[str, Any]]:
        """阶段一：流式生成卷章骨架（委托给 :class:`SkeletonPhase`）。"""
        async for event in self._skeleton.stream():
            yield event

    # ===== 阶段二 =====

    async def stream_details(self, skeleton: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """阶段二：各卷**并行**补章概要与关键事件。

        产出：``volume_start`` / ``thinking``（带 index）/ ``volume_done`` / ``volume_error``。

        ⚠️ 单卷的**系统级**失败（网络/鉴权）→ ``volume_error``，其余卷照常完成。
        ⚠️ 单卷的**内容级**失败（模型没吐正文）→ 内部重试 / 拆批 / 占位兜底，
        不会再出现"整卷只剩标题"（2026-10-29 用户图7 的根因）。
        """
        volumes = skeleton.get("volumes") or []
        if not volumes:
            return

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        remaining = len(volumes)

        async def worker(index: int, volume: dict[str, Any]) -> None:
            nonlocal remaining
            try:
                await queue.put(
                    {
                        "event": "volume_start",
                        "index": index,
                        "name": str(volume.get("name") or ""),
                    }
                )
                detail = await self._detail.detail_volume(index, volume, queue)
                await queue.put({"event": "volume_done", "index": index, "volume": detail})
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error("outline volume {} detail failed: {}", index, describe_llm_error(e))
                await queue.put(
                    {
                        "event": "volume_error",
                        "index": index,
                        "message": describe_llm_error(e),
                    }
                )
            finally:
                remaining -= 1
                if remaining == 0:
                    await queue.put(None)

        tasks = [asyncio.create_task(worker(i, v)) for i, v in enumerate(volumes)]
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    # ===== 便捷入口 =====

    async def build(self) -> dict[str, Any]:
        """**非流式**跑完两个阶段，返回完整结构。

        给非流式端点（``POST /novels/outlines/generate``）用 ——
        那条路径不需要中间事件，只要最终结构。

        :raises TwoPhaseOutlineError: 骨架阶段失败 / 骨架为空
        """
        prompt = self._skeleton.prompt()
        budget = min(32000, 4000 + self._scale.total_chapters * 120)
        try:
            resp = await self._llm.chat(
                [ChatMessage("user", prompt)],
                temperature=0.7,
                max_tokens=budget,
                stream=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("outline skeleton phase failed: {}", describe_llm_error(e))
            raise TwoPhaseOutlineError(describe_llm_error(e)) from e
        raw_text = getattr(resp, "content", "") or ""
        skeleton = self._skeleton.parse(strip_thinking(raw_text))
        if not skeleton.get("volumes"):
            raise TwoPhaseOutlineError(
                "LLM output structure invalid: 骨架为空（没有产出任何卷/章）"
            )

        volumes = skeleton.get("volumes") or []
        results = await asyncio.gather(
            *(self._detail.detail_volume_nonstream(i, v) for i, v in enumerate(volumes)),
            return_exceptions=True,
        )
        enriched: dict[int, dict[str, Any]] = {}
        for index, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(
                    "outline volume {} detail failed: {}",
                    index,
                    describe_llm_error(result),
                )
                continue
            enriched[index] = result
        return merge_volume_details(skeleton, enriched)

    async def run(self) -> AsyncIterator[dict[str, Any]]:
        """跑完两个阶段，产出全部中间事件 + 最后的 ``structure_ready``。

        事件序列：``thinking`` / ``partial`` / ``skeleton`` / ``volume_start`` /
        ``thinking(index)`` / ``volume_done`` / ``volume_error`` / ``structure_ready``。
        """
        skeleton: dict[str, Any] = {}
        enriched: dict[int, dict[str, Any]] = {}
        t0 = time.monotonic()
        first_delta_sec: float | None = None
        skeleton_sec: float | None = None
        async for event in self.stream_skeleton():
            if event.get("event") == "skeleton":
                skeleton = event.get("structure") or {}
                skeleton_sec = round(time.monotonic() - t0, 2)
                first_delta_sec = event.get("first_delta_sec")
            yield event
        if not skeleton:
            raise TwoPhaseOutlineError("骨架阶段没有产出结构")
        async for event in self.stream_details(skeleton):
            if event.get("event") == "volume_done":
                index = event.get("index")
                volume = event.get("volume")
                if isinstance(index, int) and isinstance(volume, dict):
                    enriched[index] = volume
            yield event
        yield {
            "event": "structure_ready",
            "structure": merge_volume_details(skeleton, enriched),
            "first_delta_sec": first_delta_sec,
            "skeleton_sec": skeleton_sec,
            "detail_sec": round(time.monotonic() - t0, 2) - (skeleton_sec or 0.0),
        }
