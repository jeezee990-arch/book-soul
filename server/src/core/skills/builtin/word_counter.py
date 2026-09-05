"""字数统计 Skill（Phase 6.4）。

中英文混合：汉字 + 英文单词 + 数字
- chinese_chars: 中文字符数（0x4E00-0x9FFF）
- english_words: 英文单词数（用 split）
- numbers: 数字 token 数
- total: 加权总数（汉字 1 + 英文 1）
"""

from __future__ import annotations

from ..base import SkillResult


class WordCounterSkill:
    name = "word_counter"
    description = "统计文本字数（中英文混合）"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要统计的文本"},
        },
        "required": ["text"],
    }
    requires_llm = False

    async def execute(self, text: str) -> SkillResult:
        if not isinstance(text, str):
            return SkillResult(success=False, error="text must be a string")
        if not text:
            return SkillResult(
                success=True,
                data={
                    "chinese_chars": 0,
                    "english_words": 0,
                    "numbers": 0,
                    "total": 0,
                    "raw_chars": 0,
                },
            )

        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        # 简单英文/数字 token：split 后算 isascii 的词
        tokens = text.split()
        english_words = sum(1 for w in tokens if w.isascii() and any(c.isalpha() for c in w))
        numbers = sum(1 for w in tokens if w.isascii() and any(c.isdigit() for c in w) and not any(c.isalpha() for c in w))
        total = chinese + english_words
        return SkillResult(
            success=True,
            data={
                "chinese_chars": chinese,
                "english_words": english_words,
                "numbers": numbers,
                "total": total,
                "raw_chars": len(text),
            },
        )


__all__ = ["WordCounterSkill"]
