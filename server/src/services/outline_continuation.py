"""AI 辅助续写大纲（基于已有大纲 + 已写章节生成后续卷章）。

对应需求
--------
「半开放式还差一半 —— 后续由作者自行创作或 **AI 辅助生成后续大纲**」。

与"从零生成大纲"的区别
----------------------
续写**不是**重新规划，而是接着已有故事往下写：

1. 读已有大纲（卷名 + 卷概要 + 章标题）→ 让新卷自然承接
2. 读**已写章节**（标题 + 概要/正文开头）→ 让剧情跟得上作者写到的位置
3. 复用两阶段机制：骨架（新增卷 + 章标题）→ 各卷并行补细节
4. 新卷**追加**到原大纲末尾，原有内容不动

流式协议
--------
- ``{"event": "start", "phase": "outline_continue", "volume_count": N}``
- ``{"event": "thinking" / "partial" / "skeleton" / "volume_start" / "volume_done" / "volume_error"}``
  —— 与普通大纲生成**同协议**，前端可以复用同一套渲染
- ``{"event": "done", "outline_id": ..., "structure": {...}（**完整**大纲）, "new_volumes": [...]}``
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.outline_scale import normalize_scale
from ..models.chapter import Chapter, ChapterVersion
from ..models.novel import Novel
from ..models.outline import Outline
from .outline_errors import OutlineGenerationError
from .outline_service import NovelNotFoundError, OutlineNotFoundError, OutlineService
from .outline_two_phase import TwoPhaseOutlineBuilder, TwoPhaseOutlineError

__all__ = ["OutlineContinuationService", "OutlineContinuationError"]

# 已有大纲 / 已写章节塞进 prompt 的长度上限（防 context 爆炸）
MAX_EXISTING_CONTEXT_CHARS = 4000
MAX_WRITTEN_CONTEXT_CHARS = 4000
# 每章塞多少字正文开头
CHAPTER_EXCERPT_CHARS = 300


class OutlineContinuationError(OutlineGenerationError):
    """续写大纲失败。"""


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


def _volumes_of(structure: dict[str, Any]) -> list[dict[str, Any]]:
    """取结构里的卷列表（没有就空）。"""
    volumes = structure.get("volumes")
    if not isinstance(volumes, list):
        return []
    return [v for v in volumes if isinstance(v, dict)]


def _build_existing_context(volumes: list[dict[str, Any]]) -> str:
    """把已有大纲渲染成 prompt 上下文。"""
    lines: list[str] = []
    for volume in volumes:
        name = str(volume.get("name") or "未命名卷")
        lines.append(f"《{name}》")
        summary = volume.get("summary")
        if isinstance(summary, str) and summary.strip():
            lines.append(f"  概要：{summary.strip()}")
        chapters = volume.get("chapters")
        if isinstance(chapters, list):
            titles = [
                str(c.get("title") or "").strip()
                for c in chapters
                if isinstance(c, dict) and str(c.get("title") or "").strip()
            ]
            if titles:
                lines.append("  章节：" + " / ".join(titles))
    text = "\n".join(lines)
    return text[:MAX_EXISTING_CONTEXT_CHARS]


async def _build_written_context(session: AsyncSession, novel_id: int) -> str:
    """把已写章节渲染成 prompt 上下文（标题 + 概要/正文开头）。"""
    result = await session.execute(
        select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number)
    )
    chapters = list(result.scalars())
    if not chapters:
        return ""

    # 取每章当前版本的正文开头（比 outline 更能反映"写到哪了"）
    version_ids = [c.current_version_id for c in chapters if c.current_version_id]
    excerpts: dict[int, str] = {}
    if version_ids:
        vres = await session.execute(
            select(ChapterVersion).where(ChapterVersion.id.in_(version_ids))
        )
        for v in vres.scalars():
            content = (v.content or "").strip()
            excerpts[v.id] = content[:CHAPTER_EXCERPT_CHARS]

    lines: list[str] = []
    for chapter in chapters:
        title = (chapter.title or "").strip() or f"第 {chapter.chapter_number} 章"
        excerpt = ""
        if chapter.current_version_id:
            excerpt = excerpts.get(chapter.current_version_id, "")
        if not excerpt:
            excerpt = (chapter.outline or "").strip()[:CHAPTER_EXCERPT_CHARS]
        status = "已写" if chapter.word_count > 0 else chapter.status
        if excerpt:
            lines.append(f"第{chapter.chapter_number}章《{title}》（{status}）：{excerpt}")
        else:
            lines.append(f"第{chapter.chapter_number}章《{title}》（{status}）")
    return "\n".join(lines)[:MAX_WRITTEN_CONTEXT_CHARS]


class OutlineContinuationService:
    """续写大纲服务。"""

    def __init__(self, session: AsyncSession, llm_client: _LLMClientLike | None = None) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    def _get_llm(self, outline_type: str) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene(f"outline_{outline_type}")
        return self._llm

    async def _release_llm(self, llm: _LLMClientLike, owns: bool) -> None:
        aclose = getattr(llm, "aclose", None)
        if owns and aclose is not None:
            try:
                await aclose()
            finally:
                self._llm = None

    async def stream_continue(
        self,
        novel_id: int,
        outline_id: int,
        *,
        volume_count: int = 1,
        chapters_per_volume: int | None = None,
        words_per_chapter: int = 3000,
        keywords: list[str] | None = None,
        user_extra: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """流式续写大纲。

        :param volume_count: 新增几卷（1-5）
        :param chapters_per_volume: 每卷章数（缺省取已有大纲的平均值）
        :raises OutlineContinuationError: 大纲不存在 / 类型不支持 / 生成失败
        """
        try:
            outline, novel = await self._load(novel_id, outline_id)
        except (OutlineNotFoundError, NovelNotFoundError, OutlineContinuationError) as e:
            yield {"event": "error", "message": str(e)}
            return
        existing = _volumes_of(outline.structure or {})
        if not existing:
            yield {"event": "error", "message": "原大纲没有卷，无法续写"}
            return

        cpv = chapters_per_volume or _average_chapters_per_volume(existing)
        scale = normalize_scale(
            total_chapters=volume_count * cpv,
            chapters_per_volume=cpv,
            words_per_chapter=words_per_chapter,
        )
        existing_context = _build_existing_context(existing)
        written_context = await _build_written_context(self.session, novel_id)
        last_volume_name = str(existing[-1].get("name") or "已有卷")

        llm = self._get_llm(outline.outline_type)
        owns_client = self._llm_override is None
        provider = str(getattr(llm, "provider", "unknown") or "unknown")
        model = str(getattr(llm, "model", "") or "")
        t0 = time.monotonic()

        yield {
            "event": "start",
            "phase": "outline_continue",
            "outline_type": outline.outline_type,
            "volume_count": scale.volume_count,
            "chapters_per_volume": scale.chapters_per_volume,
            "words_per_chapter": scale.words_per_chapter,
            "existing_volumes": len(existing),
        }

        builder = TwoPhaseOutlineBuilder(
            llm,
            genre=novel.genre or "通用",
            plot_summary=novel.description or "",
            keywords=keywords or [],
            scale=scale,
            outline_type=outline.outline_type,
            user_extra=user_extra,
            continue_context={
                "existing_context": existing_context,
                "written_context": written_context or "（暂无已写章节）",
                "last_volume_name": last_volume_name,
            },
        )

        new_structure: dict[str, Any] | None = None
        try:
            async for event in builder.run():
                if event.get("event") == "structure_ready":
                    new_structure = event.get("structure") or {}
                yield event
        except TwoPhaseOutlineError as e:
            yield {"event": "error", "message": str(e)}
            return
        except Exception as e:  # noqa: BLE001
            logger.error("outline continuation failed: {}", describe_llm_error(e))
            yield {"event": "error", "message": describe_llm_error(e)}
            return
        finally:
            if owns_client:
                await self._release_llm(llm, owns=True)

        if not new_structure:
            yield {"event": "error", "message": "续写没有产出新卷"}
            return

        # ===== 合并进原大纲 =====
        merged = dict(outline.structure or {})
        old_volumes = list(_volumes_of(merged))
        new_volumes = list(_volumes_of(new_structure))
        merged["volumes"] = old_volumes + new_volumes
        # 悬念钩子：续写把钩子"用掉"了 → 清掉
        merged.pop("suspense_hook", None)
        merged["outline_type"] = outline.outline_type

        outline_service = OutlineService(self.session)
        try:
            outline_service._validate_structure(outline.outline_type, merged)  # noqa: SLF001
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "message": f"续写结果结构非法: {e}"}
            return

        outline.structure = merged
        await self.session.commit()
        await self.session.refresh(outline)

        yield {
            "event": "done",
            "outline_id": outline.id,
            "novel_id": novel.id,
            "outline_type": outline.outline_type,
            "structure": merged,
            "new_volumes": new_volumes,
            "provider": provider,
            "model": model,
            "elapsed_sec": round(time.monotonic() - t0, 2),
            "volume_count": len(new_volumes),
            "total_volumes": len(old_volumes) + len(new_volumes),
        }

    async def _load(self, novel_id: int, outline_id: int) -> tuple[Outline, Novel]:
        """加载大纲与作品；不存在抛对应异常。"""
        outline = await self.session.get(Outline, outline_id)
        if outline is None:
            raise OutlineNotFoundError(outline_id)
        if outline.novel_id != novel_id:
            raise OutlineNotFoundError(outline_id)
        if outline.outline_type == "freedom":
            raise OutlineContinuationError("创作型大纲（freedom）不支持续写")
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise NovelNotFoundError(novel_id)
        return outline, novel


def _average_chapters_per_volume(volumes: list[dict[str, Any]]) -> int:
    """已有大纲的平均每卷章数（缺省 10）。"""
    counts = [len(v.get("chapters") or []) for v in volumes if isinstance(v.get("chapters"), list)]
    counts = [c for c in counts if c > 0]
    if not counts:
        return 10
    return max(1, round(sum(counts) / len(counts)))
