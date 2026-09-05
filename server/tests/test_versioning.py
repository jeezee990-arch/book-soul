"""Versioning 单元测试（Phase 4.6）。

覆盖：
- compute_unified_diff：无差异 / 有差异 / 空输入
- diff_stats / iter_hunks
- VersionTree.save_version 自动算 diff
- VersionTree.list_versions
- VersionTree.diff_with_parent / diff_between
- VersionTree.rollback（软回滚 → 新版本，parent=当前最新）
- API: GET diff / POST rollback
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.versioning.diff import (
    compute_unified_diff,
    diff_stats,
    iter_hunks,
)
from src.core.versioning.version_tree import (
    VersionNotFoundError,
    VersionTree,
)

# ===== diff =====


def test_diff_no_change() -> None:
    assert compute_unified_diff("hello", "hello") == ""


def test_diff_empty_inputs() -> None:
    assert compute_unified_diff(None, None) == ""
    assert compute_unified_diff("", "abc") != ""
    assert compute_unified_diff("abc", "") != ""


def test_diff_basic_change() -> None:
    diff = compute_unified_diff("a\nb\nc\n", "a\nB\nc\n", fromfile="o", tofile="n")
    assert "--- o" in diff
    assert "+++ n" in diff
    assert "-b" in diff
    assert "+B" in diff


def test_diff_stats() -> None:
    diff = compute_unified_diff("a\nb\nc\n", "a\nB\nC\nc\n")
    stats = diff_stats(diff)
    # difflib unified diff 的特性：b→B + C 是 1 个 hunk；c 在 new 端保留为上下文
    # 故实际：+B +C = 2 added，-b = 1 removed
    assert stats["added"] == 2
    assert stats["removed"] == 1


def test_diff_stats_clean_change() -> None:
    """清晰的全行替换：旧 3 行 → 新 3 行（无上下文重叠）。"""
    diff = compute_unified_diff("第一行\n第二行\n第三行\n", "第1行\n第2行\n第3行\n")
    stats = diff_stats(diff)
    assert stats["added"] == 3
    assert stats["removed"] == 3


def test_diff_stats_empty() -> None:
    assert diff_stats("") == {"added": 0, "removed": 0}


def test_iter_hunks() -> None:
    text = "a\nb\nc\n"
    diff = compute_unified_diff(text, "a\nB\nc\n")
    hunks = list(iter_hunks(diff))
    assert len(hunks) >= 1
    header, lines = hunks[0]
    assert header.startswith("@@")
    # 行列表里至少有一行 - 和 +
    joined = "\n".join(lines)
    assert "-b" in joined
    assert "+B" in joined


# ===== VersionTree =====


async def _make_chapter(db_initialized: Path) -> int:
    from src.db import SessionLocal
    from src.schemas.chapter import ChapterCreate
    from src.schemas.novel import NovelCreate
    from src.services.chapter_service import ChapterService
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xuanhuan"))
        svc = ChapterService(session)
        ch = await svc.create(
            ChapterCreate(novel_id=novel.id, chapter_number=1, title="第一章", content="原文")
        )
        return ch.id


@pytest.mark.asyncio
async def test_save_version_with_diff(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        v2 = await tree.save_version("新内容 v2", trigger="user_edit")
    assert v2.id is not None
    assert v2.parent_version_id is not None
    assert v2.diff is not None
    assert "-原文" in v2.diff or "-原" in v2.diff
    assert "+新" in v2.diff


@pytest.mark.asyncio
async def test_list_versions_desc(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        await tree.save_version("v2", trigger="user_edit")
        await tree.save_version("v3", trigger="user_edit")
        versions = await tree.list_versions()
    assert len(versions) == 3
    # 按时间倒序
    assert versions[0].trigger == "user_edit"
    assert versions[-1].trigger == "user_create"


@pytest.mark.asyncio
async def test_diff_with_parent_no_parent_returns_empty(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        versions = await tree.list_versions()
        first = versions[-1]  # user_create 没 parent
        diff = await tree.diff_with_parent(first.id)
    assert diff == ""


@pytest.mark.asyncio
async def test_diff_with_parent(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        v2 = await tree.save_version("第二版内容", trigger="user_edit")
        diff = await tree.diff_with_parent(v2.id)
    assert "-原文" in diff
    assert "+第二版内容" in diff


@pytest.mark.asyncio
async def test_diff_between(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        v2 = await tree.save_version("第二版", trigger="user_edit")
        v3 = await tree.save_version("第三版", trigger="user_edit")
        diff = await tree.diff_between(v2.id, v3.id)
    assert "-第二版" in diff
    assert "+第三版" in diff


@pytest.mark.asyncio
async def test_diff_between_not_found(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        with pytest.raises(VersionNotFoundError):
            await tree.diff_between(99999, 99998)


@pytest.mark.asyncio
async def test_rollback_creates_new_version(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        v2 = await tree.save_version("第二版", trigger="user_edit")
        # 把 v3 写为不同的内容
        await tree.save_version("第三版（与第二版不同）", trigger="user_edit")
        # 回滚到 v2
        rolled = await tree.rollback(v2.id)
    assert rolled.trigger == "rollback"
    assert "rollback_to" in (rolled.prompt or "")
    assert rolled.content == "第二版"
    # metadata 含原版本 trigger
    assert rolled.metadata_ is not None
    assert rolled.metadata_.get("original_trigger") == "user_edit"
    assert rolled.metadata_.get("rollback_from_version") == v2.id


@pytest.mark.asyncio
async def test_rollback_to_current_is_noop(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        await tree.save_version("v2", trigger="user_edit")
        # current = v2
        current = (await tree.list_versions())[0]
        result = await tree.rollback(current.id)
    # 没生成新版本
    assert result.id == current.id


@pytest.mark.asyncio
async def test_rollback_not_found(db_initialized: Path) -> None:
    chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        with pytest.raises(VersionNotFoundError):
            await tree.rollback(99999)


# ===== API 端点 =====


@pytest.mark.asyncio
async def test_api_get_version_diff(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.core.versioning.version_tree import VersionTree
    from src.db import SessionLocal
    from src.main import app

    chapter_id = await _make_chapter(db_initialized)
    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        # 用多行内容，确保 unified diff 产生清晰的 + / - 行
        v2 = await tree.save_version("第二版第一段\n第二版第二段\n第二版第三段\n", trigger="user_edit")

    client = TestClient(app)
    resp = client.get(f"/chapters/{chapter_id}/versions/{v2.id}/diff")
    assert resp.status_code == 200
    body = resp.json()
    assert body["to_version_id"] == v2.id
    assert body["from_version_id"] is not None
    assert body["diff"] != ""
    assert body["stats"]["added"] >= 1
    assert body["stats"]["removed"] >= 1


@pytest.mark.asyncio
async def test_api_get_version_diff_with_other_id(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.core.versioning.version_tree import VersionTree
    from src.db import SessionLocal
    from src.main import app

    chapter_id = await _make_chapter(db_initialized)
    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        v2 = await tree.save_version("第二版", trigger="user_edit")
        v3 = await tree.save_version("第三版", trigger="user_edit")

    client = TestClient(app)
    resp = client.get(f"/chapters/{chapter_id}/versions/{v3.id}/diff?other_id={v2.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_version_id"] == v2.id
    assert body["to_version_id"] == v3.id


@pytest.mark.asyncio
async def test_api_get_version_diff_404(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    chapter_id = await _make_chapter(db_initialized)
    client = TestClient(app)
    resp = client.get(f"/chapters/{chapter_id}/versions/99999/diff")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_rollback(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.core.versioning.version_tree import VersionTree
    from src.db import SessionLocal
    from src.main import app

    chapter_id = await _make_chapter(db_initialized)
    async with SessionLocal() as session:
        tree = VersionTree(session, chapter_id=chapter_id)
        v2 = await tree.save_version("第二版", trigger="user_edit")
        await tree.save_version("第三版", trigger="user_edit")

    client = TestClient(app)
    resp = client.post(f"/chapters/{chapter_id}/versions/{v2.id}/rollback")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rolled_back_to"] == v2.id
    assert body["new_version"]["trigger"] == "rollback"
    assert body["new_version"]["content"] == "第二版"


@pytest.mark.asyncio
async def test_api_rollback_404(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    chapter_id = await _make_chapter(db_initialized)
    client = TestClient(app)
    resp = client.post(f"/chapters/{chapter_id}/versions/99999/rollback")
    assert resp.status_code == 404
