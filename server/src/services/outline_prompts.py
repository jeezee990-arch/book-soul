"""两阶段大纲的 prompt 模板加载。

为什么单独一个文件
------------------
阶段一（:mod:`src.services.outline_skeleton`）与阶段二
（:mod:`src.services.outline_detail`）都要读 ``config/prompts/outline_*.yaml``。
把加载逻辑抽出来，两边共用一份实现，也不会因为互相 import 形成循环依赖
（异常类型在 :mod:`src.services.outline_errors`）。

模板位置由 :func:`src.core.paths.prompts_dir` 决定 —— 打包态走
``sys._MeIPASS/config/prompts``（PyInstaller 解包目录）。
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from ..core.paths import prompts_dir
from .outline_errors import TwoPhaseOutlineError

__all__ = ["load_phase_prompt"]


@lru_cache(maxsize=8)
def load_phase_prompt(name: str) -> str:
    """加载 ``config/prompts/outline_{name}.yaml`` 的 ``prompt`` 字段。

    :param name: 模板名（``skeleton`` / ``volume_detail`` / ``continue_skeleton`` …）
    :raises TwoPhaseOutlineError: 模板不存在或缺 ``prompt`` 字段
    """
    path = prompts_dir() / f"outline_{name}.yaml"
    if not path.is_file():
        raise TwoPhaseOutlineError(f"Outline prompt not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "prompt" not in data:
        raise TwoPhaseOutlineError(f"Outline prompt {path} missing 'prompt' field")
    return str(data["prompt"])
