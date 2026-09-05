"""Skill 注册表（Phase 6.4）。

提供：
- :func:`register` 注册一个 Skill
- :func:`get` 按名称取
- :func:`list_skills` 列出所有（按注册顺序）
- :func:`run_skill` 执行

用法：
    from src.core.skills import registry
    from src.core.skills.builtin.word_counter import WordCounterSkill

    registry.register(WordCounterSkill())
    result = await registry.run("word_counter", text="hello")
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .base import Skill, SkillResult


class SkillNotFoundError(KeyError):
    """技能未注册。"""


class SkillRegistry:
    """Skill 注册表（单例模式）。"""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            logger.warning("Skill {} already registered; overwriting", skill.name)
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise SkillNotFoundError(f"Skill not registered: {name!r}")
        return self._skills[name]

    def list(self) -> list[Skill]:
        return list(self._skills.values())

    def has(self, name: str) -> bool:
        return name in self._skills

    async def run(self, name: str, **kwargs: Any) -> SkillResult:
        skill = self.get(name)
        # 检查必填字段
        required = set(skill.input_schema.get("required", []))
        missing = required - set(kwargs.keys())
        if missing:
            return SkillResult(
                success=False,
                error=f"Missing required fields: {sorted(missing)}",
            )
        # 多余字段不阻止
        try:
            return await skill.execute(**kwargs)
        except Exception as e:  # noqa: BLE001
            logger.error("Skill {} execute failed: {}", name, e)
            return SkillResult(success=False, error=f"{type(e).__name__}: {e}")


# 模块级单例
registry = SkillRegistry()


def register(skill: Skill) -> None:
    """便捷函数：``registry.register(skill)``."""
    registry.register(skill)


def get(name: str) -> Skill:
    """便捷函数：``registry.get(name)``."""
    return registry.get(name)


def list_skills() -> list[Skill]:
    """便捷函数：``registry.list()``."""
    return registry.list()


async def run_skill(name: str, **kwargs: Any) -> SkillResult:
    """便捷函数：``await registry.run(name, **kwargs)``."""
    return await registry.run(name, **kwargs)


__all__ = [
    "SkillRegistry",
    "SkillNotFoundError",
    "registry",
    "register",
    "get",
    "list_skills",
    "run_skill",
]
