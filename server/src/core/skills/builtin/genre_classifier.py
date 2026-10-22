"""题材分类 Skill（Phase 7.1，启发式 v1）。

无 LLM：基于关键词命中数判定题材（修仙/都市/悬疑/言情）。
v2 升级：可调 LLM 做精确分类。
"""

from __future__ import annotations

from ..base import SkillResult

GENRE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "修仙": ("修仙", "灵气", "灵根", "飞升", "金丹", "筑基", "元婴", "渡劫", "宗门", "功法"),
    "都市": ("公司", "总裁", "豪门", "商场", "职场", "校园", "同学", "都市", "写字楼"),
    "悬疑": ("案件", "凶手", "线索", "嫌疑", "探案", "推理", "死者", "警方", "密室"),
    "言情": ("爱情", "恋人", "心动", "告白", "分手", "前任", "相思", "心碎", "甜蜜"),
    "科幻": ("飞船", "外星", "太空", "机器人", "AI", "未来", "时间旅行", "量子"),
    "玄幻": ("斗气", "魔法", "异界", "召唤", "魔兽", "勇者", "剑士"),
    "历史": ("朝代", "皇帝", "大臣", "边疆", "战乱", "科举", "宫廷"),
    "军事": ("连长", "团长", "营长", "作战", "部队", "演习", "战术", "战略"),
}


class GenreClassifierSkill:
    name = "genre_classifier"
    description = "启发式题材分类（基于关键词命中）"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "小说文本（任意长度）"},
            "top_n": {"type": "integer", "description": "返回前 N 个候选（默认 3）"},
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, text: str, top_n: int = 3) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        if not text.strip():
            return SkillResult(success=True, data={"candidates": [], "char_count": 0})

        scores: list[tuple[str, int, list[str]]] = []
        for genre, words in GENRE_KEYWORDS.items():
            hits = [w for w in words if w in text]
            if hits:
                scores.append((genre, len(hits), hits))
        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:top_n]

        return SkillResult(
            success=True,
            data={
                "candidates": [{"genre": g, "score": s, "matched_keywords": k} for g, s, k in top],
                "char_count": len(text),
            },
        )


__all__ = ["GenreClassifierSkill"]
