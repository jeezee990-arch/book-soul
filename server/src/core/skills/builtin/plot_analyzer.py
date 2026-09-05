"""剧情分析 Skill（Phase 7.1，启发式 v1）。

无 LLM：扫描"关键事件关键词"密度（突然/决定/发现/危机/胜利等），给出分布。
v2 升级：可调 LLM 做事件抽取。
"""

from __future__ import annotations

import re

from ..base import SkillResult

# 关键事件关键词（按权重）
KEYWORD_GROUPS: dict[str, list[str]] = {
    "突转": ["突然", "忽然", "猛然", "骤然", "瞬间", "刹那"],
    "决定": ["决定", "下定决心", "下定决心", "决意", "下定决心"],
    "发现": ["发现", "看出", "察觉", "意识到", "明白了", "恍然大悟"],
    "危机": ["危险", "危机", "威胁", "危在旦夕", "生死", "陷阱"],
    "胜利": ["胜利", "成功", "大获全胜", "击退", "击败", "斩杀"],
    "冲突": ["冲突", "争吵", "冲突", "对峙", "厮杀", "激战"],
    "情感": ["爱", "恨", "悲", "喜", "怒", "哀", "思念", "牵挂"],
}


class PlotAnalyzerSkill:
    name = "plot_analyzer"
    description = "启发式剧情分析（关键事件关键词密度）"
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
            return SkillResult(success=True, data={"groups": {}, "total_events": 0})

        groups: dict[str, list[dict[str, int | str]]] = {}
        total = 0
        for group, words in KEYWORD_GROUPS.items():
            events: list[dict[str, int | str]] = []
            for word in words:
                pat = re.compile(re.escape(word))
                positions = [m.start() for m in pat.finditer(text)]
                if positions:
                    events.append({"keyword": word, "count": len(positions)})
                    total += len(positions)
            if events:
                groups[group] = events

        return SkillResult(
            success=True,
            data={
                "groups": groups,
                "total_events": total,
                "char_count": len(text),
            },
        )


__all__ = ["PlotAnalyzerSkill"]
