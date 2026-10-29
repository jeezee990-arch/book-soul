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

import os
import sys
from functools import lru_cache
from pathlib import Path

__all__ = [
    "config_dir",
    "data_dir",
    "genres_dir",
    "is_frozen",
    "prompts_dir",
    "repo_root",
    "user_wordbanks_dir",
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
    """词库目录（config/wordbanks/）。

    环境变量 ``BOOK_SOUL_WORDBANK_DIR`` 可覆盖（测试隔离 / 特殊部署用）。
    """
    override = os.environ.get("BOOK_SOUL_WORDBANK_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return config_dir() / "wordbanks"


def data_dir() -> Path:
    """可写数据目录。

    - 环境变量 ``BOOK_SOUL_DATA_DIR`` 优先（桌面端 sidecar 一定会传）
    - 打包态回落：exe 同级 ``data/``（便携模式）
    - 开发态回落：``<repo>/data/dev``

    每次调用都重新读环境变量（不缓存）—— 测试里改 env 能立刻生效。
    """
    override = os.environ.get("BOOK_SOUL_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent / "data"
    return repo_root() / "data" / "dev"


def user_wordbanks_dir() -> Path:
    """**用户可写**的词库目录（词库管理的写盘目标）。

    为什么需要它：打包态下 ``config/`` 被 PyInstaller 打进了 exe（``sys._MEIPASS``），
    那是只读的临时目录 —— 往里写词，重启就没了。所以：

    - 打包态：``<data_dir>/wordbanks``（exe 同级 data/，随文件夹迁移）
    - 开发态：``config/wordbanks``（仓库里的真实词库文件，改了能进 git）

    环境变量 ``BOOK_SOUL_WORDBANK_DIR`` 优先（与 :func:`wordbanks_dir` 一致）。
    """
    override = os.environ.get("BOOK_SOUL_WORDBANK_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return data_dir() / "wordbanks"
    return wordbanks_dir()
