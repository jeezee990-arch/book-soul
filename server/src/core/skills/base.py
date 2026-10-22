"""Skill 接口定义（Phase 6.4）。

设计：
- 用 Protocol 定义 Skill 接口（duck typing）
- SkillResult dataclass 统一返回结构
- 业务代码依赖此接口而非具体实现
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class Skill(Protocol):
    """Skill 接口（自研 Protocol，参考 PROJECT_PLAN.md §6.4 关键代码）。"""

    name: str
    description: str
    input_schema: dict[str, Any]
    requires_llm: bool

    async def execute(self, **kwargs: Any) -> SkillResult: ...


__all__ = ["Skill", "SkillResult"]
