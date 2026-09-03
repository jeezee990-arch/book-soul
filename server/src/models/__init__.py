"""ORM 模型包。

模块 0.6：Base + Novel（示例）
Phase 1.1 起会补：Character / Chapter / Outline / Inspiration / Skill 等
"""

from .base import Base, TimestampMixin
from .novel import Novel

__all__ = ["Base", "TimestampMixin", "Novel"]
