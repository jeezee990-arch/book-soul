"""大纲阶段二（各卷补细节）的**分批 / 重试 / 兜底**逻辑。

为什么单独一个文件
------------------
两阶段大纲的"补细节"是最容易出错的一段：它要同时处理
「推理模型思考吃光额度」「批次对齐」「失败不拖垮整卷」三件事。
拆出来单独放，:mod:`src.services.outline_two_phase` 只管编排
（阶段一 / 并发 / 事件协议）。

2026-10-29 实测事故（用户图7：CH01~CH14 只有标题）
---------------------------------------------------
旧实现**一卷一次调用**（20 章一起），正文预算 = 1200 + 20×300 = 7200 token。
推理模型（MiniMax-M3.1-Flash）的思考**不受这个预算约束** —— 思考一长就把
正文额度吃光，模型最终一个字正文都不吐，报「第 N 卷返回空内容」。
服务端日志实证：5 卷里 3 卷失败 → 那 3 卷的几十章只剩标题。

现在的四道防线
--------------
1. **分批**：每批 ≤ :data:`DETAIL_BATCH_SIZE` 章 → 思考量与输出量都小一个量级；
2. **重试**：空内容 → 正文预算翻倍再试一次（思考吃额度是主因）；
3. **拆批**：还失败 → 把批次**对半拆开**重跑（章越少越好写）；
4. **兜底**：单章还失败 → 占位概要（**绝不**留"只有标题"的空章节）。

占位概要为什么不用模型编
------------------------
编出来的剧情是**假**的，作者会把它当真大纲去写正文。
这里改成诚实的占位：明确标注「待细化」，用户一眼能看出这一章没生成出来。
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from ..core.llm.base import ChatMessage, LLMClientLike
from ..core.llm.formatting import extract_json_object, strip_thinking
from ..core.llm.partial_json import parse_partial_json
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..core.llm.thinking import thinking_event
from ..core.outline_scale import OutlineScale
from .outline_errors import TwoPhaseOutlineError
from .outline_prompts import load_phase_prompt

__all__ = [
    "DETAIL_BATCH_SIZE",
    "DETAIL_MAX_BUDGET",
    "MAX_CONCURRENT_DETAIL_CALLS",
    "VolumeDetailBuilder",
    "align_detail",
    "chapters_skeleton_text",
    "detail_budget",
    "placeholder_chapter",
    "split_batches",
]

# 一次调用最多细化多少章。
#
# 为什么是 6：一卷 20 章 → 4 批。每批的正文输出 ≈ 6×250 = 1500 token，
# 推理模型为这点内容花掉的思考通常在 2-3k 以内 —— 远小于
# 「正文预算 + reasoning_token_overhead」，不会再把正文额度吃光。
DETAIL_BATCH_SIZE = 6

# 同时进行的**细化调用**数上限。
#
# 为什么限流：一次 100 章的大纲可能有 10 卷 × 4 批 = 40 个调用。
# 不限流的话，几十个推理模型同时思考（每个 ~2000 token）容易触发上游限流，
# 反而更慢。限到 8，超出的排队。
#
# ⚠️ 2026-10-29：这个信号量管的是**批次级**调用（原来管卷级）。
# 卷内各批并行、卷间并行，共用同一个信号量 → 全局并发始终 ≤ 8。
MAX_CONCURRENT_DETAIL_CALLS = 8

# 正文预算参数（token）。
#
# ⚠️ 这是**正文**预算；provider 会再叠加 ``reasoning_token_overhead``，
# 最终发给上游的是 min(正文预算 + 思考预算, 模型硬上限)。
_DETAIL_BUDGET_BASE = 800
_DETAIL_PER_CHAPTER_BUDGET = 400
_DETAIL_MIN_BUDGET = 4000
DETAIL_MAX_BUDGET = 32000

# 一次卷细化的**LLM 调用次数上限**。
#
# 为什么需要：失败处理链是「重试一次 → 对半拆批 → 再拆批」，
# 一批 6 章最坏会打 12 次调用（1 + 1 重试 + 拆批树）。
# 20 章的卷最坏 ≈ 40 次 —— 多卷并行时耗时飙升，还容易撞上游限流。
# 超过这个数就**直接给占位概要**（诚实标注「待细化」），不再递归。
#
# ⚠️ 正常路径（模型不失败）只用「批次数」次调用，远低于这个上限，
#    所以正常体验完全不受影响 —— 这只是给"模型一直失败"兜底。
MAX_CALLS_PER_VOLUME = 24


class _CallBudget:
    """一卷细化的调用次数预算（可跨并发批次共享）。

    为什么要单独一个类：卷内各批是**并行**跑的，
    用一个普通整数在并发下会算错（``+=`` 不是原子的），必须走对象方法。

    ⚠️ 单线程事件循环里"检查 + 自增"之间没有 await 点，
    所以这里是**真原子**的（不会有两个批次抢到同一个额度）。
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used = 0

    def take(self) -> bool:
        """占用一次调用额度；返回 False 表示预算已用尽。

        :return: True = 额度已占用，可以继续调用；False = 预算耗尽
        """
        if self._used >= self._limit:
            return False
        self._used += 1
        return True

    @property
    def used(self) -> int:
        """已用掉的调用次数。"""
        return self._used

    @property
    def remaining(self) -> int:
        """还剩多少次可用。"""
        return max(0, self._limit - self._used)


