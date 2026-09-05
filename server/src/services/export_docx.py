"""Word（docx）导出（Phase 4.7 占位）。

实现状态：需要 ``python-docx`` 库；当前未装。端点会返回 501 提示。

装包后接入步骤：
1. ``uv add python-docx``（先问用户）
2. 把下面的 ``_build_docx`` 实现填好（参考 PROJECT_PLAN.md §4.7 关键代码）
3. 端点会从 501 切到 200 + 二进制流
"""

from __future__ import annotations


class WordExportUnavailableError(Exception):
    """word 导出未启用（python-docx 未装）。"""


def build_docx_bytes(*_args: object, **_kw: object) -> bytes:
    """占位：抛 :class:`WordExportUnavailableError`。

    装包后实现：用 ``from docx import Document`` 创建 doc，按章节标题 + 段落写出。
    """
    raise WordExportUnavailableError(
        "Word 导出未启用：请先安装 python-docx（uv add python-docx）"
    )


__all__ = ["WordExportUnavailableError", "build_docx_bytes"]
