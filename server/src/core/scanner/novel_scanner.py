"""小说目录树扫描（Phase 6.3）。

设计：
- 扫描指定根目录下所有子目录（递归，最大深度 3）
- 调 :func:`novel_detector.is_novel_dir` 判定
- 返回 :class:`DetectedNovel` 列表
"""

from __future__ import annotations

from pathlib import Path

from .novel_detector import DetectedNovel, extract_metadata, is_novel_dir

# 扫描限制
MAX_DEPTH = 3
MAX_NOVELS = 200  # 单次扫描最多返回 200 个，防爆


def scan_directory(root_path: str, *, max_depth: int = MAX_DEPTH) -> list[DetectedNovel]:
    """扫描 root_path 下所有子目录，列出疑似小说。

    - max_depth=0 只扫根
    - max_depth=3 扫到 3 层子目录（默认）
    - 超过 MAX_NOVELS 截断（防用户误指超大目录）
    """
    root = Path(root_path)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root_path}")

    results: list[DetectedNovel] = []

    def _walk(p: Path, depth: int) -> None:
        if len(results) >= MAX_NOVELS:
            return
        if depth > max_depth:
            return
        # 跳过隐藏目录
        if p.name.startswith("."):
            return
        if is_novel_dir(str(p)):
            try:
                results.append(extract_metadata(str(p)))
            except Exception:  # noqa: BLE001
                return
            return  # 命中后不再下钻
        # 没命中 → 递归
        try:
            children = list(p.iterdir())
        except (PermissionError, OSError):
            return
        for child in children:
            if child.is_dir():
                _walk(child, depth + 1)

    _walk(root, 0)
    return results


__all__ = ["scan_directory", "MAX_DEPTH", "MAX_NOVELS"]
