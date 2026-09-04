"""CharacterGenerator / CharacterService 共享的辅助函数（Phase 3.5）。

独立成模块，控制 character_generator.py ≤ 300 行。
"""

from __future__ import annotations

from typing import Any, Protocol

from ..core.llm.base import ChatMessage, ChatResponse
from ..models.character import CHARACTER_ROLES


class CharacterGenerationError(Exception):
    """人物卡自动生成失败（含 LLM 错误、prompt 缺失、解析失败等）。"""


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口（用于注入和 mock）。"""

    provider: str

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ChatResponse: ...


def _normalize_role(role: str) -> str:
    """把 LLM 给的 role 规范化到 :data:`CHARACTER_ROLES` 之一。

    容错：去掉空白、常见近义词；无法归类时回退到 ``"其他"``。
    """
    if not isinstance(role, str):
        return "其他"
    r = role.strip()
    if r in CHARACTER_ROLES:
        return r
    # 常见近义词映射（LLM 偶尔会自己造词）
    alias = {
        "男主": "主角",
        "女主": "主角",
        "protagonist": "主角",
        "伙伴": "主角团",
        "boss": "反派",
        "antagonist": "反派",
        "盟友": "正派",
        "路人": "其他",
        "npc": "其他",
    }
    return alias.get(r, "其他")


def _trim_to_str(value: Any) -> str | None:
    """把 LLM YAML 字段值规整为 ``str | None``。None / 空 → None。"""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    # YAML 偶尔把单行解析成 int/float/bool；统一转 str
    return str(value).strip() or None
