"""Skills subpackage (Phase 6.4).

Auto-registers built-in skills on import.
"""

from __future__ import annotations

from .base import Skill, SkillResult

# 导入 builtin skills 触发自动注册
from .builtin import sensitive_word, word_counter  # noqa: F401
from .registry import (
    SkillNotFoundError,
    SkillRegistry,
    get,
    list_skills,
    register,
    registry,
    run_skill,
)

register(word_counter.WordCounterSkill())
register(sensitive_word.SensitiveWordSkill())

__all__ = [
    "Skill",
    "SkillResult",
    "SkillRegistry",
    "SkillNotFoundError",
    "registry",
    "register",
    "get",
    "list_skills",
    "run_skill",
]
