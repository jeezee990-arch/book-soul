"""章节生成的 prompt 加载 + 上下文格式化工具（Phase 4.3 抽模块）。

提供：
- :func:`load_chapter_generation_prompt`：lru_cache 读 ``chapter_generation.yaml``
- :func:`format_characters`：人物卡 → 文本块
- :func:`format_outline`：Outline.structure → 文本块
- :func:`get_chapter_outline`：从 outline 里抠本章要点
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter import Chapter, ChapterVersion
from ..models.character import Character
from ..models.outline import Outline
from .paths import prompts_dir

_PROMPTS_DIR = prompts_dir()


class ChapterContextError(Exception):
    """加载 prompt / 上下文时出错。"""


@lru_cache(maxsize=8)
def load_chapter_generation_prompt() -> str:
    """加载 ``config/prompts/chapter_generation.yaml`` 的 ``chapter_generation`` 字段。"""
    path = _PROMPTS_DIR / "chapter_generation.yaml"
    if not path.is_file():
        raise ChapterContextError(f"Chapter prompt not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "chapter_generation" not in data:
        raise ChapterContextError(f"Chapter prompt {path} missing 'chapter_generation' field")
    return str(data["chapter_generation"])


@lru_cache(maxsize=8)
def load_chapter_rewrite_prompt() -> str:
    """加载 ``config/prompts/chapter_rewrite.yaml`` 的 ``chapter_rewrite`` 字段。"""
    path = _PROMPTS_DIR / "chapter_rewrite.yaml"
    if not path.is_file():
        raise ChapterContextError(f"Chapter rewrite prompt not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "chapter_rewrite" not in data:
        raise ChapterContextError(f"Chapter rewrite prompt {path} missing 'chapter_rewrite' field")
    return str(data["chapter_rewrite"])


def format_characters(characters: list[Character]) -> str:
    """人物卡列表 → prompt 块。"""
    if not characters:
        return "（暂无人物卡）"
    parts: list[str] = []
    for c in characters:
        info_lines: list[str] = []
        for label, field in (
            ("身份", c.basic_info),
            ("性格", c.personality),
            ("习惯", c.habits),
            ("思维", c.thinking),
            ("关系", c.relationships),
            ("成长", c.growth_arc),
        ):
            if field:
                info_lines.append(f"  - {label}：{field}")
        body = "\n".join(info_lines) if info_lines else "  - （无详细字段）"
        parts.append(f"### {c.name}（{c.role}）\n{body}")
    return "\n\n".join(parts)


# 一定要带进 prompt 的角色（不管是否在本章上下文里出现）
ALWAYS_INCLUDE_ROLES = frozenset({"主角", "主角团"})


def select_relevant_characters(characters: list[Character], context_text: str) -> list[Character]:
    """挑出与本章相关的角色卡。

    为什么需要
    ----------
    章节生成 prompt 里塞**全部**活跃人物卡会带来三个问题：
    1. prompt 变长 → 首字延迟变高（用户体感"模型很慢"）
    2. token 变贵
    3. 角色一多，AI 容易混淆谁是谁

    规则
    ----
    - 名字出现在 ``context_text``（本章大纲要点 + 上一章尾部 + 用户 prompt）→ 保留
    - ``role`` 属于 :data:`ALWAYS_INCLUDE_ROLES`（主角 / 主角团）→ 永远保留
    - 一个都没匹配上 → **退回全部**（宁可多给，不可少给，避免角色凭空消失）
    """
    if not characters:
        return []
    if not context_text.strip():
        return list(characters)

    selected: list[Character] = []
    seen: set[str] = set()

    def _add(c: Character) -> None:
        key = c.name or f"__id_{id(c)}"
        if key not in seen:
            seen.add(key)
            selected.append(c)

    for c in characters:
        if c.role in ALWAYS_INCLUDE_ROLES:
            _add(c)
    for c in characters:
        if c.name and c.name in context_text:
            _add(c)

    return selected or list(characters)


def format_outline(outline: Outline | None) -> str:
    """Outline.structure → 可读文本。"""
    if outline is None or not outline.structure:
        return "（暂无大纲）"
    try:
        return json.dumps(outline.structure, ensure_ascii=False, indent=2)[:8000]
    except (TypeError, ValueError):
        return str(outline.structure)[:8000]


async def get_chapter_outline(
    session: AsyncSession, chapter: Chapter, outline: Outline | None
) -> str:
    """从 outline.structure 里抠本章要点；找不到则用 chapter.outline 字段。"""
    if outline is None or not outline.structure:
        return chapter.outline or "（无大纲）"
    structure: dict[str, Any] = outline.structure
    for key in ("chapters", "chapter_list", "outlines", "scenes"):
        ch_list = structure.get(key)
        if isinstance(ch_list, list):
            for item in ch_list:
                if not isinstance(item, dict):
                    continue
                num = item.get("number") or item.get("chapter_number") or item.get("index")
                if str(num) == str(chapter.chapter_number):
                    return (
                        item.get("summary")
                        or item.get("content")
                        or item.get("outline")
                        or json.dumps(item, ensure_ascii=False, indent=2)
                    )
    return (chapter.outline or "") + "\n\n" + format_outline(outline)


async def get_version_tail(session: AsyncSession, chapter: Chapter, chars: int) -> str:
    """从 chapter.current_version_id 取 ChapterVersion.content 末尾 chars 字。"""
    if chapter.current_version_id is None:
        return ""
    version = await session.get(ChapterVersion, chapter.current_version_id)
    if version is None or not version.content:
        return ""
    return version.content[-chars:] if len(version.content) > chars else version.content


async def get_recent_summaries(session: AsyncSession, novel_id: int, n: int = 3) -> str:
    """取最近 n 个已有内容的 chapter 的首段作为摘要（最简实现）。"""
    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id, Chapter.word_count > 0)
        .order_by(Chapter.chapter_number.desc(), Chapter.id.desc())
        .limit(n)
    )
    result = await session.execute(stmt)
    chapters = list(result.scalars())[::-1]
    if not chapters:
        return "（暂无历史章节）"
    parts: list[str] = []
    for ch in chapters:
        tail = await get_version_tail(session, ch, chars=300)
        if tail:
            parts.append(f"第 {ch.chapter_number} 章《{ch.title or '未命名'}》：{tail}")
    return "\n\n".join(parts) or "（暂无历史章节）"


async def get_previous_tail(
    session: AsyncSession, novel_id: int, before_chapter_number: int, chars: int = 1500
) -> str:
    """取上一章最后 chars 字。"""
    if before_chapter_number < 1:
        return "（无上一章）"
    stmt = (
        select(Chapter)
        .where(
            Chapter.novel_id == novel_id,
            Chapter.chapter_number == before_chapter_number,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    prev = result.scalar_one_or_none()
    if prev is None or prev.current_version_id is None:
        return "（上一章暂无内容）"
    return await get_version_tail(session, prev, chars=chars)


__all__ = [
    "ALWAYS_INCLUDE_ROLES",
    "ChapterContextError",
    "load_chapter_generation_prompt",
    "load_chapter_rewrite_prompt",
    "format_characters",
    "format_outline",
    "get_chapter_outline",
    "get_version_tail",
    "get_recent_summaries",
    "get_previous_tail",
    "select_relevant_characters",
]
