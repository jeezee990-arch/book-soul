"""ORM 模型包。

模块 0.6：Base + Novel（示例）
Phase 1.1：补全 Novel 字段
Phase 1.2：Character + CharacterVersion
后续：Chapter / Outline / Inspiration / Skill 等
"""

from .base import Base, TimestampMixin
from .character import CHARACTER_ROLES, Character, CharacterVersion
from .novel import Novel

__all__ = [
    "Base",
    "TimestampMixin",
    "Novel",
    "Character",
    "CharacterVersion",
    "CHARACTER_ROLES",
]
