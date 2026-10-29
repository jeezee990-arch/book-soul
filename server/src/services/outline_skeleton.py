"""两阶段大纲 —— **阶段一：卷章骨架**。

为什么单独一个文件
------------------
:mod:`src.services.outline_two_phase` 只负责**编排**（跑阶段一 → 跑阶段二 →
合并 → 发事件）。阶段一自己有一套完整逻辑（prompt 拼装 / 流式增量解析 /
结构清洗 / 骨架校验），拆出来单放，两个文件都远在 500 行以内。

阶段一产出
----------
``{"volumes": [{"name", "summary", "chapters": [{"title"}]}], "overall_theme": ...}``
—— 只有卷名、卷概要、章标题。章概要与关键事件由阶段二补（见
:mod:`src.services.outline_detail`）。

为什么骨架要"半截 JSON 容错解析"
--------------------------------
流式过程中模型的 JSON 经常是**残缺**的（还在吐）。这里用
:func:`src.core.llm.partial_json.parse_partial_json` 做容错解析，
让用户**边生成边看到**已经写完的那几章，而不是等全部结束才一次性出现。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from ..core.llm.base import ChatMessage, LLMClientLike, describe_llm_error
from ..core.llm.formatting import extract_json_object, strip_thinking
from ..core.llm.partial_json import parse_partial_json
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..core.llm.thinking import thinking_event
from ..core.outline_scale import OutlineScale
from .outline_errors import TwoPhaseOutlineError
from .outline_prompts import load_phase_prompt

__all__ = [
    "LLMClientLike",
    "SkeletonPhase",
    "count_chapters",
    "sanitize_skeleton",
]

# 增量解析节流：每积累这么多字符（或间隔超过下面这个秒数）才解析一次。
#
# 为什么节流：每收到一个 delta 就解析一次半截 JSON，CPU 开销白给，
# 而用户看不到区别。
PARTIAL_PARSE_MIN_CHARS = 150
PARTIAL_PARSE_MAX_INTERVAL = 0.3


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


def count_chapters(structure: dict[str, Any]) -> int:
    """统计结构里的章节数（给前端显示"已生成 N 章"）。"""
    volumes = structure.get("volumes")
    if not isinstance(volumes, list):
        return 0
    total = 0
    for volume in volumes:
        if isinstance(volume, dict) and isinstance(volume.get("chapters"), list):
            total += len(volume["chapters"])
    return total


class SkeletonPhase:
    """阶段一：卷章骨架生成。

    职责边界：**只产出骨架**（卷名 / 卷概要 / 章标题），不碰细节、不碰数据库。
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
        self._genre = genre
        self._plot_summary = plot_summary
        self._keywords = keywords or []
        self._scale = scale
        self._outline_type = outline_type
        self._user_extra = user_extra or ""
        # 续写模式：带上"已有大纲 + 已写章节"的上下文，骨架 prompt 换一份
        self._continue_context = continue_context

    def prompt(self) -> str:
        """拼装阶段一 prompt。

        续写模式（``continue_context`` 有值）用另一份模板：必须承接已有剧情。
        """
        kw = ", ".join(self._keywords) if self._keywords else "（无）"
        extra = self._user_extra.strip()
        extra_block = extra if extra else "（无）"

        if self._continue_context is not None:
            ctx = self._continue_context
            return load_phase_prompt("continue_skeleton").format(
                genre=self._genre,
                plot=self._plot_summary,
                keywords=kw,
                existing_context=ctx.get("existing_context", "（无）"),
                written_context=ctx.get("written_context", "（暂无已写章节）"),
                last_volume_name=ctx.get("last_volume_name", "已有卷"),
                volume_count=self._scale.volume_count,
                chapters_per_volume=self._scale.chapters_per_volume,
                words_per_chapter=self._scale.words_per_chapter,
                user_extra=extra_block,
            )

        mode_block = ""
        if self._outline_type == "semi_open":
            mode_block = (
                "\n- 本次只生成**前期**，故事在此停下；"
                "JSON 里额外给出 `suspense_hook`（悬念钩子，20-50字），"
                "说明后续可以从哪里继续。\n"
            )
        return load_phase_prompt("skeleton").format(
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

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        """流式生成卷章骨架。

        产出：``thinking`` / ``partial``（增量结构）/ ``skeleton``（完成）。
        """
        prompt = self.prompt()
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
            async for delta in stream:
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
                        if partial:
                            cleaned = sanitize_skeleton(partial, outline_type=self._outline_type)
                            if cleaned != last_partial:
                                last_partial = cleaned
                                yield {
                                    "event": "partial",
                                    "structure": cleaned,
                                    "chapters_done": count_chapters(cleaned),
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
                    "chapters_done": count_chapters(cleaned),
                }

        cleaned_text = strip_thinking(full_text)
        if not cleaned_text.strip():
            raise TwoPhaseOutlineError("LLM returned empty content (skeleton phase)")

        skeleton = self.parse(cleaned_text)
        if not skeleton.get("volumes"):
            raise TwoPhaseOutlineError(
                "LLM output structure invalid: 骨架为空（没有产出任何卷/章）"
            )
        yield {
            "event": "skeleton",
            "structure": skeleton,
            "chapters_done": count_chapters(skeleton),
            "first_delta_sec": (
                round(first_delta_at - t0, 2) if first_delta_at is not None else None
            ),
        }

    def parse(self, text: str) -> dict[str, Any]:
        """解析阶段一输出；整段解析失败时退回半截 JSON 容错解析。"""
        try:
            raw = extract_json_object(text)
        except ValueError:
            partial = parse_partial_json(text)
            if partial is None:
                raise TwoPhaseOutlineError("骨架 JSON 解析失败") from None
            raw = partial
        return sanitize_skeleton(raw, outline_type=self._outline_type)
