"""Quality prompt 加载 + 上下文格式化（Phase 5.2/5.3/5.4）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ...models.character import Character


def _find_repo_root() -> Path:
    """向上找项目根：包含 ``config/`` + ``pyproject.toml``。"""
    p = Path(__file__).resolve().parent
    for _ in range(8):
        if (p / "config").is_dir() and (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    return Path(__file__).resolve().parents[6]


_PROMPTS_DIR = _find_repo_root() / "config" / "prompts"
_GENRES_DIR = _find_repo_root() / "config" / "genres"


class QualityPromptError(Exception):
    """加载 prompt / 题材规则时出错。"""


# 5 个维度的 prompt 字段名（与 yaml 里 key 对应）
QUALITY_DIMENSIONS: tuple[str, ...] = (
    "writing",
    "logic",
    "pacing",
    "consistency",
    "genre",
)


@lru_cache(maxsize=8)
def load_quality_prompt(dimension: str) -> str:
    """加载 ``config/prompts/quality_{dimension}.yaml`` 的 ``quality_{dimension}`` 字段。"""
    if dimension not in QUALITY_DIMENSIONS:
        raise QualityPromptError(f"Unknown dimension: {dimension!r}")
    path = _PROMPTS_DIR / f"quality_{dimension}.yaml"
    if not path.is_file():
        raise QualityPromptError(f"Quality prompt not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    key = f"quality_{dimension}"
    if not isinstance(data, dict) or key not in data:
        raise QualityPromptError(f"Quality prompt {path} missing '{key}' field")
    return str(data[key])


def format_characters_for_quality(characters: list[Character]) -> str:
    """人物卡列表 → prompt 块（人设一致性维度用）。"""
    if not characters:
        return "（暂无人物卡；本章人设一致性无法检查）"
    parts: list[str] = []
    for c in characters:
        info_lines: list[str] = []
        for label, field in (
            ("身份", c.basic_info),
            ("性格", c.personality),
            ("习惯", c.habits),
            ("思维", c.thinking),
            ("关系", c.relationships),
            ("成长", c.growth_arc),
        ):
            if field:
                info_lines.append(f"  - {label}：{field}")
        body = "\n".join(info_lines) if info_lines else "  - （无详细字段）"
        parts.append(f"### {c.name}（{c.role}）\n{body}")
    return "\n\n".join(parts)


def load_genre_rules(genre: str) -> str:
    """加载 ``config/genres/{genre}.yaml`` 全部内容（题材合规性维度用）。"""
    if not genre:
        return "（未指定题材）"
    path = _GENRES_DIR / f"{genre.lower()}.yaml"
    if not path.is_file():
        return f"（题材 {genre!r} 暂无常识库文件）"
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001
        return f"（加载题材 {genre} 常识库失败：{e}）"
    # 渲染为可读文本
    return _yaml_to_text(data)


def _yaml_to_text(data: Any, indent: int = 0) -> str:
    """简单 yaml → 文本渲染（不解析 markdown，只列字段）。"""
    if isinstance(data, dict):
        lines = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{'  ' * indent}{k}:")
                lines.append(_yaml_to_text(v, indent + 1))
            else:
                lines.append(f"{'  ' * indent}{k}: {v}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{'  ' * indent}-")
                lines.append(_yaml_to_text(item, indent + 1))
            else:
                lines.append(f"{'  ' * indent}- {item}")
        return "\n".join(lines)
    return f"{'  ' * indent}{data}"


__all__ = [
    "QUALITY_DIMENSIONS",
    "QualityPromptError",
    "load_quality_prompt",
    "format_characters_for_quality",
    "load_genre_rules",
]
