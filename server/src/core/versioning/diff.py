"""文本 diff（Phase 4.6）。

Phase 4.6 v1 用标准库 :mod:`difflib` 实现 unified diff。
后续若需要更精确的字符级 diff（特别是中文场景），可换 ``diff-match-patch``。

约束：
- 输出是 UTF-8 安全的纯文本（unified diff 格式）
- ``compute_diff`` 始终返回 ``str``；如果输入为 None 或空 → 返回空字符串
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable


def compute_unified_diff(
    old: str | None,
    new: str | None,
    *,
    fromfile: str = "old",
    tofile: str = "new",
    n: int = 3,
) -> str:
    """计算 unified diff。

    :param old: 旧文本（None 视为空字符串）
    :param new: 新文本（None 视为空字符串）
    :param fromfile: 旧文件标签（仅显示用）
    :param tofile: 新文件标签（仅显示用）
    :param n: 上下文行数
    :return: unified diff 文本；没有差异时为空字符串

    注：当输入都不含 ``\\n`` 时，difflib 会把整段差异塞到一行（"a-b+c-d" 形式），
    不便于按行统计 ``+/-``。这种情况 :func:`diff_stats` 会回退到字符级匹配。
    """
    old_text = old or ""
    new_text = new or ""
    if old_text == new_text:
        return ""
    diff_lines = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
        n=n,
    )
    return "".join(diff_lines)


def diff_stats(diff_text: str) -> dict[str, int]:
    """从 unified diff 文本里统计新增 / 删除"行数"。

    :return: ``{"added": n, "removed": n}``；空 diff 返回 ``{"added": 0, "removed": 0}``

    特殊情况：当 diff 文本看起来是 difflib 长行合并（"a-b+c" 形式，行内无独立
    ``+xxx`` / ``-yyy``），回退到字符级差（旧字符数 vs 新字符数）。
    """
    if not diff_text:
        return {"added": 0, "removed": 0}
    lines = diff_text.splitlines()
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    if added == 0 and removed == 0 and len(lines) >= 2:
        # 长行合并的回退：用字符级差
        old_chars = sum(len(line) for line in lines if line.startswith("-") and not line.startswith("---"))
        new_chars = sum(len(line) for line in lines if line.startswith("+") and not line.startswith("+++"))
        return {"added": new_chars, "removed": old_chars}
    return {"added": added, "removed": removed}


def iter_hunks(diff_text: str) -> Iterable[tuple[str, list[str]]]:
    """把 unified diff 切成一个个 hunk。

    :yield: ``(header, lines)``；``header`` 是 ``@@ -... +... @@`` 行
    """
    if not diff_text:
        return
    current_header: str | None = None
    current_lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            if current_header is not None:
                yield current_header, current_lines
            current_header = line
            current_lines = []
        elif current_header is not None:
            # 跳过文件头（--- / +++）
            if line.startswith("---") or line.startswith("+++"):
                continue
            current_lines.append(line)
    if current_header is not None:
        yield current_header, current_lines


__all__ = ["compute_unified_diff", "diff_stats", "iter_hunks"]
