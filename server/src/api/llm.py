"""LLM 测试端点（Phase 0 模块 0.10）。

端到端验证用：
- 前端调 Tauri Cmd "test_llm"
- Rust 端代理到此 HTTP 端点
- 此端点调真实 LLM 返回结果
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.llm import (
    AuthError,
    ChatMessage,
    LLMError,
    RateLimitError,
    create_llm_client,
)

router = APIRouter(tags=["llm"])


class TestLLMRequest(BaseModel):
    """测试 LLM 请求体。"""

    prompt: str = Field(
        default="用一句话介绍你自己",
        description="用户提示词",
    )
    provider: str | None = Field(
        default=None,
        description="provider 名（None 用 default_provider）",
    )
    system: str | None = Field(
        default=None,
        description="系统提示词（None 用默认）",
    )
    max_tokens: int = Field(default=200, ge=1, le=8000)


# 默认系统提示（system 字段为 None 时使用）
_DEFAULT_SYSTEM = "You are a concise assistant. Reply in Chinese."


class TestLLMResponse(BaseModel):
    """测试 LLM 响应体。"""

    provider: str
    model: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@router.post("/llm/test", response_model=TestLLMResponse)
async def test_llm(req: TestLLMRequest) -> TestLLMResponse:
    """测试 LLM 调用（不写库，单纯验证通联）。"""
    # 允许在测试环境跳过真实调用（CI 用）
    if os.environ.get("BOOK_SOUL_SKIP_LLM") == "1":
        return TestLLMResponse(
            provider=req.provider or "mimo",
            model="stub-model",
            content=f"[stubbed] echo: {req.prompt}",
            prompt_tokens=len(req.prompt),
            completion_tokens=20,
            total_tokens=len(req.prompt) + 20,
        )

    try:
        client = create_llm_client(req.provider)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {e}") from e
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    system_msg = req.system if req.system else _DEFAULT_SYSTEM
    try:
        resp = await client.chat(
            [
                ChatMessage(role="system", content=system_msg),
                ChatMessage(role="user", content=req.prompt),
            ],
            max_tokens=req.max_tokens,
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        await client.aclose()

    return TestLLMResponse(
        provider=client.provider,
        model=resp.model,
        content=resp.content,
        prompt_tokens=resp.usage.prompt_tokens,
        completion_tokens=resp.usage.completion_tokens,
        total_tokens=resp.usage.total_tokens,
    )
