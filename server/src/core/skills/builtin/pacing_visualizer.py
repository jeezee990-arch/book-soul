"""节奏可视化 Skill（Phase 7.1，启发式 v1）。

无 LLM：把章节按段切分，统计每段长度（字数）作为节奏数据。
v2 升级：可调 LLM 标注"紧张/舒缓"标签叠加到数据上。
"""

from __future__ import annotations

from typing import Any, cast

from ..base import SkillResult


class PacingVisualizerSkill:
    name = "pacing_visualizer"
    description = "按段统计字数，输出节奏数据（前端可绘制曲线）"
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
            return SkillResult(success=True, data={"segments": [], "total_segments": 0})

        # 按 \n\n 切段
        raw = text.split("\n\n")
        segments: list[dict[str, Any]] = [
            {"index": idx, "char_count": len(p), "preview": p[:50]}
            for idx, p in enumerate(raw)
            if p.strip()
        ]
        char_counts: list[int] = [cast(int, s["char_count"]) for s in segments]
        total = sum(char_counts)
        return SkillResult(
            success=True,
            data={
                "segments": segments,
                "total_segments": len(segments),
                "total_chars": total,
                "avg_chars": round(total / len(segments), 2) if segments else 0,
                "min_chars": min(char_counts) if char_counts else 0,
                "max_chars": max(char_counts) if char_counts else 0,
            },
        )


__all__ = ["PacingVisualizerSkill"]
