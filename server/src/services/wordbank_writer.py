"""词库 YAML 写盘工具（备份 → 原子写）。

为什么单独一个模块
------------------
``wordbank_service`` 负责**业务语义**（加词 / 改词 / 删词），
这里负责**文件怎么安全地写出去**（先备份、再写临时文件、最后 ``os.replace``）。
拆开是为了让 service 保持可读，也让"写盘行为"可以单独测。

三条硬规则
----------
1. **原子写**：先写同目录临时文件，再 ``os.replace`` 覆盖目标。
   直接 ``write_text`` 到目标文件的话，进程中途被杀会留下**半截 YAML**，
   下次启动词库直接解析失败（整个板块的词都没了）。
2. **写前备份**：旧文件复制到同目录 ``.backup/{板块}-{时间戳}.yaml``，
   只保留最近 ``MAX_BACKUPS`` 份。写坏了可以手工拷回去。
3. **不碰别的板块**：调用方只传**一个板块**的完整数据，本模块只写那一个文件。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

__all__ = [
    "BACKUP_DIR_NAME",
    "MAX_BACKUPS",
    "backup_file",
    "dump_wordbank",
    "load_wordbank_file",
    "write_wordbank",
]

# 备份子目录名（放在词库目录同级，不参与题材扫描）
BACKUP_DIR_NAME = ".backup"

# 每个板块最多保留多少份备份
MAX_BACKUPS = 20


def load_wordbank_file(path: Path) -> dict[str, Any]:
    """读一个词库 YAML，返回 dict（顶层必须是 dict）。

    文件不存在 → 抛 ``FileNotFoundError``（调用方决定怎么处理）。
    """
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Wordbank root must be a dict, got {type(data).__name__}: {path}")
    return data


def dump_wordbank(data: dict[str, Any]) -> str:
    """把词库 dict 序列化成 YAML 文本。

    - ``allow_unicode=True``：中文不转义（否则文件里全是 \\uXXXX）
    - ``sort_keys=False``：保留原有顺序（name → themes → characters → …）
    - ``width=4096``：避免长行被折行
    """
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=4096)


def _timestamp() -> str:
    """备份文件名用的时间戳（本地时区，精确到微秒避免同秒覆盖）。"""
    return datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S-%f")


def _prune_backups(backup_dir: Path, stem: str) -> None:
    """只保留最近 ``MAX_BACKUPS`` 份备份（按修改时间倒序）。"""
    files = sorted(
        backup_dir.glob(f"{stem}-*.yaml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[MAX_BACKUPS:]:
        try:
            old.unlink()
        except OSError as e:  # pragma: no cover - 删不掉不影响主流程
            logger.warning("Failed to prune wordbank backup {}: {}", old, e)


def backup_file(path: Path) -> Path | None:
    """写盘前备份旧文件，返回备份路径（原文件不存在时返回 None）。

    备份放在 ``<词库目录>/.backup/{板块名}-{时间戳}.yaml``。
    """
    if not path.is_file():
        return None
    backup_dir = path.parent / BACKUP_DIR_NAME
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"{path.stem}-{_timestamp()}{path.suffix}"
        shutil.copy2(path, target)
    except OSError as e:
        # 备份失败不阻塞写入（写盘本身还有原子性兜底）
        logger.warning("Failed to backup wordbank {}: {}", path, e)
        return None
    _prune_backups(backup_dir, path.stem)
    return target


def write_wordbank(path: Path, data: dict[str, Any]) -> Path | None:
    """原子写词库文件，返回备份路径（没有旧文件时为 None）。

    步骤：备份 → 写同目录临时文件 → ``os.replace`` 覆盖 → 删除临时文件（失败时）。
    """
    backup = backup_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dump_wordbank(data)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # 同目录 replace 是原子操作：要么还是旧文件，要么整个换成新文件
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return backup
