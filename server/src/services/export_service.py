"""导出服务（Phase 3.8 + 4.7）：把 novel + outline + characters 拼成 markdown / HTML 文本。

不做的事：
- 不直接写文件（让调用方决定写哪：HTTP response / 本地文件 / 落库）
- 不调用 LLM（纯模板拼装）
- Word（docx）导出见 :mod:`src.services.export_docx`（需要 python-docx，未装时 501）
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.character import Character
from ..models.novel import Novel
from .character_service import CharacterService, NovelNotFoundError
from .outline_service import OutlineService


class ExportError(Exception):
    """导出失败。"""


class NovelExportService:
    """导出 novel 完整快照为 markdown。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def export_markdown(self, novel_id: int) -> str:
        """导出指定 novel 为 markdown 文本。"""
        # 1) 校验 novel 存在（用 CharacterService 复用 _ensure_novel_exists）
        await CharacterService(self.session)._ensure_novel_exists(novel_id)  # noqa: SLF001

        # 2) 加载 novel
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise NovelNotFoundError(novel_id)

        # 3) 加载 outline（最新一条，按 outline_type 优先 complete）
        outline_section = await self._build_outline_section(novel_id)

        # 4) 加载 characters（按角色排序）
        characters_section = await self._build_characters_section(novel_id)

        # 5) 拼装 markdown
        return self._render_markdown(novel, outline_section, characters_section)

    async def export_html(self, novel_id: int) -> str:
        """导出指定 novel 为 HTML 文本（Phase 4.7，0 依赖）。"""
        # 复用 markdown 拼装
        md = await self.export_markdown(novel_id)
        return self._markdown_to_html(md)

    # ===== 内部 =====

    async def _build_outline_section(self, novel_id: int) -> str:
        """查最新 outline，渲染为 markdown section。"""
        outline_svc = OutlineService(self.session)
        try:
            outlines = await outline_svc.list_all(novel_id=novel_id, limit=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("load outline failed: {}", e)
            return "（无）"

        if not outlines:
            return "（无）"

        # 选最新一条（list_all 已按 created_at desc）
        o = outlines[0]
        structure = o.structure or {}
        if o.outline_type == "complete":
            return self._render_complete(structure)
        if o.outline_type == "freedom":
            return self._render_freedom(structure)
        return "（未知大纲类型）"

    async def _build_characters_section(self, novel_id: int) -> str:
        """列出所有人物卡，渲染为 markdown section。"""
        stmt = (
            select(Character)
            .where(Character.novel_id == novel_id)
            .order_by(Character.role.asc(), Character.id.asc())
        )
        result = await self.session.execute(stmt)
        chars = list(result.scalars())
        if not chars:
            return "（无）"

        blocks: list[str] = []
        for c in chars:
            blocks.append(self._render_character(c))
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _render_markdown(novel: Novel, outline_md: str, chars_md: str) -> str:
        """主模板：作品名 + 元信息 + 大纲 + 人物卡。"""
        created = novel.created_at.strftime("%Y-%m-%d") if novel.created_at else ""
        description = novel.description or "（无）"
        status_zh = {
            "draft": "草稿",
            "writing": "创作中",
            "paused": "暂停",
            "completed": "已完结",
            "abandoned": "弃坑",
        }.get(novel.status, novel.status)
        parts: list[str] = [
            f"# {novel.name}",
            "",
            f"> 题材：{novel.genre}  ",
            f"> 状态：{status_zh}  ",
            f"> 创建：{created}  ",
            f"> 简介：{description}",
            "",
            "## 大纲",
            "",
            outline_md,
            "",
            "## 人物卡",
            "",
            chars_md,
            "",
        ]
        return "\n".join(parts)

    @staticmethod
    def _render_complete(structure: dict[str, Any]) -> str:
        volumes = structure.get("volumes") or []
        if not volumes:
            return "（无分卷）"
        lines: list[str] = []
        for i, v in enumerate(volumes, 1):
            name = v.get("name") or f"第 {i} 卷"
            summary = v.get("summary") or ""
            lines.append(f"### 第 {i} 卷 · {name}")
            if summary:
                lines.append(summary)
            chapters = v.get("chapters") or []
            if chapters:
                lines.append("")
                lines.append("**章：**")
                for j, ch in enumerate(chapters, 1):
                    title = ch.get("title") or f"第 {j} 章"
                    ch_summary = ch.get("summary") or ""
                    events = ch.get("key_events") or []
                    line = f"{j}. **{title}**"
                    if ch_summary:
                        line += f" — {ch_summary}"
                    lines.append(line)
                    if events:
                        lines.append(f"   - 关键事件：{'、'.join(str(e) for e in events)}")
            lines.append("")
        if structure.get("overall_theme"):
            lines.insert(0, f"**全篇主题**：{structure['overall_theme']}")
            lines.insert(1, "")
        return "\n".join(lines).rstrip()

    @staticmethod
    def _render_freedom(structure: dict[str, Any]) -> str:
        parts: list[str] = []
        themes = structure.get("themes") or []
        if themes:
            parts.append("**主题**：" + "、".join(str(t) for t in themes))
            parts.append("")
        summary = structure.get("summary") or ""
        if summary:
            parts.append("**梗概**")
            parts.append("")
            parts.append(summary)
            parts.append("")
        beats = structure.get("key_beats") or []
        if beats:
            parts.append("**关键节拍**")
            parts.append("")
            for i, b in enumerate(beats, 1):
                parts.append(f"{i}. {b}")
            parts.append("")
        return "\n".join(parts).rstrip() or "（空）"

    @staticmethod
    def _render_character(c: Character) -> str:
        status = "（退场）" if not c.is_active else ""
        lines: list[str] = [
            f"### {c.name}（{c.role}）{status}",
            "",
        ]
        fields = [
            ("基本信息", c.basic_info),
            ("性格", c.personality),
            ("习惯", c.habits),
            ("思维方式", c.thinking),
            ("人物关系", c.relationships),
            ("成长弧线", c.growth_arc),
        ]
        for label, value in fields:
            if value:
                lines.append(f"**{label}**：{value}")
                lines.append("")
        return "\n".join(lines).rstrip()

    # ===== Phase 4.7: 简易 markdown → HTML（0 依赖）=====

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @classmethod
    def _markdown_to_html(cls, md: str) -> str:
        """把 export_markdown 的输出转成 HTML（仅支持导出模板里用到的语法）。

        支持：# / ## / ### / **粗体** / 普通段落 / > 引用 / --- 分隔 / - 列表 / ``n. 列表``。
        不支持：链接、图片、代码块、表格（导出模板本身也不用）。
        """
        import re

        lines = md.split("\n")
        out: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>导出</title>",
            "<style>",
            "  body{font-family:system-ui,-apple-system,sans-serif;max-width:780px;margin:2rem auto;padding:0 1.5rem;line-height:1.7;color:#1f2937;}",
            "  h1{margin:0 0 .5em;border-bottom:2px solid #1f2937;padding-bottom:.3em;}",
            "  h2{margin:1.5em 0 .5em;border-bottom:1px solid #d1d5db;padding-bottom:.2em;}",
            "  h3{margin:1.2em 0 .4em;color:#374151;}",
            "  blockquote{margin:.8em 0;padding:.5em 1em;border-left:3px solid #d1d5db;color:#6b7280;background:#f9fafb;}",
            "  hr{border:0;border-top:1px solid #e5e7eb;margin:1.5em 0;}",
            "  ul,ol{margin:.5em 0 .8em 1.5em;}",
            "  li{margin:.2em 0;}",
            "  strong{color:#111827;}",
            "</style>",
            "</head>",
            "<body>",
        ]

        in_list: str | None = None  # "ul" | "ol" | None
        in_quote = False

        def close_list() -> None:
            nonlocal in_list
            if in_list:
                out.append(f"</{in_list}>")
                in_list = None

        def close_quote() -> None:
            nonlocal in_quote
            if in_quote:
                out.append("</blockquote>")
                in_quote = False

        for raw in lines:
            line = raw.rstrip()
            if not line:
                close_list()
                close_quote()
                continue

            # 分隔线
            if line.strip() == "---":
                close_list()
                close_quote()
                out.append("<hr>")
                continue

            # 引用
            if line.startswith(">"):
                close_list()
                if not in_quote:
                    out.append("<blockquote>")
                    in_quote = True
                content = line[1:].strip()
                out.append(f"<p>{cls._inline_format(content)}</p>")
                continue
            else:
                close_quote()

            # 标题
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                close_list()
                level = len(m.group(1))
                content = cls._inline_format(m.group(2))
                out.append(f"<h{level}>{content}</h{level}>")
                continue

            # 有序列表
            m_ol = re.match(r"^(\d+)\.\s+(.*)$", line)
            if m_ol:
                if in_list != "ol":
                    close_list()
                    out.append("<ol>")
                    in_list = "ol"
                out.append(f"<li>{cls._inline_format(m_ol.group(2))}</li>")
                continue

            # 无序列表（缩进的 - 开头）
            m_ul = re.match(r"^\s*-\s+(.*)$", line)
            if m_ul:
                if in_list != "ul":
                    close_list()
                    out.append("<ul>")
                    in_list = "ul"
                out.append(f"<li>{cls._inline_format(m_ul.group(1))}</li>")
                continue

            # 普通段落
            close_list()
            out.append(f"<p>{cls._inline_format(line)}</p>")

        close_list()
        close_quote()
        out.append("</body></html>")
        return "\n".join(out)

    @classmethod
    def _inline_format(cls, text: str) -> str:
        """行内格式：仅处理 **粗体** 和 HTML 转义。"""
        text = cls._escape_html(text)
        # **xxx** → <strong>xxx</strong>（非贪婪）
        import re

        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


__all__ = ["NovelExportService", "ExportError"]
