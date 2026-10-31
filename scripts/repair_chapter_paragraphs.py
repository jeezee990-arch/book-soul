"""修复被"假段落"破坏的历史章节正文（2026-10-30）。

问题
----
旧版前端（``NovelEditor.flushAppend``）在**文档末尾** ``insertText``，ProseMirror 会
**新建一个段落**；而流式追加是每 16ms 一次 flush。于是每个批次变成一个段落，
Tiptap 的 ``getText()`` 又用 ``"\\n\\n"`` 拼块 → 正文被切成成百上千个 1-7 字的"段落"。

用户实测数据（``《骨仙传》第 1 章``）：``len=5338``、其中 **2024 个字符是换行**，
真实正文只有 3314 字，界面却显示 5338 字。

修法
----
把假段落边界去掉 → 拼回连续正文 → 用 :class:`ProseFormatter` 重新规范分段。

⚠️ **原始段落信息已经丢失**（假边界和真边界无法区分），所以只能按标点重新断句。
   修复后正文可读性恢复，但段落切分不一定和作者当初的意图完全一致。

用法
----
```powershell
# 修复打包版的数据目录
& .\\.venv\\Scripts\\python.exe scripts\\repair_chapter_paragraphs.py `
    --data-dir "C:\\Users\\JZ\\Desktop\\Book Soul\\dist\\Book Soul\\data"

# 只看会修什么，不写库
& .\\.venv\\Scripts\\python.exe scripts\\repair_chapter_paragraphs.py --dry-run

# 二次修整：段落划分不动，只把挤在一起的连续对白拆成独立段落
& .\\.venv\\Scripts\\python.exe scripts\\repair_chapter_paragraphs.py --split-dialogue
```

⚠️ 修复会**新建一个版本**（原版本保留在版本历史里），并把章节指向新版本。
"""

from __future__ import annotations

import argparse
import asyncio
import re
import statistics
import sys
from pathlib import Path

# 让脚本能 import 到 server/src
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="修复被假段落破坏的章节正文")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="数据目录（默认读环境变量 BOOK_SOUL_DATA_DIR）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只报告要修什么，不写库",
    )
    parser.add_argument(
        "--min-segments",
        type=int,
        default=20,
        help="段落数超过这个值才判定为损坏（默认 20）",
    )
    parser.add_argument(
        "--max-median-len",
        type=int,
        default=20,
        help="段落中位长度小于这个值才判定为损坏（默认 20）",
    )
    parser.add_argument(
        "--split-dialogue",
        action="store_true",
        help=(
            "二次修整模式：**保留**现有段落划分，只把挤在一起的连续对白"
            "（“甲？”“乙。”）拆成独立段落。对已经修好、但对白还挤在一段的章节用。"
        ),
    )
    parser.add_argument(
        "--chapter-id",
        type=int,
        default=None,
        help="只处理指定章节（默认全部）",
    )
    return parser.parse_args()


def looks_broken(content: str, *, min_segments: int, max_median_len: int) -> bool:
    """判断一段正文是否被"假段落"破坏。

    特征：段落数异常多，且每段都很短（正常小说段落 30-80 字）。

    :param content: 正文
    :param min_segments: 段落数下限
    :param max_median_len: 段落中位长度上限
    :return: True 表示损坏
    """
    if not content:
        return False
    segments = [s for s in content.split("\n\n") if s.strip()]
    if len(segments) < min_segments:
        return False
    lengths = [len(s.strip()) for s in segments]
    median = statistics.median(lengths)
    return median < max_median_len


def repair_content(content: str) -> str:
    """把损坏的正文还原成规范段落。

    :param content: 损坏的正文
    :return: 修复后的正文
    """
    from src.core.prose_format import ProseFormatter

    # 1) 去掉所有换行 → 连续正文
    restored = re.sub(r"\n+", "", content)
    # 2) 重新规范分段
    formatter = ProseFormatter()
    return formatter.feed(restored) + formatter.finish()


