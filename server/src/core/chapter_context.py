"""章节生成的 prompt 加载 + 上下文格式化工具（Phase 4.3 抽模块）。

提供：
- :func:`load_chapter_generation_prompt`：lru_cache 读 ``chapter_generation.yaml``
- :func:`format_characters`：人物卡 → 文本块
- :func:`format_outline`：Outline.structure → 文本块
- :func:`get_chapter_outline`：从 outline 里抠本章要点
"""

from __future__ import annotations

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


def _chapter_one_line(chapter: Any, index: int) -> str:
    """把一个章节条目渲染成"一行"提纲（用于整体大纲文本）。"""
    if not isinstance(chapter, dict):
        text = str(chapter).strip()
        return f"  {index}. {text}" if text else ""
    title = str(chapter.get("title") or "").strip()
    summary = str(
        chapter.get("summary") or chapter.get("content") or chapter.get("outline") or ""
    ).strip()
    label = title or f"第{index}章"
    if summary:
        return f"  {index}. {label} —— {summary}"
    return f"  {index}. {label}"


def format_outline(outline: Outline | None) -> str:
    """Outline.structure → **可读的中文**大纲文本。

    ⚠️ 2026-10-29 之前这里是 ``json.dumps(structure, indent=2)[:8000]`` ——
    把整份 JSON（英文键名 + 缩进）塞进章节生成 prompt。后果有两个：

    1. prompt 里塞满英文 JSON，**模型会跟着用英文思考**（用户实测图1）；
    2. 8000 字符里绝大部分是结构噪音（缩进、键名、引号），
       真正相关的章节信息被挤到后面。

    现在改成人类可读的中文提纲：卷名、章标题、章节概要、关键节拍。
    """
    if outline is None or not outline.structure:
        return "（暂无大纲）"
    structure: dict[str, Any] = outline.structure
    lines: list[str] = []

    for key, label in (
        ("overall_theme", "全书主题"),
        ("theme", "全书主题"),
        ("summary", "全书概要"),
        ("suspense_hook", "悬念钩子"),
    ):
        value = structure.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"{label}：{value.strip()}")

    # 卷 → 章（两阶段大纲的主结构）
    #
    # ⚠️ 2026-10-29 评审：章号必须**全局累加**。
    #    以前每卷都从 1 重排 —— "第二卷"下面又出现"第 1 章"，
    #    而本章其实是全书第 6 章 → 模型会写错章节编号。
    #    （与 get_chapter_outline 的位置推断口径保持一致。）
    volumes = structure.get("volumes")
    global_index = 0
    if isinstance(volumes, list):
        for v_index, volume in enumerate(volumes):
            if not isinstance(volume, dict):
                continue
            name = str(volume.get("name") or f"第{v_index + 1}卷").strip()
            v_summary = str(volume.get("summary") or "").strip()
            lines.append(f"\n{name}" + (f" —— {v_summary}" if v_summary else ""))
            chapters = volume.get("chapters")
            if isinstance(chapters, list):
                for chapter in chapters:
                    global_index += 1
                    text = _chapter_one_line(chapter, global_index)
                    if text:
                        lines.append(text)

    # 扁平结构（单阶段大纲 / 手工结构）
    for key in ("chapters", "chapter_list", "outlines", "scenes"):
        ch_list = structure.get(key)
        if not isinstance(ch_list, list) or not ch_list:
            continue
        lines.append("")
        for chapter in ch_list:
            global_index += 1
            text = _chapter_one_line(chapter, global_index)
            if text:
                lines.append(text)

    beats = structure.get("key_beats")
    if isinstance(beats, list):
        cleaned = [str(b).strip() for b in beats if str(b).strip()]
        if cleaned:
            lines.append("\n关键节拍：" + "；".join(cleaned))

    themes = structure.get("themes")
    if isinstance(themes, list):
        cleaned = [str(t).strip() for t in themes if str(t).strip()]
        if cleaned:
            lines.append("主题：" + "、".join(cleaned))

    if not lines:
        return str(structure)[:4000]
    return "\n".join(lines)[:6000]


