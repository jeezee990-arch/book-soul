"""章节选区 / 全文重写器（Phase 4.4 流式）。

职责：
- 加载 ``chapter_rewrite.yaml`` 模板
- 拼上下文（人物卡 / 本章大纲 / 原文 / 用户要求）
- 流式调 LLM
- 暴露 AsyncIterator[str]，由 API 层包装成 ndjson 返回
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chapter_context import (
    ChapterContextError,
    format_characters,
    get_chapter_outline,
    load_chapter_rewrite_prompt,
)
from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.streaming import KIND_TEXT, ThinkSplitter
from ..core.prose_format import ProseFormatter
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


class ChapterRewriteError(Exception):
    """重写失败。"""


class ChapterRewriter:
    """流式选区 / 全文重写器。

    使用：
        rewriter = ChapterRewriter(session)
        async for chunk in rewriter.stream_rewrite(
            chapter_id=42,
            original_text="...",
            user_prompt="对话更紧凑",
        ):
            ...
    """

    def __init__(self, session: AsyncSession, llm_client: _LLMClientLike | None = None) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("chapter_rewrite")
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
            raise ChapterRewriteError(f"Chapter {chapter_id} not found")
        return chapter

    async def _load_novel(self, novel_id: int) -> Novel:
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise ChapterRewriteError(f"Novel {novel_id} not found")
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
            select(Outline).where(Outline.novel_id == novel_id).order_by(Outline.id.asc()).limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ===== 主入口 =====
    async def stream_rewrite(
        self,
        *,
        chapter_id: int,
        original_text: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        """流式重写选区 / 全文（**只吐正文**）。

        兼容入口；要拿到思考内容请用 :meth:`stream_rewrite_parts`。
        """
        async for kind, text in self.stream_rewrite_parts(
            chapter_id=chapter_id,
            original_text=original_text,
            user_prompt=user_prompt,
        ):
            if kind == KIND_TEXT:
                yield text

    async def stream_rewrite_parts(
        self,
        *,
        chapter_id: int,
        original_text: str,
        user_prompt: str,
    ) -> AsyncIterator[tuple[str, str]]:
        """流式重写，区分「思考」与「正文」。

        产出 ``(KIND_THINK, text)`` / ``(KIND_TEXT, text)``。

        ⚠️ 与 :meth:`ChapterGenerator.stream_generate_parts` 同一个理由
        （AGENTS.md §4.7）：思考内容不能被丢弃 —— 丢了思考期就是空窗，
        用户看到的是"生成卡住不动"。
        """
        if not original_text or not original_text.strip():
            raise ChapterRewriteError("original_text is empty")
        if not user_prompt or not user_prompt.strip():
            raise ChapterRewriteError("user_prompt is empty")

        chapter = await self._load_chapter(chapter_id)
        novel = await self._load_novel(chapter.novel_id)
        characters = await self._load_active_characters(chapter.novel_id)
        outline = await self._load_outline(chapter.novel_id)
        chapter_outline = await get_chapter_outline(self.session, chapter, outline)

        try:
            prompt_tpl = load_chapter_rewrite_prompt()
        except ChapterContextError as e:
            raise ChapterRewriteError(str(e)) from e

        try:
            full_prompt = prompt_tpl.format(
                genre=novel.genre,
                all_characters=format_characters(characters),
                chapter_outline=chapter_outline,
                original_text=original_text,
                user_prompt=user_prompt.strip(),
            )
        except KeyError as e:
            raise ChapterRewriteError(f"Rewrite prompt template missing key: {e}") from e

        llm = self._get_llm()
        try:
            stream_iter = await llm.chat(
                [ChatMessage("user", full_prompt)],
                temperature=0.7,
                stream=True,
            )
        except Exception as e:  # noqa: BLE001
            await self._release_llm()
            logger.error("LLM stream init failed (rewrite): {}", describe_llm_error(e))
            raise ChapterRewriteError(describe_llm_error(e)) from e

        # ⚠️ 推理模型的思考内容会以 ``<think>...</think>`` 混在 delta 里
        #    （见 core/llm/openai_compat.py）—— 思考单独走一路（不丢），
        #    正文走另一路：正文里混进一段英文思考比丢掉更糟。
        splitter = ThinkSplitter()
        # ⚠️ 正文排版归一化（2026-10-30）：与章节生成同一条链路 ——
        #    模型可能整章不给换行，也可能在汉字之间塞空格。
        #    排版器负责去空格 + 段落分隔 + 兜底断段。
        formatter = ProseFormatter()
        try:
            async for delta in stream_iter:
                if not delta:
                    continue
                for kind, text in splitter.feed(delta):
                    if not text:
                        continue
                    if kind == KIND_TEXT:
                        formatted = formatter.feed(text)
                        if formatted:
                            yield (KIND_TEXT, formatted)
                    else:
                        yield (kind, text)
            tail = formatter.finish()
            if tail:
                yield (KIND_TEXT, tail)
        finally:
            await self._release_llm()


__all__ = [
    "ChapterRewriter",
    "ChapterRewriteError",
]
