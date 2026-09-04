"""LLM 输出后处理工具（Phase 3.3+）。

集中放置各个 service 都会用到的格式化/清洗函数，
避免重复实现和不一致行为。
"""

from __future__ import annotations

import re

# 匹配 ``<think>...</think>`` 块（DOTALL 跨行；可能有多个）
_THINKING_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_thinking(text: str) -> str:
    """剥掉 LLM 输出的 ``<think>...</think>`` 推理块（minimax 推理模型会输出）。

    - 没有 think 块 → 原样返回
    - 有 think 块 → 替换为空（保留正文）
    - 多次匹配（一般 1 次足够）
    """
    return _THINKING_RE.sub("", text).strip()


def extract_json_object(text: str) -> dict:
    """从 LLM 输出里提取 JSON 对象。

    策略：
    1. 剥掉 ``<think>...</think>`` 块（如果还在）
    2. 找第一个 ``{`` 到最后一个 ``}`` 的范围
    3. ``json.loads`` 解析
    4. 解析失败 → 抛 :class:`ValueError`

    LLM 经常在 JSON 前后加"以下是..."等套话；这个函数容忍这种噪声。
    """
    import json

    cleaned = strip_thinking(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in LLM output: {cleaned[:200]!r}")
    candidate = cleaned[start : end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from LLM output: {e}; raw: {candidate[:300]!r}"
        ) from e
    if not isinstance(obj, dict):
        raise ValueError(f"LLM output is not a JSON object: {type(obj).__name__}")
    return obj
