"""Skill 自动发现 + 装载（Phase 性能优化 / 任务 Skills 自动化）。

设计：
- Skill 两种来源：
  1. **内置**（``server/src/core/skills/builtin/*.py``）—— 跟代码一起发布
  2. **用户预装**（``data/skills/<name>/manifest.yaml`` + ``handler.py``）—— 用户/JEE 自行扩展
- 每个 skill 必须有一个 ``manifest.yaml``：
    ```yaml
    name: sensitive_word
    description: 过滤敏感词
    version: 1.0
    type: post_process      # pre_process | post_process
    triggers:
      - scene:plot_generation
      - scene:chapter_generation
      - all
    enabled: true
    ```
- 装载时机：服务启动时（``init_db()`` 之后调用 ``load_skills()``）。
- 注册表：合并 builtin + 用户预装 → 全局 ``registry``。

不在本文件做的事：
- 业务层调用 Skill —— 见 ``manager.py``（apply_post / augment_prompt）。
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .base import Skill
from .registry import registry

# Skill 加载顺序：builtin 先注册，用户预装可覆盖同 name。
USER_SKILLS_DIRNAME = "skills"
USER_SKILLS_ROOT: Path | None = None  # 运行时由 ``init_skill_paths`` 注入


def init_skill_paths(user_skills_dir: Path) -> None:
    """注入用户预装目录的绝对路径（在 lifespan startup 中调用）。"""
    global USER_SKILLS_ROOT
    USER_SKILLS_ROOT = user_skills_dir


def _load_builtin_skills() -> int:
    """从 ``server/src/core/skills/builtin/*.py`` 自动 ``import`` + ``register``。

    自动附加默认 trigger（见 ``BUILTIN_MANIFESTS``），让用户预装的 skill
    在常见 LLM 流式后被调用。
    """
    builtin_pkg = "src.core.skills.builtin"
    count = 0
    try:
        importlib.import_module(builtin_pkg)
    except ImportError as e:
        logger.warning("builtin skills package not available: {}", e)
        return 0
    pkg = sys.modules.get(builtin_pkg)
    if pkg is None:
        return 0
    # ⚠️ 包的 ``__path__`` 是**列表**（不是 str）——
    #    ``Path(list)`` 会抛 TypeError（2026-10-24 实测）。
    #    之前这里直接崩 → ``load_all_skills()`` 整个中断 →
    #    ``_load_user_skills()`` 根本没机会执行 →
    #    **用户在设置里自定义的 skill 一个都加载不了**（只有内置的还在，
    #    因为它们是在 ``skills/__init__.py`` 里显式注册的）。
    pkg_paths = list(getattr(pkg, "__path__", []) or [])
    if not pkg_paths:
        return 0
    pkg_path = Path(pkg_paths[0])
    for f in sorted(pkg_path.glob("*.py")):
        if f.name.startswith("_") or f.name == "__init__.py":
            continue
        mod_name = f"{builtin_pkg}.{f.stem}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to import builtin skill module {}: {}", mod_name, e)
            continue
        # 模块里找任何含 ``name`` + ``description`` + ``execute`` 的类
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ != mod_name:
                continue
            if not (hasattr(cls, "name") and hasattr(cls, "description")):
                continue
            if not hasattr(cls, "execute"):
                continue
            try:
                inst = cls()  # type: ignore[call-arg]
                # 附加默认 manifest
                inst._manifest = BUILTIN_MANIFESTS.get(  # type: ignore[attr-defined]
                    getattr(inst, "name", ""),
                    {"type": "post_process", "triggers": ["all"], "enabled": True},
                )
                registry.register(inst)  # type: ignore[arg-type]
                count += 1
                logger.debug("Loaded builtin skill: {}", getattr(inst, "name", "?"))
            except Exception as e:  # noqa: BLE001
                logger.error("Skill init failed {}: {}", cls.__name__, e)
    return count


# Builtin skill 的自动触发配置。
# triggers: 场景列表（"all" 或 "scene:<name>"）
# type 取值：post_process | pre_process | both
# enabled: 默认 True
BUILTIN_MANIFESTS: dict[str, dict[str, Any]] = {
    "sensitive_word": {
        "type": "post_process",
        "triggers": ["all"],  # 所有场景都过滤
        "enabled": True,
        "description": "检测 / 过滤敏感词（默认全场景自动调用）",
    },
    "word_counter": {
        "type": "post_process",
        "triggers": ["all"],
        "enabled": True,
        "description": "字数统计（仅供日志；不影响文本）",
    },
    "chapter_summarizer": {
        "type": "post_process",
        "triggers": ["scene:chapter_generation"],
        "enabled": True,
        "description": "章节正文生成后自动生成摘要",
    },
    "character_extractor": {
        "type": "post_process",
        "triggers": ["scene:outline_generation"],
        "enabled": False,  # 默认禁用（已有专门的 character_generation 流程）
    },
    "style_analyzer": {
        "type": "post_process",
        "triggers": [
            "scene:chapter_generation",
            "scene:chapter_rewrite",
            "scene:plot_generation",
        ],
        "enabled": False,
    },
    "consistency_checker": {
        "type": "post_process",
        "triggers": ["scene:chapter_generation", "scene:chapter_rewrite"],
        "enabled": False,
    },
    "pacing_visualizer": {
        "type": "post_process",
        "triggers": ["scene:chapter_generation"],
        "enabled": False,
    },
    "genre_classifier": {
        "type": "post_process",
        "triggers": ["scene:plot_generation"],
        "enabled": False,
    },
    "outline_structurer": {
        "type": "post_process",
        "triggers": ["scene:outline_generation"],
        "enabled": False,
    },
    "plot_analyzer": {
        "type": "post_process",
        "triggers": ["scene:plot_generation"],
        "enabled": False,
    },
    "read_local_file": {
        "type": "pre_process",
        "triggers": ["all"],
        "enabled": False,
    },
    "web_search": {
        "type": "pre_process",
        "triggers": ["all"],
        "enabled": False,
    },
}


def _load_user_skill_dir(skill_dir: Path) -> Skill | None:
    """从 ``<skill_dir>/manifest.yaml`` + ``handler.py`` 装载一个用户 skill。"""
    manifest_path = skill_dir / "manifest.yaml"
    handler_path = skill_dir / "handler.py"
    if not manifest_path.is_file() or not handler_path.is_file():
        return None
    try:
        manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        logger.error("Invalid manifest yaml at {}: {}", manifest_path, e)
        return None
    if not isinstance(manifest_data, dict):
        logger.error("Manifest root must be a dict, got {}", type(manifest_data).__name__)
        return None

    name = str(manifest_data.get("name", "")).strip()
    if not name:
        logger.error("Manifest missing 'name': {}", manifest_path)
        return None
    description = str(manifest_data.get("description", "")).strip()

    spec = importlib.util.spec_from_file_location(
        f"skill_user.{name}",
        handler_path,
    )
    if spec is None or spec.loader is None:
        logger.error("Failed to build module spec for {}", handler_path)
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to exec handler {}: {}", handler_path, e)
        return None

    # 期望：handler.py 定义一个 ``create_skill() -> Skill`` 工厂，或一个 ``Skill`` 实例
    skill_obj: Skill | None = None
    if hasattr(module, "create_skill"):
        try:
            skill_obj = module.create_skill()  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            logger.error("create_skill() failed in {}: {}", handler_path, e)
            return None
    else:
        # 回退：找模块里任何一个有 name/description/execute 的类
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if hasattr(cls, "execute") and hasattr(cls, "name"):
                try:
                    skill_obj = cls()  # type: ignore[call-arg]
                    break
                except Exception:  # noqa: BLE001
                    continue

    if skill_obj is None:
        logger.error("No Skill instance produced by {}", handler_path)
        return None

    # 把 manifest 元数据 attach 到 skill（manager 读取 triggers / type / enabled）
    skill_obj._manifest = manifest_data  # type: ignore[attr-defined]
    # 若 handler 没设 description，用 manifest 的补上
    if not getattr(skill_obj, "description", ""):
        skill_obj.description = description  # type: ignore[attr-defined]
    return skill_obj


def _load_user_skills() -> int:
    """扫描 ``data/skills/*/manifest.yaml`` 注册用户预装 skill。"""
    if USER_SKILLS_ROOT is None or not USER_SKILLS_ROOT.is_dir():
        return 0
    count = 0
    for skill_dir in sorted(USER_SKILLS_ROOT.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill = _load_user_skill_dir(skill_dir)
        if skill is None:
            continue
        try:
            registry.register(skill)
            count += 1
            logger.debug("Loaded user skill: {} from {}", skill.name, skill_dir)
        except Exception as e:  # noqa: BLE001
            logger.error("Register user skill failed ({}): {}", skill_dir, e)
    return count


def load_all_skills() -> int:
    """加载所有 skill（builtin + 用户预装），返回注册数。

    幂等：重复调用会覆盖同名（registry 已有 warn）。
    """
    n_builtin = _load_builtin_skills()
    n_user = _load_user_skills()
    total = n_builtin + n_user
    logger.info("Skills loaded: {} (builtin={}, user={})", total, n_builtin, n_user)
    return total


__all__ = [
    "USER_SKILLS_DIRNAME",
    "init_skill_paths",
    "load_all_skills",
]
