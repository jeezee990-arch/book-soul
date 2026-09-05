"""网络搜索 Skill（Phase 7.1 占位）。

需要联网 + 搜索 API key。当前 v1 返回明确错误，提示用户配置。
v2 升级：接 Google Custom Search / Bing Search / SerpAPI。
"""

from __future__ import annotations

from ..base import SkillResult


class WebSearchSkill:
    name = "web_search"
    description = "网络搜索（占位：需配置 API key；当前返回错误）"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "返回前 N 条（默认 5）"},
        },
        "required": ["query"],
    }
    requires_llm = False

    async def execute(self, query: str, limit: int = 5) -> SkillResult:
        if not isinstance(query, str) or not query.strip():
            return SkillResult(success=False, error="query is required")
        return SkillResult(
            success=False,
            error=(
                "web_search skill 未启用：请在 server 端配置搜索 API key "
                "（如 Google CSE / SerpAPI），并在 src/core/skills/builtin/web_search.py 接入"
            ),
        )


__all__ = ["WebSearchSkill"]
