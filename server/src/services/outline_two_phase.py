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
import json
import time
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Protocol

import yaml
from loguru import logger

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.formatting import extract_json_object, strip_thinking
from ..core.llm.partial_json import parse_partial_json
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..core.outline_scale import OutlineScale
from ..core.paths import prompts_dir
from .outline_errors import OutlineGenerationError

__all__ = [
    "TwoPhaseOutlineBuilder",
    "TwoPhaseOutlineError",
    "merge_volume_details",
    "sanitize_skeleton",
]

# 同时进行的卷细化调用数上限。
#
# 为什么限流：一次 100 章的大纲可能有 10 卷 → 10 个并发 LLM 调用。
# 不限流的话，10 个推理模型同时思考（每个 ~3000 token）容易触发上游限流，
# 反而更慢。限到 8，超出的排队。
MAX_CONCURRENT_DETAILS = 8

# 增量解析节流（与 outline_generator 保持一致）
PARTIAL_PARSE_MIN_CHARS = 150
PARTIAL_PARSE_MAX_INTERVAL = 0.3


class TwoPhaseOutlineError(OutlineGenerationError):
    """两阶段大纲生成失败（阶段一失败 / 骨架不可用）。"""


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口（与 ``outline_generator`` 保持一致）。"""

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


@lru_cache(maxsize=8)
def _load_phase_prompt(name: str) -> str:
    """加载 ``config/prompts/outline_{name}.yaml`` 的 ``prompt`` 字段。"""
    path = prompts_dir() / f"outline_{name}.yaml"
    if not path.is_file():
        raise TwoPhaseOutlineError(f"Outline prompt not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "prompt" not in data:
        raise TwoPhaseOutlineError(f"Outline prompt {path} missing 'prompt' field")
    return str(data["prompt"])


# ===== 结构清洗 =====


def _clean_chapter(raw: Any) -> dict[str, Any] | None:
    """清洗单个章节；没有标题的返回 None（半截 JSON 里常见的空壳）。"""
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    chapter: dict[str, Any] = {"title": title}
    summary = raw.get("summary")
    if isinstance(summary, str) and summary.strip():
        chapter["summary"] = summary.strip()
    events = raw.get("key_events")
    if isinstance(events, list):
        chapter["key_events"] = [str(e).strip() for e in events if str(e).strip()]
    return chapter


def _clean_volume(raw: Any) -> dict[str, Any] | None:
    """清洗单卷；没有章节的返回 None。"""
    if not isinstance(raw, dict):
        return None
    chapters_raw = raw.get("chapters")
    chapters: list[dict[str, Any]] = []
    if isinstance(chapters_raw, list):
        for c in chapters_raw:
            cleaned = _clean_chapter(c)
            if cleaned is not None:
                chapters.append(cleaned)
    if not chapters:
        return None
    volume: dict[str, Any] = {
        "name": str(raw.get("name") or "未命名卷").strip() or "未命名卷",
        "chapters": chapters,
    }
    summary = raw.get("summary")
    if isinstance(summary, str) and summary.strip():
        volume["summary"] = summary.strip()
    return volume


def sanitize_skeleton(raw: dict[str, Any], *, outline_type: str = "complete") -> dict[str, Any]:
    """把模型吐出来的骨架整理成合法结构。

    - 只保留**已知**的顶层字段（``extra="forbid"`` 的 Pydantic model 会拒掉多余的键）
    - 丢掉没有标题的章节、没有章节的空卷
    - ``semi_open`` 保留 ``suspense_hook``

    :param raw: 模型输出的原始 dict
    :param outline_type: ``complete`` / ``semi_open``
    :return: 清洗后的结构
    """
    volumes_raw = raw.get("volumes")
    volumes: list[dict[str, Any]] = []
    if isinstance(volumes_raw, list):
        for v in volumes_raw:
            cleaned = _clean_volume(v)
            if cleaned is not None:
                volumes.append(cleaned)
    out: dict[str, Any] = {"volumes": volumes}
    theme = raw.get("overall_theme")
    if isinstance(theme, str) and theme.strip():
        out["overall_theme"] = theme.strip()
    if outline_type == "semi_open":
        hook = raw.get("suspense_hook")
        if isinstance(hook, str) and hook.strip():
            out["suspense_hook"] = hook.strip()
    return out


def merge_volume_details(
    skeleton: dict[str, Any], enriched: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """把阶段二各卷的结果合并回骨架。

    :param skeleton: 阶段一的骨架
    :param enriched: ``卷下标 → 细化后的卷``（失败/缺失的卷用骨架原样）
    :return: 完整的大纲结构
    """
    volumes = skeleton.get("volumes") or []
    merged: list[dict[str, Any]] = []
    for index, volume in enumerate(volumes):
        detail = enriched.get(index)
        if not isinstance(detail, dict):
            merged.append(volume)
            continue
        chapters = volume.get("chapters") or []
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


def _chapters_skeleton_text(volume: dict[str, Any]) -> str:
    """把一卷的章节骨架渲染成给阶段二 prompt 用的文本。"""
    chapters = volume.get("chapters") or []
    lines: list[str] = []
    for i, chapter in enumerate(chapters, start=1):
        title = str(chapter.get("title") or "").strip()
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


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


class TwoPhaseOutlineBuilder:
    """两阶段大纲生成器。

    职责边界：**只管生成结构**，不碰数据库、不建 novel。
    入库由 :class:`src.services.outline_generator.OutlineGenerator` 负责。
    """

    def __init__(
        self,
        llm: _LLMClientLike,
        *,
        genre: str,
        plot_summary: str,
        keywords: list[str] | None = None,
        scale: OutlineScale,
        outline_type: str = "complete",
        user_extra: str = "",
    ) -> None:
        self._llm = llm
        self._genre = genre
        self._plot_summary = plot_summary
        self._keywords = keywords or []
        self._scale = scale
        self._outline_type = outline_type
        self._user_extra = user_extra or ""

    # ===== 阶段一：骨架 =====

    def _skeleton_prompt(self) -> str:
        """拼装阶段一 prompt。"""
        kw = ", ".join(self._keywords) if self._keywords else "（无）"
        mode_block = ""
        if self._outline_type == "semi_open":
            mode_block = (
                "\n- 本次只生成**前期**，故事在此停下；"
                "JSON 里额外给出 `suspense_hook`（悬念钩子，20-50字），"
                "说明后续可以从哪里继续。\n"
            )
        extra = self._user_extra.strip()
        extra_block = extra if extra else "（无）"
        return _load_phase_prompt("skeleton").format(
            genre=self._genre,
            plot=self._plot_summary,
            keywords=kw,
            total_chapters=self._scale.total_chapters,
            volume_count=self._scale.volume_count,
            volume_plan=self._scale.volume_plan,
            words_per_chapter=self._scale.words_per_chapter,
            mode_block=mode_block,
            user_extra=extra_block,
        )

    async def stream_skeleton(self) -> AsyncIterator[dict[str, Any]]:
        """阶段一：流式生成卷章骨架。

        产出：``thinking`` / ``partial``（增量结构）/ ``skeleton``（完成）。
        """
        prompt = self._skeleton_prompt()
        splitter = ThinkSplitter()
        full_text = ""
        t0 = time.monotonic()
        last_parsed_len = 0
        last_parse_at = time.monotonic()
        last_partial: dict[str, Any] | None = None
        first_delta_at: float | None = None
        # 骨架输出量 = 章标题 + 卷名/卷概要，给足预算（宁多勿截断）
        budget = min(32000, 4000 + self._scale.total_chapters * 120)

        try:
            stream = await self._llm.chat(
                [ChatMessage("user", prompt)],
                temperature=0.7,
                max_tokens=budget,
                stream=True,
            )
            async for delta in stream:  # type: ignore[union-attr]
                if not delta:
                    continue
                for kind, text in splitter.feed(delta):
                    if kind == KIND_THINK:
                        yield {"event": "thinking", "text": text}
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
                        if partial:
                            cleaned = sanitize_skeleton(
                                partial, outline_type=self._outline_type
                            )
                            if cleaned != last_partial:
                                last_partial = cleaned
                                yield {
                                    "event": "partial",
                                    "structure": cleaned,
                                    "chapters_done": _count_chapters(cleaned),
                                }
        except Exception as e:  # noqa: BLE001
            logger.error("outline skeleton phase failed: {}", describe_llm_error(e))
            raise TwoPhaseOutlineError(describe_llm_error(e)) from e

        # 流结束：再解析一次，把最后写完的几章补发出去
        # （节流会漏掉最后几十毫秒才写完的部分 —— 用户看到的章数会少 1-2 章）
        final_partial = parse_partial_json(full_text)
        if final_partial:
            cleaned = sanitize_skeleton(final_partial, outline_type=self._outline_type)
            if cleaned != last_partial:
                last_partial = cleaned
                yield {
                    "event": "partial",
                    "structure": cleaned,
                    "chapters_done": _count_chapters(cleaned),
                }

        cleaned_text = strip_thinking(full_text)
        if not cleaned_text.strip():
            raise TwoPhaseOutlineError("LLM returned empty content (skeleton phase)")

        skeleton = self._parse_skeleton(cleaned_text)
        if not skeleton.get("volumes"):
            raise TwoPhaseOutlineError(
                "LLM output structure invalid: 骨架为空（没有产出任何卷/章）"
            )
        yield {
            "event": "skeleton",
            "structure": skeleton,
            "chapters_done": _count_chapters(skeleton),
            "first_delta_sec": (
                round(first_delta_at - t0, 2) if first_delta_at is not None else None
            ),
        }

    def _parse_skeleton(self, text: str) -> dict[str, Any]:
        """解析阶段一输出；整段解析失败时退回半截 JSON 容错解析。"""
        try:
            raw = extract_json_object(text)
        except ValueError:
            raw = parse_partial_json(text)
            if raw is None:
                raise TwoPhaseOutlineError("骨架 JSON 解析失败") from None
        return sanitize_skeleton(raw, outline_type=self._outline_type)

    # ===== 阶段二：各卷并行补细节 =====

    def _detail_prompt(self, index: int, volume: dict[str, Any]) -> str:
        """拼装某一卷的细节 prompt。"""
        return _load_phase_prompt("volume_detail").format(
            genre=self._genre,
            plot=self._plot_summary,
            volume_index=index + 1,
            volume_count=self._scale.volume_count,
            volume_name=str(volume.get("name") or ""),
            volume_summary=str(volume.get("summary") or "（无）"),
            chapters_json=_chapters_skeleton_text(volume),
            words_per_chapter=self._scale.words_per_chapter,
        )

    async def stream_details(
        self, skeleton: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """阶段二：各卷**并行**补章概要与关键事件。

        产出：``volume_start`` / ``thinking``（带 index）/ ``volume_done`` / ``volume_error``。

        ⚠️ 单卷失败**不拖垮整条流**：失败的卷保留骨架原样，其余卷照常完成。
        """
        volumes = skeleton.get("volumes") or []
        if not volumes:
            return

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DETAILS)
        remaining = len(volumes)

        async def worker(index: int, volume: dict[str, Any]) -> None:
            nonlocal remaining
            try:
                async with semaphore:
                    await queue.put(
                        {
                            "event": "volume_start",
                            "index": index,
                            "name": str(volume.get("name") or ""),
                        }
                    )
                    detail = await self._detail_volume(index, volume, queue)
                    await queue.put(
                        {"event": "volume_done", "index": index, "volume": detail}
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "outline volume {} detail failed: {}", index, describe_llm_error(e)
                )
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

        tasks = [
            asyncio.create_task(worker(i, v)) for i, v in enumerate(volumes)
        ]
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

    async def _detail_volume(
        self, index: int, volume: dict[str, Any], queue: asyncio.Queue
    ) -> dict[str, Any]:
        """调用 LLM 细化一卷，返回补齐概要与关键事件后的卷。"""
        prompt = self._detail_prompt(index, volume)
        chapters = volume.get("chapters") or []
        # 每章概要 ~80 字 + 3 个关键事件 ≈ 250 token，留 3 倍余量
        budget = min(16000, 1200 + len(chapters) * 300)
        splitter = ThinkSplitter()
        full_text = ""
        stream = await self._llm.chat(
            [ChatMessage("user", prompt)],
            temperature=0.5,
            max_tokens=budget,
            stream=True,
        )
        async for delta in stream:  # type: ignore[union-attr]
            if not delta:
                continue
            for kind, text in splitter.feed(delta):
                if kind == KIND_THINK:
                    await queue.put(
                        {"event": "thinking", "index": index, "text": text}
                    )
                    continue
                full_text += text
        cleaned = strip_thinking(full_text)
        if not cleaned.strip():
            raise TwoPhaseOutlineError(f"第 {index + 1} 卷返回空内容")
        try:
            raw = extract_json_object(cleaned)
        except ValueError:
            raw = parse_partial_json(cleaned)
            if raw is None:
                raise TwoPhaseOutlineError(f"第 {index + 1} 卷 JSON 解析失败") from None
        if not isinstance(raw, dict):
            raise TwoPhaseOutlineError(f"第 {index + 1} 卷 JSON 形状不对")
        detail = raw.get("chapters")
        if not isinstance(detail, list):
            detail = []
        return {
            "name": volume.get("name", ""),
            "summary": volume.get("summary", ""),
            "chapters": detail,
        }

    # ===== 便捷入口 =====

    async def build(self) -> dict[str, Any]:
        """**非流式**跑完两个阶段，返回完整结构。

        给非流式端点（``POST /novels/outlines/generate``）用 ——
        那条路径不需要中间事件，只要最终结构。

        :raises TwoPhaseOutlineError: 骨架阶段失败 / 骨架为空
        """
        prompt = self._skeleton_prompt()
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
        skeleton = self._parse_skeleton(strip_thinking(raw_text))
        if not skeleton.get("volumes"):
            raise TwoPhaseOutlineError(
                "LLM output structure invalid: 骨架为空（没有产出任何卷/章）"
            )

        volumes = skeleton.get("volumes") or []
        results = await asyncio.gather(
            *(self._detail_volume_nonstream(i, v) for i, v in enumerate(volumes)),
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

    async def _detail_volume_nonstream(
        self, index: int, volume: dict[str, Any]
    ) -> dict[str, Any]:
        """非流式细化一卷。"""
        prompt = self._detail_prompt(index, volume)
        chapters = volume.get("chapters") or []
        budget = min(16000, 1200 + len(chapters) * 300)
        resp = await self._llm.chat(
            [ChatMessage("user", prompt)],
            temperature=0.5,
            max_tokens=budget,
            stream=False,
        )
        cleaned = strip_thinking(getattr(resp, "content", "") or "")
        if not cleaned.strip():
            raise TwoPhaseOutlineError(f"第 {index + 1} 卷返回空内容")
        try:
            raw = extract_json_object(cleaned)
        except ValueError:
            raw = parse_partial_json(cleaned)
            if raw is None:
                raise TwoPhaseOutlineError(
                    f"第 {index + 1} 卷 JSON 解析失败"
                ) from None
        detail = raw.get("chapters") if isinstance(raw, dict) else None
        if not isinstance(detail, list):
            detail = []
        return {
            "name": volume.get("name", ""),
            "summary": volume.get("summary", ""),
            "chapters": detail,
        }

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


def _dump(value: Any) -> str:
    """调试用：把结构压成短 JSON（避免在日志里刷屏）。"""
    return json.dumps(value, ensure_ascii=False)[:500]
