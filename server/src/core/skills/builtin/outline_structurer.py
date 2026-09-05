"""大纲结构化 Skill（Phase 7.1，启发式 v1）。

无 LLM：把自由文本大纲按行解析为结构（chapter / volume / key_event）。
v2 升级：可调 LLM 提取结构。
"""

from __future__ import annotations

import re

from ..base import SkillResult

_VOL_PATTERNS = [
    re.compile(r"^第\s*([一二三四五六七八九十百千万\d]+)\s*卷\s*[：:、]?\s*(.*)$"),
]
_CH_PATTERNS = [
    re.compile(r"^第\s*([一二三四五六七八九十百千万\d]+)\s*章\s*[：:、]?\s*(.*)$"),
    re.compile(r"^Chapter\s*(\d+)\s*[：:、]?\s*(.*)$", re.IGNORECASE),
]
_EVENT_PATTERNS = [
    re.compile(r"^[-*•·]\s*(.+)$"),
    re.compile(r"^\d+\.\s*(.+)$"),
]


class OutlineStructurerSkill:
    name = "outline_structurer"
    description = "启发式把自由文本大纲解析为结构（卷/章/事件）"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "自由文本大纲"},
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, text: str) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        if not text.strip():
            return SkillResult(success=True, data={"volumes": [], "orphan_chapters": []})

        volumes: list[dict] = []
        orphan_chapters: list[dict] = []
        current_vol: dict | None = None
        current_ch: dict | None = None

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            matched = False
            # 卷
            for pat in _VOL_PATTERNS:
                m = pat.match(stripped)
                if m:
                    current_vol = {"number": m.group(1), "title": m.group(2), "chapters": []}
                    volumes.append(current_vol)
                    current_ch = None
                    matched = True
                    break
            if matched:
                continue
            # 章
            for pat in _CH_PATTERNS:
                m = pat.match(stripped)
                if m:
                    current_ch = {
                        "number": m.group(1),
                        "title": m.group(2),
                        "events": [],
                    }
                    if current_vol is not None:
                        current_vol["chapters"].append(current_ch)
                    else:
                        orphan_chapters.append(current_ch)
                    matched = True
                    break
            if matched:
                continue
            # 事件（"-" 或数字开头）
            for pat in _EVENT_PATTERNS:
                m = pat.match(stripped)
                if m:
                    if current_ch is not None:
                        current_ch["events"].append(m.group(1))
                    matched = True
                    break

        return SkillResult(
            success=True,
            data={
                "volumes": volumes,
                "orphan_chapters": orphan_chapters,
                "total_volumes": len(volumes),
                "total_chapters": sum(len(v["chapters"]) for v in volumes) + len(orphan_chapters),
            },
        )


__all__ = ["OutlineStructurerSkill"]
