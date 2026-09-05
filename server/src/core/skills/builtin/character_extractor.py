"""角色抽取 Skill（Phase 7.1，启发式 v1）。

无 LLM：基于"X 说：" / "X 道：" / "X 心想" 模式 + 名字出现频次。
v2 升级：可调 LLM 做 NER 抽取。
"""

from __future__ import annotations

import re
from collections import Counter

from ..base import SkillResult

_DIALOG_PATTERNS = [
    re.compile(r"([\u4e00-\u9fff]{2,4})(?:说|道|喊|叫|笑|叹|问|答|心想|暗想)"),
    re.compile(r"([\u4e00-\u9fff]{2,4})(?:听|看|望|走|跑|想|笑|哭)"),
]


class CharacterExtractorSkill:
    name = "character_extractor"
    description = "启发式抽取章节中可能的角色名（基于对话/动作模式 + 频次）"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "章节正文"},
            "top_n": {"type": "integer", "description": "返回前 N 个（默认 10）"},
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, text: str, top_n: int = 10) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        if not text.strip():
            return SkillResult(success=True, data={"characters": [], "total_candidates": 0})

        counts: Counter[str] = Counter()
        for pat in _DIALOG_PATTERNS:
            for m in pat.finditer(text):
                name = m.group(1)
                counts[name] += 1
        # 过滤：只在文本中出现 ≥2 次的名字（去掉一次性提及）
        filtered = Counter({n: c for n, c in counts.items() if c >= 2})
        top = filtered.most_common(top_n)
        return SkillResult(
            success=True,
            data={
                "characters": [{"name": n, "mentions": c} for n, c in top],
                "total_candidates": len(counts),
            },
        )


__all__ = ["CharacterExtractorSkill"]
