"""Skill 自动调用层（Phase 性能优化 / Skills 自动化）。

设计：
- 业务代码只需要在生成 LLM 前调 ``augment_prompt(scene, base)``，
  生成 LLM 后调 ``apply_post(scene, text)``。
- manager 内部按 scene 自动筛选并执行匹配触发器的 skills。
- Skill 的 ``_manifest`` 字段决定触发条件（loader 写入）。

不在本文件做的事：
- 注册 skill（loader.py）
- 暴露 REST API（api/skills.py）
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .registry import registry

# 一个 scene 对应的常用 trigger 名称（业务代码按场景调用）
SCENE_NAMES = frozenset(
    {
        "plot_generation",
        "outline_generation",
        "character_generation",
        "chapter_generation",
        "chapter_rewrite",
        "summary",
    }
)


def _skill_manifest(skill: Any) -> dict[str, Any]:
    """取 skill 的 manifest dict（loader 写入）。"""
    return getattr(skill, "_manifest", {}) or {}


def _is_enabled(skill: Any) -> bool:
    """manifest ``enabled`` 字段；缺省 True。"""
    return bool(_skill_manifest(skill).get("enabled", True))


def _matches_scene(skill: Any, scene: str) -> bool:
    """skill 的 ``triggers`` 是否命中当前 scene。

    命中规则（任一满足）：
    - triggers 为空 / 不存在 → 不自动调用
    - ``- scene:<scene>`` 精确匹配
    - ``- all`` 命中所有 scene
    """
    triggers = _skill_manifest(skill).get("triggers") or []
    if not triggers:
        return False
    if "all" in triggers:
        return True
    if f"scene:{scene}" in triggers:
        return True
    return False


def _is_post_skill(skill: Any) -> bool:
    t = _skill_manifest(skill).get("type", "post_process")
    return t in ("post_process", "both")


def _is_pre_skill(skill: Any) -> bool:
    t = _skill_manifest(skill).get("type", "post_process")
    return t in ("pre_process", "both")


def list_for_scene(scene: str) -> list[str]:
    """列出在指定 scene 自动触发的 skill 名（post 模式）。"""
    out: list[str] = []
    for s in registry.list():
        if not _is_enabled(s):
            continue
        if not _is_post_skill(s):
            continue
        if _matches_scene(s, scene):
            out.append(s.name)
    return out


async def apply_post(scene: str, text: str, **kwargs: Any) -> str:
    """对 LLM 生成的文本跑一遍所有匹配的 post-process skill。

    行为约束：
    - 失败的 skill 不影响其他 skill；原文本不被丢失
    - 默认输出 ``run_skill`` 的 ``data.text`` 字段；若 skill 不返 text，则用原 text
    - 返回最终文本（可能与输入不同；也可能与输入相同）
    """
    if not text:
        return text
    current = text
    for skill in registry.list():
        if not _is_enabled(skill):
            continue
        if not _is_post_skill(skill):
            continue
        if not _matches_scene(skill, scene):
            continue
        try:
            result = await skill.execute(text=current, **kwargs)
        except Exception as e:  # noqa: BLE001
            logger.warning("Skill {} (scene {}) failed: {}", skill.name, scene, e)
            continue
        if not result.success:
            logger.warning(
                "Skill {} (scene {}) returned failure: {}",
                skill.name,
                scene,
                result.error,
            )
            continue
        if isinstance(result.data, dict) and "text" in result.data:
            new_text = result.data["text"]
            if isinstance(new_text, str) and new_text:
                current = new_text
        # 否则保留 current
    return current


def augment_prompt(scene: str, base: str = "") -> str:
    """给 system prompt 附加可用 skills 说明（让 LLM 知道哪些工具可用）。

    返回 ``base + skills block``；若无任何 pre-skill 命中 scene，返回原 base。
    """
    available: list[str] = []
    for skill in registry.list():
        if not _is_enabled(skill):
            continue
        if not _is_pre_skill(skill):
            continue
        if not _matches_scene(skill, scene):
            continue
        desc = getattr(skill, "description", "") or ""
        if desc:
            available.append(f"- `{skill.name}`: {desc}")
        else:
            available.append(f"- `{skill.name}`")
    if not available:
        return base
    block = (
        "\n\n## 当前可用的自动 Skills（无需手动调用，系统会自动应用）\n"
        + "\n".join(available)
        + "\n"
    )
    return base + block


def disable(name: str) -> bool:
    """运行时禁用某个 skill（保留在 registry 但关闭自动调用）。"""
    try:
        skill = registry.get(name)
    except KeyError:
        return False
    manifest = _skill_manifest(skill)
    manifest["enabled"] = False
    skill._manifest = manifest  # type: ignore[attr-defined]
    logger.info("Skill {} disabled", name)
    return True


def enable(name: str) -> bool:
    try:
        skill = registry.get(name)
    except KeyError:
        return False
    manifest = _skill_manifest(skill)
    manifest["enabled"] = True
    skill._manifest = manifest  # type: ignore[attr-defined]
    logger.info("Skill {} enabled", name)
    return True


def is_enabled(name: str) -> bool:
    try:
        skill = registry.get(name)
    except KeyError:
        return False
    return _is_enabled(skill)


__all__ = [
    "SCENE_NAMES",
    "list_for_scene",
    "apply_post",
    "augment_prompt",
    "disable",
    "enable",
    "is_enabled",
]
