"""路径解析统一入口（开发态 / 打包态）。

为什么存在
----------
项目里原本有 **7 处**各自实现 `_find_repo_root()`（向上找含
``config/`` 且含 ``pyproject.toml`` 的目录）。问题有两个：

1. **重复** —— 改一处漏六处，是典型的"同一个常量散落多处"
2. **打包态失效** —— PyInstaller 打包后没有 ``pyproject.toml``，
   向上找永远找不到，提示词 / 词库 / 题材全部加载失败

打包态的正确做法是用 ``sys._MEIPASS``（PyInstaller 把 ``--add-data``
打进去的文件解包到这里）。本模块统一处理这件事。
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

__all__ = [
    "config_dir",
    "genres_dir",
    "is_frozen",
    "prompts_dir",
    "repo_root",
    "wordbanks_dir",
]


def is_frozen() -> bool:
    """当前是否运行在 PyInstaller 打包产物里。"""
    return bool(getattr(sys, "frozen", False))


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """项目根目录。

    - 打包态：``sys._MEIPASS``（PyInstaller 解包目录）
    - 开发态：向上找同时含 ``config/`` 与 ``pyproject.toml`` 的目录
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)

    p = Path(__file__).resolve().parent
    for _ in range(8):
        if (p / "config").is_dir() and (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    # 兜底：core/paths.py → core → src → server → 根
    return Path(__file__).resolve().parents[3]


def config_dir() -> Path:
    """配置目录（config/）。"""
    return repo_root() / "config"


def prompts_dir() -> Path:
    """提示词目录（config/prompts/）。"""
    return config_dir() / "prompts"


def genres_dir() -> Path:
    """题材常识目录（config/genres/）。"""
    return config_dir() / "genres"


def wordbanks_dir() -> Path:
    """词库目录（config/wordbanks/）。"""
    return config_dir() / "wordbanks"
