"""OpenAI 兼容协议客户端（httpx 手写，不用 openai SDK）。

适用 provider：
- minimax（https://api.minimaxi.com/v1）
- OpenAI（https://api.openai.com/v1）
- 其他声明 type=openai_compat 的 provider

支持：
- 非流式 chat
- 流式 chat（OpenAI SSE 格式）
- 自动超时 + 重试（指数退避）
- 错误码到异常的映射（401/403/404/429/...）
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import (
    AuthError,
    ChatMessage,
    ChatResponse,
    ContextOverflowError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
    Usage,
)
from .streaming import extract_delta_text, iter_sse_chunks


class OpenAICompatClient:
    """OpenAI 兼容协议客户端。"""

    provider: str = "openai_compat"

    def __init__(self, config: dict[str, Any], api_key: str | None = None) -> None:
        self._base_url = config["base_url"].rstrip("/")
        self._api_key = api_key or self._resolve_api_key(config)
        self._default_model: str = config.get("default_model", "")
        # Phase 3.4 修：默认 60s 太长。海外节点正常 5-15s，30s 够。
        # 60s × 3 retry = 180s 远超 Rust 120s timeout，导致前端报 network error。
        self._timeout_s: float = float(config.get("timeout_seconds", 30))
        self._max_retries: int = int(config.get("max_retries", 2))
        self._provider_name: str = config.get("provider_name", "openai_compat")

        if not self._api_key:
            raise AuthError(
                f"Provider '{self._provider_name}' has empty API key "
                f"(set env var '{config.get('api_key_env', '')}' or pass api_key=)"
            )

        # 实例属性覆盖类属性：让业务层读到真实 provider 名（如 "mimo"）
        # 和默认模型名，而不是笼统的 "openai_compat" / 空
        self.provider = self._provider_name
        self.model = self._default_model

        # 复用 httpx.AsyncClient（连接池）
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout_s, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

    @staticmethod
    def _resolve_api_key(config: dict[str, Any]) -> str:
        env_var = config.get("api_key_env") or ""
        if not env_var:
            return ""
        return os.environ.get(env_var, "")

    async def aclose(self) -> None:
        await self._client.aclose()

    # ===================== chat =====================

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncIterator[str]:
        model_name = model or self._default_model
        if not model_name:
            raise ValueError("model is required (no default_model in config)")

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if stream:
            return self._stream_chat(payload)  # type: ignore[return-value]
        return await self._non_stream_chat(payload)

    # ===================== 非流式 =====================

    async def _non_stream_chat(self, payload: dict[str, Any]) -> ChatResponse:
        url = "/chat/completions"

        async def _do_request() -> ChatResponse:
            resp = await self._client.post(url, json=payload)
            self._raise_for_status(resp)
            data = resp.json()
            return self._parse_response(data)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            # Phase 3.4 修：加 httpx.TimeoutException 到 retry 列表
            # （原代码只 retry TransportError，timeout 不重试——和"minimax 慢"场景冲突）
            retry=retry_if_exception_type(
                (RateLimitError, httpx.TransportError, httpx.TimeoutException)
            ),
            reraise=True,
        ):
            with attempt:
                try:
                    return await _do_request()
                except (RateLimitError, httpx.TransportError) as e:
                    # 每次失败都记（str(e) 可能为空，至少留异常类型）
                    logger.warning(
                        "LLM request attempt {}/{} failed: {}",
                        attempt.retry_state.attempt_number,
                        self._max_retries,
                        str(e) or type(e).__name__,
                    )
                    raise

        # AsyncRetrying 不会走到这里，加个保险
        raise LLMError("Unexpected retry state")

    def _parse_response(self, data: dict[str, Any]) -> ChatResponse:
        choices = data.get("choices") or []
        content = ""
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content") or ""
        return ChatResponse(
            content=content,
            model=data.get("model", ""),
            usage=Usage.from_dict(data.get("usage")),
            raw=data,
        )

    # ===================== 流式 =====================

    async def _stream_chat(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        url = "/chat/completions"
        # 流式不做 tenacity 重试（避免重复输出）
        # 如果要重试，可以让外层包装一个简单的 retry
        resp = await self._client.post(url, json=payload)
        self._raise_for_status(resp)
        async for chunk in iter_sse_chunks(resp):
            text = extract_delta_text(chunk)
            if text:
                yield text

    # ===================== 错误映射 =====================

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        try:
            err_body = resp.json()
        except Exception:  # noqa: BLE001
            err_body = {"raw": resp.text[:500]}

        # Phase 3.4 修：minimax 偶尔返回空 body（status 4xx/5xx + 空 text），
        # 导致 `msg` 为空 → 后续 service 包成 "LLM call failed: " 没任何细节。
        # 修法：始终在 message 里包含 status code + body（哪怕空也标记 "(empty body)"）。
        body_msg = (
            (err_body.get("error") or {}).get("message")
            or err_body.get("raw", "")
            or "(empty body)"
        )
        msg = f"[HTTP {resp.status_code}] {body_msg[:300]}"
        if resp.status_code in (401, 403):
            raise AuthError(f"Auth failed {msg}")
        if resp.status_code == 404:
            raise ModelNotFoundError(f"Model not found: {msg}")
        if resp.status_code == 429:
            raise RateLimitError(f"Rate limited: {msg}")
        if resp.status_code == 413 or "context_length" in msg.lower():
            raise ContextOverflowError(f"Context overflow: {msg}")
        raise LLMError(f"LLM HTTP {msg}")


# 帮助在 except 链中临时 sleep（不直接 await asyncio.sleep 防止锁死）
async def _noop() -> None:
    await asyncio.sleep(0)
