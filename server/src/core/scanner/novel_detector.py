"""小说目录检测（Phase 6.3）。

判定规则（参考 PROJECT_PLAN.md §6.3）：
- 目录下 ``.md`` 文件数 >= 3
- 至少 1 个 md 文件内容含章节标记（第 X 章 / Chapter X 等）

设计要点：
- 纯同步函数，扫描是 IO 密集但不需要 asyncio（FastAPI sync def 即可）
- 异常鲁棒：单文件读失败不阻塞整体
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 章节模式：中文"第X章" / 英文 "Chapter X" / 数字"01"等
CHAPTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"第[一二三四五六七八九十百千万\d]+章\s*[^\n]*"),
    re.compile(r"Chapter\s*\d+", re.IGNORECASE),
    re.compile(r"^\s*#+\s*第[一二三四五六七八九十百千万\d]+章", re.MULTILINE),
    re.compile(r"^\s*#+\s*Chapter\s*\d+", re.IGNORECASE | re.MULTILINE),
)


@dataclass
class DetectedChapter:
    """检测到的单章信息。"""

    title: str
    path: str
    word_count: int
    preview: str = ""  # 前 100 字（用于详情页预览）


@dataclass
class DetectedNovel:
    """检测到的小说目录。"""

    dir_path: str
    title: str
    chapter_count: int
    total_words: int
    chapters: list[DetectedChapter] = field(default_factory=list)


def is_novel_dir(path: str) -> bool:
    """快速判断一个目录是否像小说。"""
    p = Path(path)
    if not p.is_dir():
        return False
    md_files = list(p.glob("*.md"))
    if len(md_files) < 3:
        return False
    # 看前 5 个文件的内容是否含章节标记
    for f in md_files[:5]:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")[:500]
        except OSError:
            continue
        if any(p.search(content) for p in CHAPTER_PATTERNS):
            return True
    return False


def extract_metadata(path: str) -> DetectedNovel:
    """深度解析一个小说目录，返回章节列表 + 总字数 + 标题。"""
    p = Path(path)
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")

    md_files = sorted(p.glob("*.md"))
    chapters: list[DetectedChapter] = []
    total_words = 0

    for f in md_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        wc = len(content)
        total_words += wc

        title = f.stem  # fallback
        for pattern in CHAPTER_PATTERNS:
            m = pattern.search(content[:300])
            if m:
                title = m.group(0).strip()
                break

        chapters.append(
            DetectedChapter(
                title=title,
                path=str(f.absolute()),
                word_count=wc,
                preview=content[:200].replace("\n", " ").strip(),
            )
        )

    return DetectedNovel(
        dir_path=str(p.absolute()),
        title=p.name,
        chapter_count=len(md_files),
        total_words=total_words,
        chapters=chapters,
    )


__all__ = [
    "CHAPTER_PATTERNS",
    "DetectedChapter",
    "DetectedNovel",
    "is_novel_dir",
    "extract_metadata",
]
