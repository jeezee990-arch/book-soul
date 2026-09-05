"""一致性检查 Skill（Phase 7.1，启发式 v1）。

无 LLM：检查文本中同一名字的多种写法（前后不一致）。
v2 升级：可调 LLM 做完整一致性分析。
"""

from __future__ import annotations

from ..base import SkillResult

# 简单别名：常见"同物不同名"（中英 / 繁简）
COMMON_ALIASES: dict[str, tuple[str, ...]] = {
    "主角": ("主角", "主人公", "男主", "女主"),
    "师父": ("师父", "师傅", "老师", "师尊"),
    "法宝": ("法宝", "灵宝", "法器", "宝物"),
}


class ConsistencyCheckerSkill:
    name = "consistency_checker"
    description = "启发式一致性检查（名字别名 + 同一名字出现频次）"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "章节正文"},
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, text: str) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        if not text.strip():
            return SkillResult(success=True, data={"issues": [], "checked_chars": 0})

        # 检查常见别名：同一 group 内多种说法同时出现
        issues: list[dict[str, object]] = []
        for canonical, aliases in COMMON_ALIASES.items():
            present: list[tuple[str, int]] = []
            for alias in aliases:
                count = text.count(alias)
                if count > 0:
                    present.append((alias, count))
            if len(present) >= 2:
                # 至少 2 个不同别名都出现 → 提示用户确认
                issues.append(
                    {
                        "type": "alias_variation",
                        "canonical": canonical,
                        "found": [{"name": n, "count": c} for n, c in present],
                        "suggestion": f"建议统一使用「{canonical}」或保留区分",
                    }
                )

        return SkillResult(
            success=True,
            data={"issues": issues, "checked_chars": len(text)},
        )


__all__ = ["ConsistencyCheckerSkill"]