def split_batches(
    chapters: list[dict[str, Any]], size: int = DETAIL_BATCH_SIZE
) -> list[list[dict[str, Any]]]:
    """把一卷的章节切成若干批（每批 ≤ ``size`` 章）。

    :param chapters: 该卷的章节骨架（有序）
    :param size: 每批最多多少章
    :return: 批次列表（顺序与原章节一致）
    """
    if size < 1:
        size = 1
    return [chapters[i : i + size] for i in range(0, len(chapters), size)]


def detail_budget(chapter_count: int) -> int:
    """一批章节的正文预算（token）。

    :param chapter_count: 这一批有多少章
    :return: 正文预算；有下限（保证思考吃不掉）与上限（别把模型打爆）
    """
    raw = _DETAIL_BUDGET_BASE + max(0, chapter_count) * _DETAIL_PER_CHAPTER_BUDGET
    return min(DETAIL_MAX_BUDGET, max(_DETAIL_MIN_BUDGET, raw))


def chapters_skeleton_text(chapters: list[dict[str, Any]]) -> str:
    """把章节骨架渲染成给阶段二 prompt 用的文本（编号从 1 开始）。"""
    lines: list[str] = []
    for i, chapter in enumerate(chapters, start=1):
        title = str(chapter.get("title") or "").strip()
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


def placeholder_chapter(chapter: dict[str, Any], volume: dict[str, Any]) -> dict[str, Any]:
    """细化彻底失败时的占位概要。

    诚实标注「待细化」而不是编剧情 —— 假的概要会被作者当真大纲去写正文。
    章号与标题来自骨架，所以用户能一眼定位到缺哪一章。

    :param chapter: 骨架里的章节条目
    :param volume: 所属卷（提供卷名/卷概要作为上下文）
    :return: ``{"summary": ..., "key_events": []}``
    """
    title = str(chapter.get("title") or "").strip() or "本章"
    volume_name = str(volume.get("name") or "").strip()
    volume_summary = str(volume.get("summary") or "").strip()
    context = volume_summary or (f"属于《{volume_name}》" if volume_name else "")
    tail = f"{context}。" if context else ""
    return {
        "summary": f"【待细化】{title} —— {tail}本章概要尚未生成，可重新生成该卷。",
        "key_events": [],
    }


