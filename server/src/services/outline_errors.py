"""大纲生成的公共异常类型。

为什么单独一个文件
------------------
:mod:`src.services.outline_generator`、:mod:`src.services.outline_two_phase`、
:mod:`src.services.outline_single_phase` 三处都会抛"大纲生成失败"，
但它们互相引用会形成循环 import。把基类抽到这里，三边都从这里继承。

调用方（API 层、测试）只需要 catch :class:`OutlineGenerationError` 一个类型。
"""

from __future__ import annotations

__all__ = ["OutlineGenerationError", "TwoPhaseOutlineError"]


class OutlineGenerationError(Exception):
    """大纲生成失败（LLM 调用失败 / JSON 解析失败 / 结构非法）。"""


class TwoPhaseOutlineError(OutlineGenerationError):
    """两阶段大纲生成失败（阶段一失败 / 骨架不可用）。

    放在这里而不是 :mod:`src.services.outline_two_phase`，是为了让
    阶段一（:mod:`src.services.outline_skeleton`）与阶段二
    （:mod:`src.services.outline_detail`）都能引用它而不形成循环 import。
    """
