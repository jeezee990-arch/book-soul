"""小说目录导入（Phase 6.3）。

把 :class:`DetectedNovel` 导入为 DB 里的 ``novel`` + ``chapter`` + ``chapter_version``。
- novel.read_only = True（标记为导入，不允许直接编辑）
- 每章建一个 ``ChapterVersion``，trigger = "imported"
- 文件路径存到 chapter.outline 里（让前端知道文件在哪）
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.chapter import Chapter, ChapterVersion
from ...models.novel import Novel
from .novel_detector import DetectedNovel


class NovelImportError(Exception):
    """导入失败。"""


async def import_detected_novel(
    session: AsyncSession,
    detected: DetectedNovel,
    *,
    genre: str = "xiuxian",
) -> Novel:
    """把一个 DetectedNovel 导入 DB；返回新建的 Novel。"""
    if detected.chapter_count == 0:
        raise NovelImportError(f"No chapters to import: {detected.dir_path}")

    # 1) 创建 novel
    novel = Novel(
        name=detected.title,
        genre=genre,
        description=f"从本地目录导入：{detected.dir_path}",
        read_only=True,
        imported=True,
        outline_mode=None,  # 导入无大纲
    )
    session.add(novel)
    await session.flush()

    # 2) 逐章导入
    from pathlib import Path

    for idx, ch in enumerate(detected.chapters, start=1):
        # 读全文
        try:
            content = Path(ch.path).read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logger.warning("Skip chapter (read failed): {} ({})", ch.path, e)
            continue

        chapter = Chapter(
            novel_id=novel.id,
            chapter_number=idx,
            title=ch.title,
            outline=None,
            status="imported",  # 用 imported 标记
            word_count=len(content),
        )
        session.add(chapter)
        await session.flush()

        ver = ChapterVersion(
            chapter_id=chapter.id,
            parent_version_id=None,
            content=content,
            diff=None,
            trigger="imported",
            prompt=None,
            metadata_={"source_path": ch.path, "source_filename": Path(ch.path).name},
            word_count=len(content),
        )
        session.add(ver)
        await session.flush()
        chapter.current_version_id = ver.id

    await session.commit()
    await session.refresh(novel)
    logger.info(
        "Imported novel id={} from {} ({} chapters)",
        novel.id,
        detected.dir_path,
        detected.chapter_count,
    )
    return novel


__all__ = ["NovelImportError", "import_detected_novel"]
