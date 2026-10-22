"""本地扫描器测试（Phase 6.3）。

覆盖：
- novel_detector.is_novel_dir / extract_metadata
- novel_scanner.scan_directory
- novel_importer.import_detected_novel
- API: /scanner/scan / /scanner/import
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ===== detector =====


def test_is_novel_dir_negative(tmp_path: Path) -> None:
    # 0 个 md
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    assert not (tmp_path / "x").exists()  # sanity

    from src.core.scanner.novel_detector import is_novel_dir

    assert not is_novel_dir(str(tmp_path))


def test_is_novel_dir_too_few_md(tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import is_novel_dir

    for i in range(2):
        (tmp_path / f"ch{i:02d}.md").write_text("随便", encoding="utf-8")
    assert not is_novel_dir(str(tmp_path))


def test_is_novel_dir_no_chapter_pattern(tmp_path: Path) -> None:
    """3 个 md 但都不含章节标记。"""
    from src.core.scanner.novel_detector import is_novel_dir

    for i in range(3):
        (tmp_path / f"file{i}.md").write_text("这是一些普通文本，无章节标记。", encoding="utf-8")
    assert not is_novel_dir(str(tmp_path))


def test_is_novel_dir_chinese_chapter(tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import is_novel_dir

    for i in range(3):
        path = tmp_path / f"ch{i:02d}.md"
        path.write_text(
            f"# 第一卷\n\n第{i + 1}章 开篇\n\n某主角开始冒险。",
            encoding="utf-8",
        )
    assert is_novel_dir(str(tmp_path))


def test_is_novel_dir_english_chapter(tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import is_novel_dir

    for i in range(3):
        (tmp_path / f"ch{i:02d}.md").write_text(
            f"# Volume 1\n\nChapter {i + 1}\n\nSome text.",
            encoding="utf-8",
        )
    assert is_novel_dir(str(tmp_path))
    assert is_novel_dir(str(tmp_path))


def test_is_novel_dir_nonexistent(tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import is_novel_dir

    assert not is_novel_dir(str(tmp_path / "nonexistent"))


def test_extract_metadata(tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import extract_metadata

    (tmp_path / "ch01.md").write_text("# 第一卷\n\n第一章 觉醒\n\n韩立出生。", encoding="utf-8")
    (tmp_path / "ch02.md").write_text("第二章 拜入\n\n...", encoding="utf-8")
    (tmp_path / "notes.md").write_text("第三章 notes", encoding="utf-8")

    meta = extract_metadata(str(tmp_path))
    assert meta.title == tmp_path.name
    assert meta.chapter_count == 3
    assert meta.total_words > 0
    # 至少第一/第二章应该识别出章节标题
    titles = [c.title for c in meta.chapters]
    assert any("第一章" in t or "觉醒" in t for t in titles)


# ===== scanner =====


def test_scan_directory_no_novels(tmp_path: Path) -> None:
    from src.core.scanner.novel_scanner import scan_directory

    # 只有 1 个 md，不算
    (tmp_path / "readme.md").write_text("hello", encoding="utf-8")
    result = scan_directory(str(tmp_path))
    assert result == []


def test_scan_directory_finds_nested(tmp_path: Path) -> None:
    from src.core.scanner.novel_scanner import scan_directory

    novel_a = tmp_path / "novel_a"
    novel_a.mkdir()
    for i in range(3):
        (novel_a / f"ch{i}.md").write_text(f"第{i + 1}章 开篇\n\n正文", encoding="utf-8")

    novel_b = tmp_path / "subdir" / "novel_b"
    novel_b.mkdir(parents=True)
    for i in range(3):
        (novel_b / f"ch{i}.md").write_text(f"第{i + 1}章\n\n正文", encoding="utf-8")

    # 中间目录
    (tmp_path / "subdir").mkdir(exist_ok=True)

    result = scan_directory(str(tmp_path), max_depth=3)
    paths = [r.dir_path for r in result]
    assert any(str(novel_a) in p for p in paths)
    assert any(str(novel_b) in p for p in paths)


def test_scan_directory_skips_hidden(tmp_path: Path) -> None:
    from src.core.scanner.novel_scanner import scan_directory

    hidden = tmp_path / ".hidden_novel"
    hidden.mkdir()
    for i in range(3):
        (hidden / f"ch{i}.md").write_text(f"第{i + 1}章\n\n正文", encoding="utf-8")
    result = scan_directory(str(tmp_path))
    assert all(".hidden" not in r.dir_path for r in result)


def test_scan_directory_max_depth(tmp_path: Path) -> None:
    from src.core.scanner.novel_scanner import scan_directory

    deep = tmp_path / "a" / "b" / "c" / "novel"
    deep.mkdir(parents=True)
    for i in range(3):
        (deep / f"ch{i}.md").write_text(f"第{i + 1}章\n\n正文", encoding="utf-8")

    # max_depth=2 找不到
    assert scan_directory(str(tmp_path), max_depth=2) == []
    # max_depth=4 找到
    found = scan_directory(str(tmp_path), max_depth=4)
    assert any("novel" in r.dir_path for r in found)


# ===== importer =====


@pytest.mark.asyncio
async def test_import_detected_novel(db_initialized: Path, tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import extract_metadata
    from src.core.scanner.novel_importer import import_detected_novel
    from src.db import SessionLocal

    for i in range(3):
        (tmp_path / f"ch{i}.md").write_text(f"第{i + 1}章\n\n正文内容 {i}", encoding="utf-8")

    detected = extract_metadata(str(tmp_path))
    async with SessionLocal() as session:
        novel = await import_detected_novel(session, detected, genre="xiuxian")

    assert novel.id is not None
    assert novel.read_only is True
    assert novel.imported is True
    assert novel.genre == "xiuxian"
    # 3 个 chapter
    from sqlalchemy import select

    from src.models.chapter import Chapter

    async with SessionLocal() as session:
        result = await session.execute(
            select(Chapter).where(Chapter.novel_id == novel.id).order_by(Chapter.chapter_number)
        )
        chapters = list(result.scalars())
    assert len(chapters) == 3
    # 第一章 current_version_id 应该非空
    assert chapters[0].current_version_id is not None
    assert chapters[0].status == "imported"


@pytest.mark.asyncio
async def test_import_no_chapters_raises(db_initialized: Path, tmp_path: Path) -> None:
    from src.core.scanner.novel_detector import DetectedNovel
    from src.core.scanner.novel_importer import NovelImportError, import_detected_novel
    from src.db import SessionLocal

    detected = DetectedNovel(
        dir_path=str(tmp_path), title="空", chapter_count=0, total_words=0, chapters=[]
    )
    async with SessionLocal() as session:
        with pytest.raises(NovelImportError, match="No chapters"):
            await import_detected_novel(session, detected)


# ===== API =====


@pytest.mark.asyncio
async def test_api_scan_no_path(tmp_path: Path) -> None:
    """scan 一个没有小说的目录：返回空列表。"""
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post("/scanner/scan", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["novels"] == []


@pytest.mark.asyncio
async def test_api_scan_finds_novel(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    for i in range(3):
        (tmp_path / f"ch{i}.md").write_text(f"第{i + 1}章\n\n正文", encoding="utf-8")
    client = TestClient(app)
    resp = client.post("/scanner/scan", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["novels"]) >= 1
    assert body["novels"][0]["chapter_count"] == 3


@pytest.mark.asyncio
async def test_api_scan_invalid_path() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post("/scanner/scan", json={"path": "/this/does/not/exist/anywhere"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_import_novel(db_initialized: Path, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    for i in range(3):
        (tmp_path / f"ch{i}.md").write_text(f"第{i + 1}章\n\n正文", encoding="utf-8")
    client = TestClient(app)
    resp = client.post("/scanner/import", json={"dir_path": str(tmp_path), "genre": "xiuxian"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapter_count"] == 3
    assert body["novel_id"] > 0
    assert body["name"] == tmp_path.name

    # 验证 DB
    from src.db import SessionLocal
    from src.models.novel import Novel as NovelModel

    async with SessionLocal() as session:
        n = await session.get(NovelModel, body["novel_id"])
        assert n is not None
        assert n.read_only is True
        assert n.imported is True


@pytest.mark.asyncio
async def test_api_import_invalid_path() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post("/scanner/import", json={"dir_path": "/nonexistent/dir/abc"})
    assert resp.status_code == 422
