"""HTML / 多格式导出单元测试（Phase 4.7）。

覆盖：
- export_html：基本转义、标题、引用、列表、分隔线
- _inline_format：HTML 转义 + **粗体**
- API: /novels/{id}/export?format=md|html|docx
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ===== HTML 转换 =====


def test_markdown_to_html_escapes_html() -> None:
    from src.services.export_service import NovelExportService

    html = NovelExportService._markdown_to_html("# Title <script>alert(1)</script>\n")
    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_markdown_to_html_headings() -> None:
    from src.services.export_service import NovelExportService

    md = "# H1\n## H2\n### H3\n"
    html = NovelExportService._markdown_to_html(md)
    assert "<h1>H1</h1>" in html
    assert "<h2>H2</h2>" in html
    assert "<h3>H3</h3>" in html


def test_markdown_to_html_quote_hr_lists() -> None:
    from src.services.export_service import NovelExportService

    md = "> 引用一行\n> 引用二行\n\n---\n\n- item 1\n- item 2\n\n1. one\n2. two\n"
    html = NovelExportService._markdown_to_html(md)
    assert "<blockquote>" in html
    assert "</blockquote>" in html
    assert "<hr>" in html
    assert "<ul>" in html
    assert "<li>item 1</li>" in html
    assert "<ol>" in html
    assert "<li>one</li>" in html


def test_inline_format_bold_and_escape() -> None:
    from src.services.export_service import NovelExportService

    out = NovelExportService._inline_format("**韩立** & <南宫婉>")
    assert "<strong>韩立</strong>" in out
    assert "&amp;" in out
    assert "&lt;南宫婉&gt;" in out


def test_inline_format_does_not_match_unmatched_bold() -> None:
    from src.services.export_service import NovelExportService

    # 单独的 * 不应被替换
    out = NovelExportService._inline_format("这是 *星号* 测试")
    assert "<strong>" not in out


# ===== 集成：export_html 端到端 =====


@pytest.mark.asyncio
async def test_export_html_end_to_end(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.schemas.novel import NovelCreate
    from src.services.export_service import NovelExportService
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(
            NovelCreate(name="测试小说", genre="xuanhuan", description="简介 <test>")
        )
        exporter = NovelExportService(session)
        html = await exporter.export_html(novel.id)
    assert "<!DOCTYPE html>" in html
    assert "测试小说" in html
    assert "&lt;test&gt;" in html
    assert "<h1>测试小说</h1>" in html


@pytest.mark.asyncio
async def test_export_html_novel_not_found(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.services.character_service import NovelNotFoundError
    from src.services.export_service import NovelExportService

    async with SessionLocal() as session:
        exporter = NovelExportService(session)
        with pytest.raises(NovelNotFoundError):
            await exporter.export_html(9999)


# ===== API =====


@pytest.mark.asyncio
async def test_api_export_md(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.db import SessionLocal
    from src.main import app
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(
            NovelCreate(name="测试", genre="xuanhuan")
        )
        novel_id = novel.id

    client = TestClient(app)
    resp = client.get(f"/novels/{novel_id}/export?format=md")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"].endswith(".md")
    assert body["mime"].startswith("text/markdown")
    assert body["content_b64"]  # 非空


@pytest.mark.asyncio
async def test_api_export_html(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.db import SessionLocal
    from src.main import app
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(
            NovelCreate(name="测试", genre="xuanhuan")
        )
        novel_id = novel.id

    client = TestClient(app)
    resp = client.get(f"/novels/{novel_id}/export?format=html")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"].endswith(".html")
    assert "text/html" in body["mime"]
    import base64

    decoded = base64.b64decode(body["content_b64"]).decode("utf-8")
    assert "<!DOCTYPE html>" in decoded


@pytest.mark.asyncio
async def test_api_export_docx_returns_501(db_initialized: Path) -> None:
    """docx 导出未装 python-docx 时返回 501。"""
    from fastapi.testclient import TestClient

    from src.db import SessionLocal
    from src.main import app
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(
            NovelCreate(name="测试", genre="xuanhuan")
        )
        novel_id = novel.id

    client = TestClient(app)
    resp = client.get(f"/novels/{novel_id}/export?format=docx")
    # 未装 python-docx → 501
    assert resp.status_code == 501
    assert "python-docx" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_export_invalid_format(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.get("/novels/1/export?format=exe")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_export_novel_not_found(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.get("/novels/9999/export?format=md")
    assert resp.status_code == 404
