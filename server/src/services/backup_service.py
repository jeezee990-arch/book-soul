"""备份 / 恢复服务（Phase 7.4）。

设计：
- 备份：把 data_dir（含 db / novels/ / logs/）打包为 zip
- 恢复：上传 zip → 验证 → 解压覆盖
- 安全性：限制 zip 大小、路径检查（防 zip slip）

不做的事：
- 不重启服务（导入后需用户手动重启 Tauri）
- 不上传到云端
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# 备份大小限制（500 MB）
MAX_BACKUP_BYTES = 500 * 1024 * 1024
# 允许的 zip 内文件名前缀（防 zip slip）
ALLOWED_PATH_PREFIXES: tuple[str, ...] = (
    "book-soul.db",
    "MANIFEST.txt",
    "novels/",
    "logs/",
)


class BackupError(Exception):
    """备份/恢复失败。"""


def export_backup(data_dir: Path | str) -> bytes:
    """把 data_dir 打包为 zip 字节流。

    :raises BackupError: 目录不存在 / 超出大小 / IO 失败
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise BackupError(f"Data dir not found: {data_dir}")

    # 计算大小（只算 novels/ + db + logs/）
    total = 0
    for sub in ("book-soul.db", "novels", "logs"):
        p = data_dir / sub
        if p.is_file():
            total += p.stat().st_size
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
    if total > MAX_BACKUP_BYTES:
        raise BackupError(
            f"Backup too large: {total / 1024 / 1024:.1f} MB (max {MAX_BACKUP_BYTES // 1024 // 1024} MB)"
        )

    buf = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 写一个 manifest 标记
        manifest = (
            f"# Book Soul Backup\n"
            f"version: 1\n"
            f"created_at: {datetime.now().isoformat()}\n"  # noqa: DTZ005
            f"data_dir: {data_dir.absolute()}\n"
        )
        zf.writestr("MANIFEST.txt", manifest)

        # book-soul.db
        db_file = data_dir / "book-soul.db"
        if db_file.is_file():
            zf.write(db_file, "book-soul.db")

        # novels/
        novels_dir = data_dir / "novels"
        if novels_dir.is_dir():
            for f in novels_dir.rglob("*"):
                if f.is_file():
                    arc = "novels/" + str(f.relative_to(novels_dir))
                    zf.write(f, arc)

        # logs/（可选）
        logs_dir = data_dir / "logs"
        if logs_dir.is_dir():
            for f in logs_dir.rglob("*.log"):
                if f.is_file():
                    arc = "logs/" + str(f.relative_to(logs_dir))
                    zf.write(f, arc)

    data = buf.getvalue()
    logger.info(
        "Exported backup: {} ({} MB, {})",
        timestamp,
        len(data) / 1024 / 1024,
        data_dir,
    )
    return data


def import_backup(
    data_dir: Path | str,
    zip_bytes: bytes,
    *,
    overwrite: bool = True,
) -> dict[str, Any]:
    """从 zip 恢复。

    流程：
    1. 验证 zip（不爆大小）
    2. 解压到临时目录
    3. 安全检查（路径必须在允许前缀内）
    4. 覆盖到 data_dir
    5. 备份当前 db 为 db.bak.<ts>（防意外）

    :param overwrite: True 覆盖现有；False 校验后不写入
    :return: 导入摘要（恢复的文件数 / 大小）
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise BackupError(f"Data dir not found: {data_dir}")
    if len(zip_bytes) > MAX_BACKUP_BYTES:
        raise BackupError(f"Zip too large: {len(zip_bytes) / 1024 / 1024:.1f} MB")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # 安全检查：每个文件必须在允许前缀
            names = zf.namelist()
            for name in names:
                if name.endswith("/"):
                    continue
                if not any(name.startswith(p) for p in ALLOWED_PATH_PREFIXES):
                    raise BackupError(f"Unsafe path in zip: {name!r}")

            if not overwrite:
                return {"files": len(names), "dry_run": True}

            # 备份现有 db（如果存在）
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
            existing_db = data_dir / "book-soul.db"
            if existing_db.is_file():
                backup_db = data_dir / f"book-soul.db.bak.{timestamp}"
                shutil.copy2(existing_db, backup_db)
                logger.info("Backed up existing db to {}", backup_db)

            # 解压到临时目录 → 移动到目标
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                zf.extractall(tmp)
                # 覆盖 / 合并
                restored = 0
                for name in names:
                    if name.endswith("/"):
                        continue
                    src = tmp / name
                    dst = data_dir / name
                    if not src.is_file():
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    restored += 1
                logger.info("Restored {} files to {}", restored, data_dir)
                return {
                    "files": restored,
                    "manifest_present": "MANIFEST.txt" in names,
                    "db_backed_up": existing_db.is_file(),
                }
    except zipfile.BadZipFile as e:
        raise BackupError(f"Invalid zip file: {e}") from e


__all__ = ["BackupError", "export_backup", "import_backup", "MAX_BACKUP_BYTES"]
