"""用户运行时设置（``.book-soul-settings.yaml``）的读写入口。

为什么单独放 core
----------------
``core/llm/factory.py`` 需要知道"用户在设置页选了哪个 provider / 模型"
（否则设置页形同虚设），但项目分层是 ``core ← services ← api``：
core 不能反向依赖 services。

所以把"读"这一半下沉到 core（这里），"写"仍然由
``services/settings_service.py`` 负责（它要校验 + 合并）。

文件位置：``<data_dir>/.book-soul-settings.yaml``。
``data_dir`` 由环境变量 ``BOOK_SOUL_DATA_DIR`` 决定；
打包版默认是 exe 同级 ``data/``（便携模式）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

# 用户设置文件名（settings_service 写、这里读，两边必须一致）
SETTINGS_FILENAME = ".book-soul-settings.yaml"


def _data_dir() -> Path:
    """当前数据目录。

    每次调用都重新看环境变量 ``BOOK_SOUL_DATA_DIR``，而不是用
    ``core.config`` 那个 import 时就固定下来的单例 —— 这样测试里改 env
    能立刻生效，也不受模块被重新 import 的影响。
    """
    override = os.environ.get("BOOK_SOUL_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    from .config import settings as app_settings

    return app_settings.data_dir


def settings_file_path() -> Path:
    """用户设置文件的绝对路径。"""
    return _data_dir() / SETTINGS_FILENAME


def read_settings_yaml(path: Path | None = None) -> dict[str, Any]:
    """读用户设置 yaml。

    文件不存在 / 内容损坏都返回空 dict —— 绝不因为设置文件坏了就起不来。

    :param path: 显式指定路径（测试用 tmp_path）；None 表示用默认位置。
    """
    target = path if path is not None else settings_file_path()
    if not target.is_file():
        return {}
    try:
        with target.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to read {}: {}; using defaults", target, e)
        return {}
    return data if isinstance(data, dict) else {}


def get_user_llm_prefs() -> tuple[str, str]:
    """取用户在设置页选的 ``(provider, model)``。

    未设置时返回 ``("", "")``，由调用方回落到 ``config/llm.yaml`` 的默认值。

    为什么不用缓存：设置一改就要立刻生效（用户在设置页点保存，
    下一次生成就该用新模型），文件很小，读一次几毫秒。
    """
    raw = read_settings_yaml()
    llm = raw.get("llm") or {}
    if not isinstance(llm, dict):
        return "", ""
    return str(llm.get("provider") or ""), str(llm.get("model") or "")
