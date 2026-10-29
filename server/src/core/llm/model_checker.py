"""模型能力校验。

规则（来自 AGENTS.md 安全规范 + JEE 决策）：
- context_window 必须 >= 32k 才能生成章节（容纳 prompt + 历史 + 8k 字输出）
- max_output_tokens 至少要 >= max_chars/2（防止一次输出截断到一半章节）

输出 ModelCheckResult，UI 据此弹红框/黄框。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .factory import get_provider_config, load_llm_config


@dataclass
class ModelWarning:
    level: str  # 'error' | 'warning' | 'info'
    message: str


@dataclass
class ModelCheckResult:
    provider: str
    model: str
    context_window: int
    max_output_tokens: int
    quality_tier: str
    warnings: list[ModelWarning] = field(default_factory=list)
    can_generate_chapter: bool = False


def _get_chapter_limits() -> tuple[int, int, int]:
    """从 llm.yaml 读章节硬限 + 最小 context。"""
    cfg = load_llm_config()
    cl = cfg.get("chapter_limits") or {}
    return (
        int(cl.get("min_chars", 1000)),
        int(cl.get("max_chars", 8000)),
        int(cl.get("min_context_needed", 32000)),
    )


def check_model_capability(
    provider: str,
    model: str,
) -> ModelCheckResult:
    """检查指定 provider/model 是否支持章节生成。

    模型没在 ``llm.yaml`` 登记规格时**不抛错** —— 用户可以自己填服务端
    新出的模型名（项目要求"能自行更换模型"）。这时按 provider 级
    ``default_context_window`` / ``default_max_output_tokens`` 估算能力，
    并给一条 info 级别的提示。

    :raises KeyError: provider 不存在时
    """
    pc = get_provider_config(provider)
    specs = pc.get("model_specs") or {}
    spec_raw = specs.get(model)
    known = isinstance(spec_raw, dict)
    # mypy 不会通过布尔变量 ``known`` 收窄 ``spec_raw``，这里显式再判一次 isinstance：
    # 语义与原实现完全一致 —— 非 dict（含 None / 脏值）一律退化成空 dict。
    spec: dict[str, Any] = spec_raw if isinstance(spec_raw, dict) else {}

    context_window = int(spec.get("context_window", pc.get("default_context_window", 0)) or 0)
    max_output = int(spec.get("max_output_tokens", pc.get("default_max_output_tokens", 0)) or 0)
    quality_tier = str(spec.get("quality_tier", "unknown"))

    min_chars, max_chars, min_context = _get_chapter_limits()
    # 粗略估计：中文 1 字 ≈ 1.5-2 tokens，章节 8k 字 ≈ 16k tokens
    max_chars_tokens = max_chars * 2

    warnings: list[ModelWarning] = []

    if not known:
        warnings.append(
            ModelWarning(
                level="info",
                message=(
                    f"模型 {model} 未在 config/llm.yaml 登记规格，"
                    f"能力按 provider 默认值估算（上下文 {context_window} tokens）"
                ),
            )
        )

    if context_window <= 0:
        warnings.append(
            ModelWarning(
                level="error",
                message=f"模型 {model} 未声明 context_window，无法生成章节",
            )
        )
    elif context_window < min_context:
        warnings.append(
            ModelWarning(
                level="error",
                message=(
                    f"模型 {model} 上下文仅 {context_window} tokens，"
                    f"无法支持 {min_chars}-{max_chars} 字章节生成（最低需要 {min_context}）"
                ),
            )
        )

    if max_output > 0 and max_output < max_chars_tokens:
        warnings.append(
            ModelWarning(
                level="warning",
                message=(
                    f"模型 {model} 最大输出 {max_output} tokens，{max_chars} 字章节可能需分多次生成"
                ),
            )
        )

    can_generate = context_window >= min_context and max_output >= max_chars_tokens // 2

    return ModelCheckResult(
        provider=provider,
        model=model,
        context_window=context_window,
        max_output_tokens=max_output,
        quality_tier=quality_tier,
        warnings=warnings,
        can_generate_chapter=can_generate,
    )