async def run(args: argparse.Namespace) -> int:
    """主流程。

    :param args: 命令行参数
    :return: 退出码
    """
    if args.data_dir:
        import os

        os.environ["BOOK_SOUL_DATA_DIR"] = str(Path(args.data_dir).resolve())

    from sqlalchemy import select

    from src.core.prose_format import count_prose_words
    from src.db import SessionLocal, init_db
    from src.models.chapter import Chapter, ChapterVersion

    await init_db()

    fixed = 0
    found = 0
    async with SessionLocal() as session:
        if args.split_dialogue:
            return await _run_split_dialogue(session, args)

        rows = (
            await session.execute(
                select(ChapterVersion).order_by(ChapterVersion.id.asc())
            )
        ).scalars().all()

        for version in rows:
            if args.chapter_id and version.chapter_id != args.chapter_id:
                continue
            if not looks_broken(
                version.content,
                min_segments=args.min_segments,
                max_median_len=args.max_median_len,
            ):
                continue

            old_len = len(version.content)
            old_words = count_prose_words(version.content)
            new_content = repair_content(version.content)
            new_words = count_prose_words(new_content)
            chapter = await session.get(Chapter, version.chapter_id)

            print(
                f"[修复] version={version.id} chapter={version.chapter_id} "
                f"《{chapter.title if chapter else '?'}》"
            )
            print(
                f"       字符 {old_len} → {len(new_content)}"
                f"   字数 {old_words} → {new_words}"
                f"   段落 {version.content.count(chr(10) * 2) + 1}"
                f" → {new_content.count(chr(10) * 2) + 1}"
            )

            if args.dry_run:
                print("       （dry-run，未写库）")
                found += 1
                continue

            # 新建一个版本（保留原版本在历史里）
            new_version = ChapterVersion(
                chapter_id=version.chapter_id,
                parent_version_id=version.id,
                content=new_content,
                trigger="user_edit",
                prompt=None,
                metadata_={"repaired": "fake-paragraphs", "source_version_id": version.id},
                word_count=new_words,
            )
            session.add(new_version)
            await session.flush()

            if chapter is not None:
                chapter.current_version_id = new_version.id
                chapter.word_count = new_words
                session.add(chapter)

            fixed += 1

        await session.commit()

    if args.dry_run:
        print(f"\n共发现 {found} 处损坏（dry-run，未修改数据库）")
    else:
        print(f"\n共修复 {fixed} 处（原版本保留在版本历史里）")
    return 0


async def _run_split_dialogue(session, args: argparse.Namespace) -> int:
    """二次修整：保留段落划分，只把连续对白拆成独立段落。

    只处理**章节的当前版本**（历史版本不再动），避免重复处理。

    :param session: 数据库会话
    :param args: 命令行参数
    :return: 退出码
    """
    from sqlalchemy import select

    from src.core.prose_format import count_prose_words, split_consecutive_dialogue
    from src.models.chapter import Chapter, ChapterVersion

    stmt = select(Chapter).order_by(Chapter.id.asc())
    if args.chapter_id:
        stmt = stmt.where(Chapter.id == args.chapter_id)
    chapters = list((await session.execute(stmt)).scalars().all())

    changed = 0
    for chapter in chapters:
        if not chapter.current_version_id:
            continue
        version = await session.get(ChapterVersion, chapter.current_version_id)
        if version is None or not version.content.strip():
            continue

        new_content = split_consecutive_dialogue(version.content)
        if new_content == version.content:
            continue

        old_words = count_prose_words(version.content)
        new_words = count_prose_words(new_content)
        old_paras = len([p for p in version.content.split("\n\n") if p.strip()])
        new_paras = len([p for p in new_content.split("\n\n") if p.strip()])

        print(f"[拆对白] chapter={chapter.id} 《{chapter.title}》 version={version.id}")
        print(
            f"          字数 {old_words} → {new_words}"
            f"   段落 {old_paras} → {new_paras}"
        )

        if args.dry_run:
            print("          （dry-run，未写库）")
            changed += 1
            continue

        new_version = ChapterVersion(
            chapter_id=chapter.id,
            parent_version_id=version.id,
            content=new_content,
            trigger="user_edit",
            prompt=None,
            metadata_={"repaired": "split-dialogue", "source_version_id": version.id},
            word_count=new_words,
        )
        session.add(new_version)
        await session.flush()

        chapter.current_version_id = new_version.id
        chapter.word_count = new_words
        session.add(chapter)
        changed += 1

    await session.commit()

    verb = "发现" if args.dry_run else "已拆"
    print(f"\n共{verb} {changed} 章（原版本保留在版本历史里，可回滚）")
    return 0


def main() -> int:
    """命令行入口。"""
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