def _explicit_chapter_number(item: dict[str, Any]) -> int | None:
    """从章节条目里读显式章号；没有则返回 None（走位置推断）。"""
    for key in ("number", "chapter_number", "index", "no"):
        value = item.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _find_chapter_in_volumes(
    structure: dict[str, Any], chapter_number: int
) -> tuple[str, dict[str, Any]] | None:
    """在 ``volumes[].chapters[]`` 嵌套结构里找指定章。

    ⚠️ 这是需求7 的核心 bug（2026-10-29 用户实测）：
    两阶段大纲（2026-10-25 起）产出的结构是 ``volumes[].chapters[]`` ——
    **章在卷里面**。旧实现只找顶层 key（chapters / chapter_list / outlines /
    scenes），对两阶段结构**永远找不到** → 章节生成退化成"把整份 8KB 大纲
    JSON 塞进 prompt" → 正文完全没按本章大纲走。

    章号有两种来源：
    - 条目里的显式章号（number / chapter_number）；
    - 按 ``volumes`` 顺序累加的**位置**（两阶段大纲的章节条目只有
      title / summary / key_events，没有章号 —— 位置才是主流）。

    :return: ``(卷名, 章节条目)``；找不到返回 None
    """
    volumes = structure.get("volumes")
    if not isinstance(volumes, list):
        return None
    positional = 0
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        chapters = volume.get("chapters")
        if not isinstance(chapters, list):
            continue
        volume_name = str(volume.get("name") or "").strip()
        for item in chapters:
            if not isinstance(item, dict):
                continue
            positional += 1
            explicit = _explicit_chapter_number(item)
            if explicit is not None:
                if explicit == chapter_number:
                    return volume_name, item
            elif positional == chapter_number:
                return volume_name, item
    return None


def _format_chapter_detail(volume_name: str, item: dict[str, Any]) -> str:
    """把一章的大纲条目渲染成给 prompt 用的中文文本。"""
    lines: list[str] = []
    if volume_name:
        lines.append(f"所属卷：{volume_name}")
    title = str(item.get("title") or "").strip()
    if title:
        lines.append(f"章节标题：{title}")
    summary = str(item.get("summary") or item.get("content") or item.get("outline") or "").strip()
    if summary:
        lines.append(f"本章概要：{summary}")
    events = item.get("key_events")
    if isinstance(events, list):
        cleaned = [str(e).strip() for e in events if str(e).strip()]
        if cleaned:
            lines.append("关键事件（每一条都必须在正文中实际发生）：")
            lines.extend(f"- {e}" for e in cleaned)
    return "\n".join(lines)


async def get_chapter_outline(
    session: AsyncSession, chapter: Chapter, outline: Outline | None
) -> str:
    """从 outline.structure 里抠本章要点；找不到则用 chapter.outline 字段。

    ⚠️ 需求7（2026-10-29）：必须支持两阶段大纲的 ``volumes[].chapters[]``
    嵌套结构，否则"按本章大纲创作"根本落不了地。
    """
    if outline is None or not outline.structure:
        return chapter.outline or "（无大纲）"
    structure: dict[str, Any] = outline.structure

    # 1) 扁平结构（单阶段大纲 / 手工结构）
    for key in ("chapters", "chapter_list", "outlines", "scenes"):
        ch_list = structure.get(key)
        if isinstance(ch_list, list):
            for item in ch_list:
                if not isinstance(item, dict):
                    continue
                num = _explicit_chapter_number(item)
                if num is not None and num == chapter.chapter_number:
                    detail = _format_chapter_detail("", item)
                    if detail:
                        return detail

    # 2) 两阶段结构：章在卷里面（需求7 的主路径）
    found = _find_chapter_in_volumes(structure, chapter.chapter_number)
    if found is not None:
        volume_name, item = found
        detail = _format_chapter_detail(volume_name, item)
        if detail:
            return detail

    # 3) 兜底：章级字段 + 整体大纲（可读中文，不是 JSON）
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
