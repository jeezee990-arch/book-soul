"""文风分析 Skill（Phase 7.1，启发式 v1）。

无 LLM：计算基础指标（句长均值、感叹号密度、对话占比、段落数）。
v2 升级：可调 LLM 做更精细的文风评估。
"""

from __future__ import annotations

import re

from ..base import SkillResult

_SENT_END = re.compile(r"[。！？!?\.]+")
_DIALOG = re.compile(r"[「『\"].*?[」』\"]", re.DOTALL)


class StyleAnalyzerSkill:
    name = "style_analyzer"
    description = "启发式文风分析（句长、感叹号、对话占比等基础指标）"
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
            return SkillResult(success=True, data={"char_count": 0})

        char_count = len(text)
        # 句数
        sentences = [s for s in _SENT_END.split(text) if s.strip()]
        sentence_count = len(sentences)
        avg_sentence_len = round(char_count / sentence_count, 2) if sentence_count else 0
        # 感叹号密度
        excl = text.count("!") + text.count("！")
        excl_density = round(excl / max(char_count, 1) * 1000, 3)  # 每 1000 字
        # 问号密度
        qm = text.count("?") + text.count("？")
        qm_density = round(qm / max(char_count, 1) * 1000, 3)
        # 对话占比
        dialog_chars = sum(len(m.group(0)) for m in _DIALOG.finditer(text))
        dialog_ratio = round(dialog_chars / max(char_count, 1), 4)
        # 段落
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        paragraph_count = len(paragraphs)
        avg_paragraph_len = round(char_count / paragraph_count, 2) if paragraph_count else 0

        return SkillResult(
            success=True,
            data={
                "char_count": char_count,
                "sentence_count": sentence_count,
                "avg_sentence_len": avg_sentence_len,
                "paragraph_count": paragraph_count,
                "avg_paragraph_len": avg_paragraph_len,
                "exclamation_density": excl_density,
                "question_density": qm_density,
                "dialog_ratio": dialog_ratio,
            },
        )


__all__ = ["StyleAnalyzerSkill"]
