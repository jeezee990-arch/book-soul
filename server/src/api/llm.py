"""LLM 测试端点（Phase 0 模块 0.10）。

端到端验证用：
- 前端调 Tauri Cmd "test_llm"
- Rust 端代理到此 HTTP 端点
- 此端点调真实 LLM 返回结果
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.llm import (
    AuthError,
    ChatMessage,
    LLMError,
    RateLimitError,
    create_llm_client,
)
from ..core.llm import cache as llm_cache
from ..core.llm.factory import get_provider_config

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


@router.get("/llm/health")
async def llm_health(
    provider: str | None = Query(None, description="只探活这一个 provider"),
) -> dict:
    """探活 provider（设置页 / 顶栏模型灯用）。

    返回 ``{provider: {"ok": bool, "message": str}}``。

    ⚠️ 走缓存（``core/llm/cache.py``）：这个端点会被前端在启动时调用，
    实时探测要等外部网络（可达性差时 ~3 秒），会把顶栏模型灯卡成"转圈"。
    缓存命中时是 0 延迟，过期时先返回旧值再后台刷新。

    ⚠️ **带 provider 参数时只探这一个**（顶栏灯用）：

    灯只关心"当前生效的那个 provider"。如果每次都探全部 provider，
    那么"用户用 mimo，但没配的 openai / 没启动的 ollama 不可达"就会
    让灯白等 3 秒 —— 那 3 秒对灯毫无意义。
    不带参数 = 探全部（启动预检用，后台跑，不阻塞任何人）。
    """
    providers = [provider] if provider else None
    results = await llm_cache.get_health(providers)
    return {name: {"ok": ok, "message": message} for name, (ok, message) in results.items()}


@router.get("/llm/models")
async def llm_models(
    provider: str = Query(..., description="provider name"),
    refresh: bool = Query(False, description="忽略缓存强制重新拉取"),
) -> dict:
    """列出某个 provider 支持的模型（设置页下拉框用）。

    实时从 provider 的 ``/models`` 端点拉取 —— 服务端下线模型后，
    设置页立刻能反映出来，不会再出现"配了个服务端不认的模型名"的 400。

    返回字段：
    - ``models``：实时列表 ∪ 配置登记列表（前端下拉框用这个）
    - ``live_models``：服务端实时支持的
    - ``configured_models``：``config/llm.yaml`` 登记的
    - ``default_model``：该 provider 的默认模型
    - ``reachable`` / ``message``：连通性

    ⚠️ 带缓存（``core/llm/cache.py``）：设置页每次打开都会调，
    实时拉取在网络差时要等好几秒。``?refresh=1`` 强制绕过缓存
    （对应前端「刷新列表」按钮）。
    """
    try:
        get_provider_config(provider)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await llm_cache.get_models(provider, force=refresh)