def align_detail(
    detail: list[Any], batch: list[dict[str, Any]], volume: dict[str, Any]
) -> list[dict[str, Any]]:
    """把模型返回的批次结果与批次章节对齐（**同长同序**）。

    模型可能少给、多给 —— 这里按**下标**对齐（阶段二的 prompt 已要求同序同长），
    缺的位置用占位概要补上：绝不留"只有标题"的空章节。

    :param detail: 模型返回的 ``chapters`` 列表
    :param batch: 本批次的章节骨架
    :param volume: 所属卷（占位概要用）
    :return: 与 ``batch`` 等长、同序的 ``{"summary", "key_events"}`` 列表
    """
    aligned: list[dict[str, Any]] = []
    for i, chapter in enumerate(batch):
        extra = detail[i] if i < len(detail) and isinstance(detail[i], dict) else {}
        summary = str(extra.get("summary") or "").strip()
        raw_events = extra.get("key_events")
        events = (
            [str(e).strip() for e in raw_events if str(e).strip()]
            if isinstance(raw_events, list)
            else []
        )
        if not summary and not events:
            aligned.append(placeholder_chapter(chapter, volume))
        else:
            aligned.append({"summary": summary, "key_events": events})
    return aligned


# ===== 阶段二执行器 ===


class VolumeDetailBuilder:
    """阶段二：给各卷补章概要与关键事件。

    负责分批、重试、拆批与占位兜底（策略见模块 docstring）。
    不碰数据库、不管事件协议 —— 事件由调用方
    （:class:`src.services.outline_two_phase.TwoPhaseOutlineBuilder`）转发。
    """

    def __init__(
        self,
        llm: LLMClientLike,
        *,
        genre: str,
        plot_summary: str,
        scale: OutlineScale,
        max_concurrent: int = MAX_CONCURRENT_DETAIL_CALLS,
    ) -> None:
        self._llm = llm
        self._genre = genre
        self._plot_summary = plot_summary
        self._scale = scale
        self._max_concurrent = max_concurrent
        # 并发闸门懒创建：asyncio.Semaphore 会绑定事件循环，
        # 不能在构造时创建 —— 同一个 builder 可能被不同 loop 用。
        self._semaphore: asyncio.Semaphore | None = None

    def _gate(self) -> asyncio.Semaphore:
        """取（并懒创建）并发闸门。"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    # ===== 对外入口 =====

    async def detail_volume(
        self, index: int, volume: dict[str, Any], queue: asyncio.Queue
    ) -> dict[str, Any]:
        """流式细化一卷（分批 + 重试 + 兜底）。"""
        chapters = list(volume.get("chapters") or [])
        if not chapters:
            return {
                "name": volume.get("name", ""),
                "summary": volume.get("summary", ""),
                "chapters": [],
            }
        batches = split_batches(chapters)
        budget = _CallBudget(MAX_CALLS_PER_VOLUME)
        results = await asyncio.gather(
            *(
                self._detail_batch(
                    index,
                    volume,
                    batch,
                    queue,
                    batch_no=i + 1,
                    batch_total=len(batches),
                    budget=budget,
                )
                for i, batch in enumerate(batches)
            )
        )
        detail_chapters: list[dict[str, Any]] = []
        for item in results:
            detail_chapters.extend(item)
        return {
            "name": volume.get("name", ""),
            "summary": volume.get("summary", ""),
            "chapters": detail_chapters,
        }

    async def detail_volume_nonstream(self, index: int, volume: dict[str, Any]) -> dict[str, Any]:
        """非流式细化一卷（同样分批 + 重试 + 兜底）。"""
        chapters = list(volume.get("chapters") or [])
        if not chapters:
            return {
                "name": volume.get("name", ""),
                "summary": volume.get("summary", ""),
                "chapters": [],
            }
        batches = split_batches(chapters)
        budget = _CallBudget(MAX_CALLS_PER_VOLUME)
        results = await asyncio.gather(
            *(
                self._detail_batch_nonstream(
                    index,
                    volume,
                    batch,
                    batch_no=i + 1,
                    batch_total=len(batches),
                    budget=budget,
                )
                for i, batch in enumerate(batches)
            )
        )
        detail_chapters: list[dict[str, Any]] = []
        for item in results:
            detail_chapters.extend(item)
        return {
            "name": volume.get("name", ""),
            "summary": volume.get("summary", ""),
            "chapters": detail_chapters,
        }

    # ===== 内部：重试 / 拆批 =====

    async def _detail_batch(
        self,
        index: int,
        volume: dict[str, Any],
        batch: list[dict[str, Any]],
        queue: asyncio.Queue,
        *,
        batch_no: int = 1,
        batch_total: int = 1,
        depth: int = 0,
        budget: _CallBudget,
    ) -> list[dict[str, Any]]:
        """细化一批章节（失败处理链见模块 docstring）。

        ⚠️ LLM 的**系统级**错误（网络/鉴权）不在这里吞 —— 直接往上抛，
        由调用方转成 ``volume_error`` 事件（用户需要知道出事了）。

        ⚠️ 调用预算用尽 → 整批直接给占位概要，不再递归（见 ``_CallBudget``）。
        """
        if not budget.take():
            logger.warning(
                "outline volume {} batch {}/{}: call budget exhausted, using placeholders",
                index,
                batch_no,
                batch_total,
            )
            return [placeholder_chapter(c, volume) for c in batch]
        batch_budget = detail_budget(len(batch))
        try:
            return await self._call_detail_batch(
                index,
                volume,
                batch,
                queue,
                budget=batch_budget,
                batch_no=batch_no,
                batch_total=batch_total,
            )
        except TwoPhaseOutlineError as e:
            logger.warning(
                "outline volume {} batch {}/{} failed ({} chapters): {}",
                index,
                batch_no,
                batch_total,
                len(batch),
                e,
            )
            if depth == 0 and budget.take():
                # 预算翻倍重试一次（思考吃额度是空内容的主因）
                try:
                    return await self._call_detail_batch(
                        index,
                        volume,
                        batch,
                        queue,
                        budget=min(batch_budget * 2, DETAIL_MAX_BUDGET),
                        batch_no=batch_no,
                        batch_total=batch_total,
                    )
                except TwoPhaseOutlineError:
                    pass
            if len(batch) > 1:
                mid = len(batch) // 2
                left = await self._detail_batch(
                    index,
                    volume,
                    batch[:mid],
                    queue,
                    batch_no=batch_no,
                    batch_total=batch_total,
                    depth=depth + 1,
                    budget=budget,
                )
                right = await self._detail_batch(
                    index,
                    volume,
                    batch[mid:],
                    queue,
                    batch_no=batch_no,
                    batch_total=batch_total,
                    depth=depth + 1,
                    budget=budget,
                )
                return left + right
            return [placeholder_chapter(batch[0], volume)]

    async def _detail_batch_nonstream(
        self,
        index: int,
        volume: dict[str, Any],
        batch: list[dict[str, Any]],
        *,
        batch_no: int = 1,
        batch_total: int = 1,
        depth: int = 0,
        budget: _CallBudget,
    ) -> list[dict[str, Any]]:
        """非流式细化一批章节（与流式版同一套重试 / 拆批 / 占位策略）。"""
        if not budget.take():
            logger.warning(
                "outline volume {} batch {}/{}: call budget exhausted, using placeholders",
                index,
                batch_no,
                batch_total,
            )
            return [placeholder_chapter(c, volume) for c in batch]
        batch_budget = detail_budget(len(batch))
        try:
            return await self._call_detail_batch_nonstream(
                index,
                volume,
                batch,
                budget=batch_budget,
                batch_no=batch_no,
                batch_total=batch_total,
            )
        except TwoPhaseOutlineError as e:
            logger.warning(
                "outline volume {} batch {}/{} failed ({} chapters): {}",
                index,
                batch_no,
                batch_total,
                len(batch),
                e,
            )
            if depth == 0 and budget.take():
                try:
                    return await self._call_detail_batch_nonstream(
                        index,
                        volume,
                        batch,
                        budget=min(batch_budget * 2, DETAIL_MAX_BUDGET),
                        batch_no=batch_no,
                        batch_total=batch_total,
                    )
                except TwoPhaseOutlineError:
                    pass
            if len(batch) > 1:
                mid = len(batch) // 2
                left = await self._detail_batch_nonstream(
                    index,
                    volume,
                    batch[:mid],
                    batch_no=batch_no,
                    batch_total=batch_total,
                    depth=depth + 1,
                    budget=budget,
                )
                right = await self._detail_batch_nonstream(
                    index,
                    volume,
                    batch[mid:],
                    batch_no=batch_no,
                    batch_total=batch_total,
                    depth=depth + 1,
                    budget=budget,
                )
                return left + right
            return [placeholder_chapter(batch[0], volume)]

    # ===== 内部：真正的 LLM 调用 =====

    def _prompt(
        self,
        index: int,
        volume: dict[str, Any],
        batch: list[dict[str, Any]],
        batch_no: int,
        batch_total: int,
    ) -> str:
        """拼装某**一批**章节的细节 prompt。

        ⚠️ 只喂**这一批**的章节骨架：批次小 → 推理模型思考少 → 正文额度不会被吃光。
        """
        return load_phase_prompt("volume_detail").format(
            genre=self._genre,
            plot=self._plot_summary,
            volume_index=index + 1,
            volume_count=self._scale.volume_count,
            volume_name=str(volume.get("name") or ""),
            volume_summary=str(volume.get("summary") or "（无）"),
            chapters_json=chapters_skeleton_text(batch),
            words_per_chapter=self._scale.words_per_chapter,
            batch_hint=f"第 {batch_no}/{batch_total} 批，本批共 {len(batch)} 章",
        )

    async def _call_detail_batch(
        self,
        index: int,
        volume: dict[str, Any],
        batch: list[dict[str, Any]],
        queue: asyncio.Queue,
        *,
        budget: int,
        batch_no: int,
        batch_total: int,
    ) -> list[dict[str, Any]]:
        """流式调用 LLM 细化一批章节，返回与 ``batch`` 等长、同序的条目列表。"""
        prompt = self._prompt(index, volume, batch, batch_no, batch_total)
        splitter = ThinkSplitter()
        full_text = ""
        async with self._gate():
            stream = await self._llm.chat(
                [ChatMessage("user", prompt)],
                temperature=0.5,
                max_tokens=budget,
                stream=True,
            )
            async for delta in stream:
                if not delta:
                    continue
                for kind, text in splitter.feed(delta):
                    if kind == KIND_THINK:
                        await queue.put(thinking_event(text, index=index))
                        continue
                    full_text += text
        return self._parse_detail(index, full_text, batch, volume)

    async def _call_detail_batch_nonstream(
        self,
        index: int,
        volume: dict[str, Any],
        batch: list[dict[str, Any]],
        *,
        budget: int,
        batch_no: int,
        batch_total: int,
    ) -> list[dict[str, Any]]:
        """非流式调用 LLM 细化一批章节。"""
        prompt = self._prompt(index, volume, batch, batch_no, batch_total)
        async with self._gate():
            resp = await self._llm.chat(
                [ChatMessage("user", prompt)],
                temperature=0.5,
                max_tokens=budget,
                stream=False,
            )
        return self._parse_detail(index, getattr(resp, "content", "") or "", batch, volume)

    @staticmethod
    def _parse_detail(
        index: int,
        raw_text: str,
        batch: list[dict[str, Any]],
        volume: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """解析模型输出并与批次对齐。

        :raises TwoPhaseOutlineError: 空内容 / JSON 解析失败（调用方据此重试）
        """
        cleaned = strip_thinking(raw_text)
        if not cleaned.strip():
            raise TwoPhaseOutlineError(f"第 {index + 1} 卷返回空内容")
        try:
            raw = extract_json_object(cleaned)
        except ValueError:
            partial = parse_partial_json(cleaned)
            if partial is None:
                raise TwoPhaseOutlineError(f"第 {index + 1} 卷 JSON 解析失败") from None
            raw = partial
        if not isinstance(raw, dict):
            raise TwoPhaseOutlineError(f"第 {index + 1} 卷 JSON 形状不对")
        detail = raw.get("chapters")
        if not isinstance(detail, list):
            detail = []
        return align_detail(detail, batch, volume)
