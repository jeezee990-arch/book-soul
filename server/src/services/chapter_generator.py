"""章节正文生成器（Phase 4.3 流式）。

职责：
- 加载上下文（人物卡 / 大纲 / 前章摘要 / 前章尾部 / 用户 prompt）
- 流式调 LLM
- 暴露 AsyncIterator[str]，由 API 层包装成 ndjson 返回

不做的事：
- 不写 ChapterVersion 记录（流式输出可能中途失败；写版本由前端拿到完整文本后调 update_content）
- prompt 加载 / 格式化：见 :mod:`src.core.chapter_context`
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chapter_context import (
    format_characters,
    format_outline,
    get_chapter_outline,
    get_previous_tail,
    get_recent_summaries,
    load_chapter_generation_prompt,
)
from ..core.llm.base import ChatMessage, describe_llm_error
from ..models.chapter import Chapter
from ..models.character import Character
from ..models.novel import Novel
from ..models.outline import Outline


class _LLMClientLike(Protocol):
    """流式 LLM 客户端最小接口（duck typing）。"""

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


class ChapterGenerationError(Exception):
    """章节生成失败。"""


class ChapterGenerator:
    """流式章节生成器。

    使用：
        gen = ChapterGenerator(session)
        async for chunk in gen.stream_generate(chapter_id=42, user_prompt="..."):
            ...
    """

    def __init__(self, session: AsyncSession, llm_client: _LLMClientLike | None = None) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("chapter_generation")
        return self._llm

    async def _release_llm(self) -> None:
        """关闭懒加载的客户端，避免连接泄漏。"""
        if self._llm_override is not None:
            return
        aclose = getattr(self._llm, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            finally:
                self._llm = None

    # ===== 上下文加载（薄包装，复用 chapter_context） =====
    async def _load_chapter(self, chapter_id: int) -> Chapter:
        chapter = await self.session.get(Chapter, chapter_id)
        if chapter is None:
            raise ChapterGenerationError(f"Chapter {chapter_id} not found")
        return chapter

    async def _load_novel(self, novel_id: int) -> Novel:
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise ChapterGenerationError(f"Novel {novel_id} not found")
        return novel

    async def _load_active_characters(self, novel_id: int) -> list[Character]:
        from sqlalchemy import select

        stmt = (
            select(Character)
            .where(Character.novel_id == novel_id, Character.is_active.is_(True))
            .order_by(Character.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def _load_outline(self, novel_id: int) -> Outline | None:
        from sqlalchemy import select

        stmt = (
            select(Outline)
            .where(Outline.novel_id == novel_id)
            .order_by(Outline.id.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ===== 主入口 =====
    async def stream_generate(
        self,
        *,
        chapter_id: int,
        user_prompt: str = "",
        target_word_count: int = 4000,
    ) -> AsyncIterator[str]:
        """流式生成章节正文。

        失败：抛 :class:`ChapterGenerationError`（在 yield 之前 / 之后均可能）。
        """
        chapter = await self._load_chapter(chapter_id)
        novel = await self._load_novel(chapter.novel_id)
        characters = await self._load_active_characters(chapter.novel_id)
        outline = await self._load_outline(chapter.novel_id)
        chapter_outline = await get_chapter_outline(self.session, chapter, outline)
        recent_summaries = await get_recent_summaries(self.session, chapter.novel_id, n=3)
        previous_tail = await get_previous_tail(
            self.session, chapter.novel_id, chapter.chapter_number - 1, chars=1500
        )

        prompt_tpl = load_chapter_generation_prompt()
        try:
            full_prompt = prompt_tpl.format(
                novel_name=novel.name,
                genre=novel.genre,
                outline_mode=novel.outline_mode or "complete",
                all_characters=format_characters(characters),
                novel_outline=format_outline(outline),
                chapter_outline=chapter_outline,
                recent_summaries=recent_summaries,
                previous_tail=previous_tail,
                target_word_count=target_word_count,
                user_prompt=user_prompt.strip() or "（无）",
            )
        except KeyError as e:
            raise ChapterGenerationError(f"Prompt template missing key: {e}") from e

        llm = self._get_llm()
        try:
            stream_iter = await llm.chat(
                [ChatMessage("user", full_prompt)],
                temperature=0.7,
                stream=True,
            )
        except Exception as e:  # noqa: BLE001
            await self._release_llm()
            logger.error("LLM stream init failed: {}", describe_llm_error(e))
            raise ChapterGenerationError(describe_llm_error(e)) from e

        # stream_iter 是 AsyncIterator[str]；逐个 yield
        try:
            async for delta in stream_iter:  # type: ignore[union-attr]
                if delta:
                    yield delta
        finally:
            await self._release_llm()


__all__ = [
    "ChapterGenerator",
    "ChapterGenerationError",
]
