"""敏感词检测 Skill（Phase 6.4）。

默认内置一份常用敏感词列表（政治/暴力/色情/赌博/毒品相关）。
生产环境应该接词库服务或在线 API（v2 升级）。
"""

from __future__ import annotations

from ..base import SkillResult

# v1 内置词表（最小集）
DEFAULT_SENSITIVE_WORDS: tuple[str, ...] = (
    # 色情
    "色情",
    "裸聊",
    "约炮",
    "一夜情",
    "卖淫",
    "嫖娼",
    # 赌博
    "赌博",
    "赌场",
    "百家乐",
    "澳门威尼斯",
    "网赌",
    # 毒品
    "毒品",
    "海洛因",
    "冰毒",
    "大麻",
    "可卡因",
    # 暴力
    "炸弹制作",
    "制毒方法",
    "自杀方法",
    # 政治（示例）
    "法轮功",
    "台独",
    "港独",
)


class SensitiveWordSkill:
    name = "sensitive_word"
    description = "检测文本中是否含敏感词"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要检测的文本"},
            "words": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选：自定义词表（覆盖默认）",
            },
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, text: str, words: list[str] | None = None) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        word_list = tuple(words) if words else DEFAULT_SENSITIVE_WORDS
        if not text:
            return SkillResult(
                success=True,
                data={"has_sensitive": False, "matches": [], "checked": len(word_list)},
            )

        matches: list[dict[str, int]] = []
        for w in word_list:
            if not w:
                continue
            start = 0
            while True:
                idx = text.find(w, start)
                if idx == -1:
                    break
                matches.append({"word": w, "position": idx})
                start = idx + len(w)

        return SkillResult(
            success=True,
            data={
                "has_sensitive": len(matches) > 0,
                "match_count": len(matches),
                "matches": matches,
                "checked": len(word_list),
            },
        )


__all__ = ["SensitiveWordSkill", "DEFAULT_SENSITIVE_WORDS"]
