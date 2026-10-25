"""半截 JSON 的容错解析（流式渲染大纲用）。

为什么需要（2026-10-25）
----------------------
大纲生成返回的是一个大 JSON（20-40 章，可能几万字符）。流式传输时用户
拿到的是"半截 JSON"——旧实现把原始 JSON 文本直接丢给前端用 ``<pre>``
渲染，用户看到的就是一堆英文代码（用户反馈的"把代码也显示出来"）。

要让用户看到**中文剧情**，就得在流式过程中把已经写完的部分解析出来。
但流式中间态的 JSON 一定不完整，``json.loads`` 必然失败。

解法：扫描出**最后一个完整闭合的容器**（对象或数组），在那里切断，
把外层还没闭合的括号补齐，再解析。这样能拿到"已完成的那几卷 / 几章"。

例子（流式中间态）::

    {"volumes": [{"name": "第一卷", "chapters": [{"title": "第一章", "sum

补齐后得到::

    {"volumes": [{"name": "第一卷", "chapters": [{"title": "第一章", "sum]}]}

→ 能解析出第一卷和第一章的**已写完**字段。
"""

from __future__ import annotations

import json
from typing import Any

__all__ = ["parse_partial_json"]


def _closers(stack: list[str]) -> str:
    """把未闭合的容器栈补成对应的右括号序列。

    :param stack: 容器类型列表（``"{"`` / ``"["``），栈顶是 innermost
    :return: 需要补在末尾的右括号字符串（innermost 在前）
    """
    return "".join("]" if c == "[" else "}" for c in reversed(stack))


def _last_closed_container(text: str) -> tuple[int | None, list[str]]:
    """找出最后一个**完整闭合**的容器位置，以及它外层还没闭合的容器栈。

    :param text: JSON 文本片段（不含前导噪声）
    :return: ``(切断位置, 外层未闭合容器栈)``；没有任何容器闭合过时
        切断位置为 ``None``
    """
    stack: list[str] = []
    in_str = False
    escaped = False
    last_cut: int | None = None
    last_stack: list[str] = []

    for i, ch in enumerate(text):
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            # 这个容器闭合了 —— 它的内容此刻是完整的，
            # 把它当作候选切断点（外层用栈补括号）。
            last_cut = i + 1
            last_stack = list(stack)

    return last_cut, last_stack


def parse_partial_json(raw: str) -> dict[str, Any] | None:
    """从"半截 JSON"里提取已经完整写出来的部分。

    三步：
    1. 去掉前导噪声（找第一个 ``{``）
    2. 整段能解析 → 直接返回
    3. 整段解析不了 → 在最后一个闭合容器处切断 + 补齐外层括号再解析

    :param raw: LLM 已经吐出来的原始文本（可能只有一半）
    :return: 解析出的 dict；**任何一步失败都返回 None**（调用方应视为
        "还没解析出东西"，而不是抛异常 —— 流式中间态解析失败是常态）
    """
    if not raw:
        return None
    start = raw.find("{")
    if start == -1:
        return None
    text = raw[start:]

    # 2) 整段就是完整 JSON
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        return obj if isinstance(obj, dict) else None

    # 3) 切断 + 补齐
    cut, stack = _last_closed_container(text)
    if cut is None:
        return None
    candidate = text[:cut] + _closers(stack)
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
