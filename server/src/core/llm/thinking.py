"""思考内容净身：保证前端只看到**纯中文**（2026-10-29 新增）。

用户实测（2026-10-29 实机走查图1）
----------------------------------
生成剧情时，剧情卡片里直接流出模型的**英文规划文字**::

    viation. Opening hook. Need count 200-40

用户诉求：**「生成剧情的时候需要修改为纯中文思考输出，不要含有代码以及英文」**。

三道防线
--------
1. **prompt 层**：prompt 里明确写「全程用中文思考」。这能大幅提高中文比例，
   但**不保证** —— 推理模型（MiniMax-M3.1-Flash）用什么语言思考由它自己决定，
   prompt 只能影响、不能强制。
2. **协议层（本模块）**：thinking 事件转发前过一道净身器，把英文单词与
   代码痕迹**删掉**，只留中文。即使模型想的是英文，用户看到的也是纯中文。
3. **展示层**：前端拿到的 ``text`` 一定已经是净身后的中文。

为什么是「删掉脏字符」而不是「整段丢弃」
--------------------------------------
整段丢弃会让思考期变成"什么都没有" → 用户又回到"卡住不动"的体感
（AGENTS.md §4.7 踩过一次的坑：思考被丢掉 → 前端一个字收不到）。
删脏字符能保住中文句子；只有**纯英文/纯代码**的片段才会被清空 ——
这时前端用占位符顶上（见 ``THINKING_PLACEHOLDER``），保证"模型思考中"始终可见。

净身规则
--------
- 允许：汉字、中文标点（、。《》「」）、全角标点（，。（）等）、阿拉伯数字、空白。
- 删除：ASCII 字母（英文单词）、ASCII 标点与代码符号（``{}<>;=:()[]`` 等）、
  全角字母（Ａ-Ｚ）、Markdown 强调符（``*``、``#``、``_``）。
- 判废：清洗后**没有汉字**，或汉字占非空白字符的比例 < 30%（基本都是数字）→ 返回空串。
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "THINKING_PLACEHOLDER",
    "sanitize_thinking",
    "thinking_event",
]

# 前端在"思考内容被净身清空"时用来顶替的占位符（纯中文，不会泄漏任何原文）。
THINKING_PLACEHOLDER = "正在思考……"

# 允许保留的字符：数字 + 空白 + 破折号/引号/省略号 + 中文标点 + 汉字 + 全角标点。
#
# ⚠️ 全角区段刻意**排除** Ａ-Ｚ / ａ-ｚ（U+FF21-FF3A / U+FF41-FF5A）：
# 全角字母也是"英文"，同样要删。
_ALLOWED = re.compile(
    r"[^0-9\s\u2014\u2015\u2018-\u201d\u2026"
    r"\u3000-\u303f\u4e00-\u9fff"
    r"\uff01-\uff20\uff3b-\uff40\uff5b-\uff65]"
)

# 单个汉字判定
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff]")

# 连续空格/制表符压成一个
_MULTI_SPACE = re.compile(r"[ \t]{2,}")

# 汉字占比下限：低于这个值说明剩下的基本都是数字，没有展示价值
_MIN_CJK_RATIO = 0.3


def sanitize_thinking(text: str) -> str:
    """把一段模型思考洗成"纯中文"。

    :param text: 原始思考片段（可能为空、可能混着英文与代码）
    :return: 去掉英文/代码痕迹后的片段；没有可展示的中文时返回**空串**
    """
    if not text:
        return ""
    cleaned = _ALLOWED.sub("", text)
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
    if not cleaned:
        return ""
    cjk_chars = _CJK_CHAR.findall(cleaned)
    if not cjk_chars:
        return ""
    nonspace_count = sum(1 for c in cleaned if not c.isspace())
    if not nonspace_count:
        return ""
    if len(cjk_chars) / nonspace_count < _MIN_CJK_RATIO:
        return ""
    return cleaned


def thinking_event(text: str, *, max_chars: int | None = None, **extra: Any) -> dict[str, Any]:
    """构造 ``thinking`` 事件负载（已净身）。

    :param text: 原始思考片段
    :param max_chars: 净身后最多保留多少字（``None`` = 不限）。
        调用方常用它做"思考内容最多转发 N 字"的限流。
    :param extra: 额外字段（如 ``index`` / ``phase``）
    :return: ``{"event": "thinking", "text": <纯中文>, "dirty": bool, **extra}``

    ``dirty`` 为 True 表示原文含英文/代码、被净身器清掉了一部分（或被截断）——
    前端据此知道"模型仍在思考，只是没有可展示的中文"，应该显示占位符而不是空白。
    """
    clean = sanitize_thinking(text)
    truncated = clean[:max_chars] if max_chars is not None else clean
    event: dict[str, Any] = {"event": "thinking", "text": truncated}
    if truncated != text.strip():
        event["dirty"] = True
    event.update(extra)
    return event
