"""网络搜索 Skill（Phase 7.1 + 升级版）。

v2 升级：接入 SerpAPI（https://serpapi.com/）。
- 免费 100 次/月，付费起 $50/月
- 支持 web search / news / scholar 等多种引擎

配置：
    API key 存系统 keyring（参考 LLM provider 设计）
    或通过 .env: SERPAPI_KEY=xxx

v1 占位（无 API key）→ 失败并返回提示。
"""

from __future__ import annotations

import os

import httpx

from ..base import SkillResult

SERPAPI_BASE = "https://serpapi.com/search.json"


class WebSearchSkill:
    name = "web_search"
    description = "网络搜索（SerpAPI；需配置 SERPAPI_KEY）"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "返回前 N 条（默认 5）"},
            "engine": {
                "type": "string",
                "description": "搜索引擎（google / bing / duckduckgo 等，默认 google）",
            },
        },
        "required": ["query"],
    }
    requires_llm = False

    async def execute(
        self, query: str, limit: int = 5, engine: str = "google"
    ) -> SkillResult:
        if not isinstance(query, str) or not query.strip():
            return SkillResult(success=False, error="query is required")

        # 取 API key（环境变量优先，其次 .env）
        api_key = os.environ.get("SERPAPI_KEY", "")
        if not api_key:
            return SkillResult(
                success=False,
                error=(
                    "web_search 未启用：请在系统环境变量或 .env 中设置 SERPAPI_KEY\n"
                    "（注册 https://serpapi.com/ 获取免费 key）"
                ),
            )

        limit = max(1, min(20, int(limit or 5)))

        params = {
            "q": query,
            "api_key": api_key,
            "engine": engine or "google",
            "num": limit,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(SERPAPI_BASE, params=params)
        except httpx.HTTPError as e:
            return SkillResult(success=False, error=f"HTTP error: {e}")
        if resp.status_code != 200:
            return SkillResult(
                success=False, error=f"SerpAPI HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        # SerpAPI organic_results 字段是搜索结果列表
        results_raw = data.get("organic_results", []) or []
        results: list[dict] = []
        for r in results_raw[:limit]:
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", ""),
                    "position": r.get("position"),
                }
            )
        return SkillResult(
            success=True,
            data={
                "query": query,
                "engine": engine or "google",
                "count": len(results),
                "results": results,
            },
        )


__all__ = ["WebSearchSkill"]
