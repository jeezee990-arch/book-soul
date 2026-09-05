"""备份 / 恢复服务测试（Phase 7.4）。"""

from __future__ import annotations

import base64
import zipfile

import pytest


def _make_data_dir(tmp_path) -> None:
    """构造一个最小 data_dir 模拟真实结构。"""
    (tmp_path / "book-soul.db").write_bytes(b"fake db content")
    (tmp_path / "novels").mkdir()
    (tmp_path / "novels" / "a.md").write_text("韩立出生", encoding="utf-8")
    (tmp_path / "novels" / "b.md").write_text("韩立修仙", encoding="utf-8")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text("log line", encoding="utf-8")


# ===== export =====


def test_export_basic(tmp_path) -> None:
    from src.services.backup_service import export_backup

    _make_data_dir(tmp_path)
    data = export_backup(tmp_path)
    assert isinstance(data, bytes)
    assert len(data) > 0
    # 验证 zip 内容
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        names = set(zf.namelist())
    assert "MANIFEST.txt" in names
    assert "book-soul.db" in names
    assert "novels/a.md" in names
    assert "novels/b.md" in names
    assert "logs/app.log" in names


def test_export_no_dir(tmp_path) -> None:
    from src.services.backup_service import BackupError, export_backup

    with pytest.raises(BackupError, match="not found"):
        export_backup(tmp_path / "nonexistent")


def test_export_size_limit(tmp_path, monkeypatch) -> None:
    """超大文件触发大小限制。"""
    from src.services import backup_service
    from src.services.backup_service import BackupError, export_backup

    _make_data_dir(tmp_path)
    monkeypatch.setattr(backup_service, "MAX_BACKUP_BYTES", 10)  # 10 字节限制
    with pytest.raises(BackupError, match="too large"):
        export_backup(tmp_path)


# ===== import =====


def test_import_basic(tmp_path) -> None:
    from src.services.backup_service import export_backup, import_backup

    _make_data_dir(tmp_path)
    zip_data = export_backup(tmp_path)

    # 改原数据，再恢复
    (tmp_path / "book-soul.db").write_bytes(b"changed")
    (tmp_path / "novels" / "a.md").write_text("changed")

    result = import_backup(tmp_path, zip_data, overwrite=True)
    assert result["files"] > 0
    assert result["manifest_present"] is True
    # 验证恢复成功
    assert (tmp_path / "book-soul.db").read_bytes() == b"fake db content"
    assert (tmp_path / "novels" / "a.md").read_text(encoding="utf-8") == "韩立出生"


def test_import_dry_run(tmp_path) -> None:
    """overwrite=False 不写盘，只校验。"""
    from src.services.backup_service import export_backup, import_backup

    _make_data_dir(tmp_path)
    zip_data = export_backup(tmp_path)

    result = import_backup(tmp_path, zip_data, overwrite=False)
    assert result["dry_run"] is True
    # 原数据没变
    assert (tmp_path / "book-soul.db").read_bytes() == b"fake db content"


def test_import_unsafe_path(tmp_path) -> None:
    """含不安全路径的 zip 被拒绝。"""
    import io

    from src.services.backup_service import BackupError, import_backup

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../etc/passwd", "bad")
    with pytest.raises(BackupError, match="Unsafe path"):
        import_backup(tmp_path, buf.getvalue())


def test_import_invalid_zip(tmp_path) -> None:
    from src.services.backup_service import BackupError, import_backup

    with pytest.raises(BackupError, match="Invalid zip"):
        import_backup(tmp_path, b"not a zip file")


def test_import_too_large(tmp_path, monkeypatch) -> None:
    from src.services import backup_service
    from src.services.backup_service import BackupError, import_backup

    monkeypatch.setattr(backup_service, "MAX_BACKUP_BYTES", 5)
    with pytest.raises(BackupError, match="too large"):
        import_backup(tmp_path, b"x" * 100)


def test_import_backs_up_existing_db(tmp_path) -> None:
    """已有 db 会被备份为 .bak.<ts>。"""
    import re

    from src.services.backup_service import export_backup, import_backup

    _make_data_dir(tmp_path)
    zip_data = export_backup(tmp_path)

    result = import_backup(tmp_path, zip_data, overwrite=True)
    assert result["db_backed_up"] is True
    # 找 .bak.<ts> 文件
    bak_files = list(tmp_path.glob("book-soul.db.bak.*"))
    assert len(bak_files) == 1
    # 内容是原 db（fake db content）
    assert bak_files[0].read_bytes() == b"fake db content"
    # 命名格式
    assert re.match(r"book-soul\.db\.bak\.\d{8}-\d{6}", bak_files[0].name)


# ===== API =====


@pytest.mark.asyncio
async def test_api_export_import_roundtrip(tmp_path, db_initialized) -> None:
    """端到端：API 导出 → API 导入。"""
    from fastapi.testclient import TestClient

    from src.core.config import settings
    from src.main import app

    # 把 data_dir 临时切到 tmp_path（让 export 找到）
    old_dir = settings.book_soul_data_dir
    settings.book_soul_data_dir = str(tmp_path)
    try:
        _make_data_dir(tmp_path)
        client = TestClient(app)
        # export
        resp = client.get("/backup/export")
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "book-soul-backup.zip"
        assert body["mime"] == "application/zip"
        zip_b64 = body["content_b64"]
        assert zip_b64

        # 改原数据
        (tmp_path / "book-soul.db").write_bytes(b"changed")

        # import
        resp = client.post(
            "/backup/import",
            json={"zip_b64": zip_b64, "overwrite": True},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["files"] > 0
        assert result["manifest_present"] is True

        # 验证恢复
        assert (tmp_path / "book-soul.db").read_bytes() == b"fake db content"
    finally:
        settings.book_soul_data_dir = old_dir


def test_api_import_invalid_base64() -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    client = TestClient(app)
    resp = client.post(
        "/backup/import",
        json={"zip_b64": "not valid base64!@#$", "overwrite": True},
    )
    assert resp.status_code == 422


def test_api_import_unsafe_zip() -> None:
    """API 层拒绝含 unsafe path 的 zip。"""
    import io
    import zipfile

    from fastapi.testclient import TestClient

    from src.main import app

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../etc/passwd", "bad")
    zip_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    client = TestClient(app)
    resp = client.post(
        "/backup/import",
        json={"zip_b64": zip_b64, "overwrite": True},
    )
    assert resp.status_code == 422
