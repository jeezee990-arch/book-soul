"""Word（docx）导出（Phase 4.7 完整实现）。

使用 ``python-docx`` 把 novel 章节内容拼成 docx 文件：
- 封面：作品名 + 题材 + 简介
- 章节列表：每章标题 + 段落
- 字符数：保留中文段落（python-docx 自动处理 CJK 字体）
"""

from __future__ import annotations

import io

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.prose_format import split_paragraphs
from ..models.chapter import Chapter, ChapterVersion
from ..models.novel import Novel
from .export_service import chapter_heading


class WordExportUnavailableError(Exception):
    """word 导出未启用（python-docx 未装）。"""


async def build_docx_bytes(novel_id: int, session: AsyncSession) -> bytes:
    """把 novel 及其所有章节内容导出为 docx 字节流。

    :raises WordExportUnavailableError: python-docx 未装（不应当发生，因 pyproject 依赖）
    """
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError as e:
        raise WordExportUnavailableError(
            "Word 导出未启用：请先安装 python-docx（uv add python-docx）"
        ) from e

    # 1) 加载 novel
    novel = await session.get(Novel, novel_id)
    if novel is None:
        raise WordExportUnavailableError(f"Novel {novel_id} not found")

    # 2) 加载章节（按 chapter_number 升序）
    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number.asc(), Chapter.id.asc())
    )
    result = await session.execute(stmt)
    chapters: list[Chapter] = list(result.scalars())

    # 3) 构建 doc
    doc = Document()
    # 设置默认字体（CJK 友好）
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Microsoft YaHei"
    font.size = Pt(11)

    # 封面
    title = doc.add_heading(novel.name, level=0)
    title.alignment = 1  # center
    info = doc.add_paragraph()
    info.add_run(f"题材：{novel.genre}\n").bold = True
    info.add_run(f"状态：{novel.status}\n")
    if novel.description:
        info.add_run(f"\n{novel.description}\n")
    doc.add_page_break()

    # 章节
    for ch in chapters:
        doc.add_heading(chapter_heading(ch.chapter_number, ch.title), level=1)
        if ch.outline:
            p = doc.add_paragraph()
            run = p.add_run(f"【大纲】{ch.outline}")
            run.italic = True

        # 拿当前版本内容
        content = await _get_chapter_content(session, ch)
        if not content.strip():
            doc.add_paragraph("（暂无内容）")
            continue
        # 按段落切（空行是段落分隔；单个 \n 也当分隔，兼容手写正文）
        for para_text in split_paragraphs(content):
            doc.add_paragraph(para_text)
        # 章节末尾分页（最后章节不分）
        if ch is not chapters[-1]:
            doc.add_page_break()

    # 4) 写入字节流
    buffer = io.BytesIO()
    doc.save(buffer)
    logger.info("Exported novel {} ({} chapters) to docx", novel_id, len(chapters))
    return buffer.getvalue()


async def _get_chapter_content(session: AsyncSession, chapter: Chapter) -> str:
    """取 chapter 的 current_version.content。"""
    if chapter.current_version_id is None:
        return ""
    version = await session.get(ChapterVersion, chapter.current_version_id)
    if version is None:
        return ""
    return version.content


__all__ = ["WordExportUnavailableError", "build_docx_bytes"]
