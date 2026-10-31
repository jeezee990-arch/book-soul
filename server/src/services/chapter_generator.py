"""章节正文生成器（Phase 4.3 流式）。

职责：
- 加载上下文（人物卡 / 大纲 / 前章摘要 / 前章尾部 / 用户 prompt）
- 流式调 LLM
- 暴露 AsyncIterator[str]（只吐正文）或 AsyncIterator[tuple[str, str]]
  （区分思考 / 正文），由 API 层包装成 ndjson 返回

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
    select_relevant_characters,
)
from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.streaming import KIND_TEXT, ThinkSplitter
from ..core.prose_format import ProseFormatter
from ..models.chapter import Chapter
from ..models.character import Character
from ..models.novel import Novel
from ..models.outline import Outline

# 大纲模式 → prompt 里显示的中文标签
#
# 半开放式（semi_open）的章节**不能自己把故事写完** —— 大纲只到前期，
# 后续由作者创作或 AI 续写。把模式原样（英文枚举）塞进 prompt，
# 模型多半看不懂，所以这里翻成人话。
_OUTLINE_MODE_LABELS: dict[str, str] = {
    "complete": "完整大纲（从开头写到全书结束，本章按大纲推进即可）",
    "semi_open": "半开放式（大纲只到前期并留了悬念，本章要延续悬念，不要写出结局）",
    "freedom": "创作型（自由文字 + 关键节拍，按节拍推进）",
}


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
            select(Outline).where(Outline.novel_id == novel_id).order_by(Outline.id.asc()).limit(1)
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
        """流式生成章节正文（**只吐正文**）。

        兼容入口：给只需要正文的调用方用。要拿到思考内容请用
        :meth:`stream_generate_parts`。

        失败：抛 :class:`ChapterGenerationError`（在 yield 之前 / 之后均可能）。
        """
        async for kind, text in self.stream_generate_parts(
            chapter_id=chapter_id,
            user_prompt=user_prompt,
            target_word_count=target_word_count,
        ):
            if kind == KIND_TEXT:
                yield text

    async def stream_generate_parts(
        self,
        *,
        chapter_id: int,
        user_prompt: str = "",
        target_word_count: int = 4000,
    ) -> AsyncIterator[tuple[str, str]]:
        """流式生成章节正文，区分「思考」与「正文」。

        产出 ``(KIND_THINK, text)`` / ``(KIND_TEXT, text)``。

        ⚠️ 为什么要分开（AGENTS.md §4.7 铁律：思考内容不能被丢弃）：
        推理模型（MiniMax M3 等）先吐好几秒的 ``<think>`` 再开始写正文。
        以前这里 ``if kind == KIND_THINK: continue`` 把思考整段丢了 →
        思考期前端一个字都收不到 → 用户看到"生成卡住不动"。
        现在思考单独走一路，由 API 层转成 ``thinking`` 事件给前端显示。
        """
        chapter = await self._load_chapter(chapter_id)
        novel = await self._load_novel(chapter.novel_id)
        all_characters = await self._load_active_characters(chapter.novel_id)
        outline = await self._load_outline(chapter.novel_id)
        chapter_outline = await get_chapter_outline(self.session, chapter, outline)
        recent_summaries = await get_recent_summaries(self.session, chapter.novel_id, n=3)
        previous_tail = await get_previous_tail(
            self.session, chapter.novel_id, chapter.chapter_number - 1, chars=1500
        )

        # 只把"本章相关"的人物卡塞进 prompt（缩短 prompt → 首字更快、token 更省）
        context_text = "\n".join([chapter_outline, previous_tail, user_prompt])
        characters = select_relevant_characters(all_characters, context_text)
        if len(characters) != len(all_characters):
            logger.debug(
                "chapter {}: character cards filtered {}/{} -> {}",
                chapter_id,
                len(all_characters),
                len(all_characters),
                len(characters),
            )

        prompt_tpl = load_chapter_generation_prompt()
        mode_key = novel.outline_mode or "complete"
        try:
            full_prompt = prompt_tpl.format(
                novel_name=novel.name,
                genre=novel.genre,
                outline_mode=_OUTLINE_MODE_LABELS.get(mode_key, mode_key),
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
        #
        # ⚠️ 推理模型（MiniMax M3 等）的思考内容会被上游包成
        #    ``<think>...</think>`` 混在 delta 里（见 core/llm/openai_compat.py）。
        #    这里用 ThinkSplitter 拆成两路：**思考单独走一路**（不丢），
        #    正文走另一路 —— 正文里混进 "We need answer Chinese..." 是灾难。
        splitter = ThinkSplitter()
        # ⚠️ 正文排版归一化（2026-10-30，用户实测反馈）：
        #    模型可能整章不给一个换行（实测 MiniMax-M3.1-Flash 的输出里
        #    **零个换行**），也可能在汉字之间塞空格。
        #    排版器负责：去汉字间空格 + 段落分隔 + 兜底断段（模型不输出段落时）。
        #    增量处理，所以流式界面里看到的就是规范排版的正文。
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
    "ChapterGenerator",
    "ChapterGenerationError",
]
