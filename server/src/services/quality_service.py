"""Quality check service (Phase 5.2/5.3/5.4)。

职责：
- 加载 chapter 内容 + 人物卡 + 题材规则
- 5 个维度（writing / logic / pacing / consistency / genre）**并行** 调 LLM
- 解析 LLM 返回的 JSON，校验 + 整合成 :class:`QualityReport`
- 不存历史报告（Phase 6.2 藏书馆再做）

不在范围内：
- 流式（质检一次性返回，不需要逐字）
- 多 chapter 批量（v1 仅单 chapter）
- 雷达图数据格式（前端自行做）
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.quality.prompts import (
    QUALITY_DIMENSIONS,
    QualityPromptError,
    format_characters_for_quality,
    load_genre_rules,
    load_quality_prompt,
)
from ..core.queue_merge import merge_queue_events
from ..models.chapter import Chapter, ChapterVersion
from ..models.character import Character
from ..models.novel import Novel


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口（duck typing）。"""

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


class QualityCheckError(Exception):
    """质检失败。"""


@dataclass
class DimensionIssue:
    """单个维度的问题条目。"""

    type: str = ""
    character: str = ""
    quote: str = ""
    problem: str = ""
    suggestion: str = ""


@dataclass
class DimensionResult:
    """单个维度的评分结果。"""

    dimension: str
    score: float
    issues: list[DimensionIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    error: str | None = None  # 调 LLM 失败时填


@dataclass
class QualityReport:
    """5 维度整合后的报告。"""

    chapter_id: int
    novel_id: int
    chapter_title: str
    genre: str
    total_score: float  # 5 维度均分
    dimension_scores: dict[str, float]  # {"writing": 7.5, ...}
    dimension_results: list[DimensionResult]  # 完整结果
    issues: list[DimensionIssue]  # 合并所有维度
    suggestions: list[str]  # 合并所有维度
    provider: str = "unknown"
    model: str = ""


class QualityService:
    """章节质检服务。"""

    def __init__(self, session: AsyncSession, llm_client: _LLMClientLike | None = None) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("quality_check")
        return self._llm

    async def _release_llm(self) -> None:
        if self._llm_override is not None:
            return
        aclose = getattr(self._llm, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            finally:
                self._llm = None

    # ===== 上下文 =====
    async def _load_chapter(self, chapter_id: int) -> Chapter:
        chapter = await self.session.get(Chapter, chapter_id)
        if chapter is None:
            raise QualityCheckError(f"Chapter {chapter_id} not found")
        return chapter

    async def _load_novel(self, novel_id: int) -> Novel:
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise QualityCheckError(f"Novel {novel_id} not found")
        return novel

    async def _get_chapter_content(self, chapter: Chapter) -> str:
        if chapter.current_version_id is None:
            return ""
        version = await self.session.get(ChapterVersion, chapter.current_version_id)
        return version.content if version else ""

    async def _load_active_characters(self, novel_id: int) -> list[Character]:
        stmt = (
            select(Character)
            .where(Character.novel_id == novel_id, Character.is_active.is_(True))
            .order_by(Character.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    # ===== 单维度 =====
    async def _evaluate_dimension(
        self,
        dimension: str,
        chapter: Chapter,
        chapter_content: str,
        novel: Novel,
        characters: list[Character],
    ) -> DimensionResult:
        """对单个维度调 LLM 评分。失败时返回带 error 的 result（不让一个维度拖垮整体）。"""
        try:
            prompt_tpl = load_quality_prompt(dimension)
        except QualityPromptError as e:
            return DimensionResult(dimension=dimension, score=0.0, error=f"prompt load failed: {e}")

        if dimension == "consistency":
            extra = format_characters_for_quality(characters)
        elif dimension == "genre":
            extra = load_genre_rules(novel.genre)
        else:
            extra = ""

        try:
            full_prompt = prompt_tpl.format(
                chapter_content=chapter_content,
                genre=novel.genre,
                title=chapter.title or "（未命名）",
                all_characters=extra,
                genre_rules=extra,
            )
        except KeyError as e:
            return DimensionResult(
                dimension=dimension, score=0.0, error=f"prompt template missing key: {e}"
            )

        llm = self._get_llm()
        try:
            resp = await llm.chat(
                [ChatMessage("user", full_prompt)],
                temperature=0.3,
                max_tokens=2048,
                stream=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed (quality/{}): {}", dimension, describe_llm_error(e))
            return DimensionResult(dimension=dimension, score=0.0, error=describe_llm_error(e))

        raw = getattr(resp, "content", "") or ""
        return self._parse_dimension_response(dimension, raw)

    @staticmethod
    def _parse_dimension_response(dimension: str, raw: str) -> DimensionResult:
        """解析 LLM 返回的 JSON。"""
        if not raw.strip():
            return DimensionResult(
                dimension=dimension, score=0.0, error="LLM returned empty content"
            )
        try:
            obj = QualityService._extract_json(raw)
        except ValueError as e:
            return DimensionResult(dimension=dimension, score=0.0, error=f"invalid JSON: {e}")

        if not isinstance(obj, dict):
            return DimensionResult(
                dimension=dimension, score=0.0, error="LLM output is not a JSON object"
            )

        try:
            score = float(obj.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        # 0-10 范围
        score = max(0.0, min(10.0, score))

        issues_raw = obj.get("issues") or []
        if not isinstance(issues_raw, list):
            issues_raw = []
        issues = [
            DimensionIssue(
                type=str(i.get("type", "")) if isinstance(i, dict) else "",
                character=str(i.get("character", "")) if isinstance(i, dict) else "",
                quote=str(i.get("quote", "")) if isinstance(i, dict) else "",
                problem=str(i.get("problem", "")) if isinstance(i, dict) else "",
                suggestion=str(i.get("suggestion", "")) if isinstance(i, dict) else "",
            )
            for i in issues_raw
        ]

        suggestions_raw = obj.get("suggestions") or []
        if not isinstance(suggestions_raw, list):
            suggestions_raw = []
        suggestions = [str(s) for s in suggestions_raw]

        return DimensionResult(
            dimension=dimension, score=score, issues=issues, suggestions=suggestions
        )

    @staticmethod
    def _extract_json(text: str) -> Any:
        """从 markdown 文本里抠 JSON（找首个 { 到匹配的 }）。"""
        # 先尝试 strip thinking
        if "</think>" in text:
            text = text.split("</think>", 1)[-1]
        # 找第一个 { 和最后一个 }
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found")
        # 用 stack 找匹配的 }
        depth = 0
        in_str = False
        escape = False
        end = -1
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == -1:
            raise ValueError("No matching JSON closing brace")
        return json.loads(text[start:end])

    # ===== 主入口 =====
    async def check_chapter(self, novel_id: int, chapter_id: int) -> QualityReport:
        """对单章节做 5 维度质检（并行）。"""
        chapter = await self._load_chapter(chapter_id)
        if chapter.novel_id != novel_id:
            raise QualityCheckError(f"Chapter {chapter_id} not in novel {novel_id}")
        novel = await self._load_novel(novel_id)
        chapter_content = await self._get_chapter_content(chapter)
        if not chapter_content.strip():
            raise QualityCheckError(
                f"Chapter {chapter_id} has no content (current_version is empty)"
            )
        characters = await self._load_active_characters(novel_id)

        # 并行 5 维度
        tasks = [
            self._evaluate_dimension(dim, chapter, chapter_content, novel, characters)
            for dim in QUALITY_DIMENSIONS
        ]
        results: list[DimensionResult] = list(await asyncio.gather(*tasks))

        # 整合
        dim_scores: dict[str, float] = {}
        valid_scores: list[float] = []
        all_issues: list[DimensionIssue] = []
        all_suggestions: list[str] = []
        for r in results:
            if r.error is None:
                dim_scores[r.dimension] = r.score
                valid_scores.append(r.score)
            else:
                # 出错的维度：记 0 但不计入均分
                dim_scores[r.dimension] = 0.0
                logger.warning("Dimension {} failed: {}", r.dimension, r.error)
            all_issues.extend(r.issues)
            all_suggestions.extend(r.suggestions)
        total = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0

        provider = "unknown"
        model = ""
        llm = self._llm
        if llm is not None:
            provider = str(getattr(llm, "provider", "unknown") or "unknown")
            model = str(getattr(llm, "model", "") or "")

        return QualityReport(
            chapter_id=chapter.id,
            novel_id=novel.id,
            chapter_title=chapter.title or "（未命名）",
            genre=novel.genre,
            total_score=total,
            dimension_scores=dim_scores,
            dimension_results=results,
            issues=all_issues,
            suggestions=all_suggestions,
            provider=provider,
            model=model,
        )

    # ===== 流式（Phase 性能优化）=====

    async def stream_check_chapter(
        self,
        novel_id: int,
        chapter_id: int,
        *,
        user_extra: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """流式质检：5 维度**并行**调 LLM，单个完成即推送。

        协议：
        - ``{"event": "start", "dimensions": [...]}``
        - ``{"event": "dimension_done", "dim": "...", "score": ..., "issues": [...], "suggestions": [...], "error": null|"..."}``
        - ``{"event": "done", "chapter_id": ..., "novel_id": ..., "total_score": ..., "dimension_scores": {...}, "provider": "...", "model": "..."}``
        - ``{"event": "error", "message": "..."}``
        """
        try:
            chapter = await self._load_chapter(chapter_id)
            if chapter.novel_id != novel_id:
                raise QualityCheckError(f"Chapter {chapter_id} not in novel {novel_id}")
            novel = await self._load_novel(novel_id)
            chapter_content = await self._get_chapter_content(chapter)
            if not chapter_content.strip():
                raise QualityCheckError(f"Chapter {chapter_id} has no content")
            characters = await self._load_active_characters(novel_id)
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "message": str(e)}
            return

        yield {"event": "start", "dimensions": list(QUALITY_DIMENSIONS)}

        # 并行跑 + 每个维度完成后立即发事件（用 queue 透出）
        queues: list[asyncio.Queue[dict[str, Any] | None]] = [
            asyncio.Queue() for _ in QUALITY_DIMENSIONS
        ]

        async def dim_runner(idx: int, dim: str) -> None:
            try:
                result = await self._evaluate_dimension(
                    dim, chapter, chapter_content, novel, characters
                )
            except Exception as e:  # noqa: BLE001
                result = DimensionResult(dimension=dim, score=0.0, error=str(e))
            payload = {
                "event": "dimension_done",
                "dim": dim,
                "score": result.score,
                "issues": [asdict(i) for i in result.issues],
                "suggestions": list(result.suggestions),
                "error": result.error,
            }
            await queues[idx].put(payload)
            await queues[idx].put(None)

        tasks = [
            asyncio.create_task(dim_runner(i, dim)) for i, dim in enumerate(QUALITY_DIMENSIONS)
        ]

        all_results: dict[str, DimensionResult] = {}
        try:
            async for payload in merge_queue_events(queues):
                all_results[payload["dim"]] = DimensionResult(
                    dimension=payload["dim"],
                    score=float(payload["score"]),
                    issues=[
                        DimensionIssue(
                            type=i.get("type", ""),
                            character=i.get("character", ""),
                            quote=i.get("quote", ""),
                            problem=i.get("problem", ""),
                            suggestion=i.get("suggestion", ""),
                        )
                        for i in payload["issues"]
                    ],
                    suggestions=payload["suggestions"],
                    error=payload["error"],
                )
                yield payload
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 整合
        dim_scores: dict[str, float] = {}
        valid_scores: list[float] = []
        all_issues: list[DimensionIssue] = []
        all_suggestions: list[str] = []
        for dim in QUALITY_DIMENSIONS:
            r = all_results.get(dim)
            if r is None:
                continue
            if r.error is None:
                dim_scores[dim] = r.score
                valid_scores.append(r.score)
            else:
                dim_scores[dim] = 0.0
                logger.warning("Dimension {} failed: {}", dim, r.error)
            all_issues.extend(r.issues)
            all_suggestions.extend(r.suggestions)
        total = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0

        provider = "unknown"
        model = ""
        if self._llm is not None:
            provider = str(getattr(self._llm, "provider", "unknown") or "unknown")
            model = str(getattr(self._llm, "model", "") or "")

        yield {
            "event": "done",
            "chapter_id": chapter.id,
            "novel_id": novel.id,
            "chapter_title": chapter.title or "（未命名）",
            "total_score": total,
            "dimension_scores": dim_scores,
            "issues": [asdict(i) for i in all_issues],
            "suggestions": all_suggestions,
            "provider": provider,
            "model": model,
        }


__all__ = [
    "QualityService",
    "QualityCheckError",
    "QualityReport",
    "DimensionResult",
    "DimensionIssue",
]
