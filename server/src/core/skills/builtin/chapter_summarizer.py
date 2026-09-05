"""章节摘要 Skill（Phase 7.1，启发式 v1）。

无 LLM：用首段 + 中间采样 + 尾段拼成粗略摘要。
v2 升级：可调 LLM 生成更智能摘要。
"""

from __future__ import annotations

from ..base import SkillResult


class ChapterSummarizerSkill:
    name = "chapter_summarizer"
    description = "提取章节粗略摘要（首段 + 末段 + 中段采样）"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "章节正文"},
            "head_chars": {"type": "integer", "description": "首段保留字符数（默认 200）"},
            "tail_chars": {"type": "integer", "description": "末段保留字符数（默认 200）"},
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(
        self,
        text: str,
        head_chars: int = 200,
        tail_chars: int = 200,
    ) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        if not text.strip():
            return SkillResult(success=True, data={"summary": "", "total_chars": 0})

        head = text[:head_chars]
        # 取中段（如有）
        mid = ""
        if len(text) > head_chars + tail_chars:
            mid_start = len(text) // 2 - 50
            mid_end = mid_start + 100
            if mid_start > head_chars and mid_end < len(text) - tail_chars:
                mid = text[mid_start:mid_end]
        tail = text[-tail_chars:] if len(text) > head_chars else ""

        parts = [head]
        if mid:
            parts.append(f"\n[...]\n{mid}\n[...]\n")
        if tail:
            parts.append(tail)
        summary = "".join(parts).strip()
        return SkillResult(
            success=True,
            data={
                "summary": summary,
                "total_chars": len(text),
                "summary_chars": len(summary),
                "head_chars": len(head),
                "tail_chars": len(tail) if tail else 0,
            },
        )


__all__ = ["ChapterSummarizerSkill"]
