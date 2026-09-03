"""ORM 模型包。

模块 0.6：Base + Novel（示例）
Phase 1.1：补全 Novel 字段
Phase 1.2：Character + CharacterVersion
Phase 1.3：Chapter + ChapterVersion
后续：Outline / Inspiration / Skill 等
"""

from .base import Base, TimestampMixin
from .chapter import CHAPTER_STATUSES, VERSION_TRIGGERS, Chapter, ChapterVersion
from .character import CHARACTER_ROLES, Character, CharacterVersion
from .novel import Novel

__all__ = [
    "Base",
    "TimestampMixin",
    "Novel",
    "Character",
    "CharacterVersion",
    "CHARACTER_ROLES",
    "Chapter",
    "ChapterVersion",
    "CHAPTER_STATUSES",
    "VERSION_TRIGGERS",
]
