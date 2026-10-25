"""ORM 模型包。

模块 0.6：Base + Novel（示例）
Phase 1.1：补全 Novel 字段
Phase 1.2：Character + CharacterVersion
Phase 1.3：Chapter + ChapterVersion
Phase 1.4：Outline
Phase 1.5：Inspiration
后续：Skill 等
"""

from .base import Base, TimestampMixin
from .chapter import CHAPTER_STATUSES, VERSION_TRIGGERS, Chapter, ChapterVersion
from .character import CHARACTER_ROLES, Character, CharacterVersion
from .chat import CHAT_ROLES, ChatConversation, ChatMessage, ChatProject
from .inspiration import INSPIRATION_TYPES, Inspiration
from .novel import Novel
from .outline import OUTLINE_TYPES, Outline

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
    "Outline",
    "OUTLINE_TYPES",
    "Inspiration",
    "INSPIRATION_TYPES",
    "ChatProject",
    "ChatConversation",
    "ChatMessage",
    "CHAT_ROLES",
]
