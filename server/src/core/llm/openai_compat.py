"""OpenAI 兼容协议客户端（httpx 手写，不用 openai SDK）。

适用 provider：
- minimax（https://api.minimaxi.com/v1）
- OpenAI（https://api.openai.com/v1）
- 其他声明 type=openai_compat 的 provider

支持：
- 非流式 chat
- 流式 chat（OpenAI SSE 格式）—— **必须用 client.stream()**
- 自动超时 + 重试（指数退避）
- 错误码到异常的映射（401/403/404/429/...）

⚠️ 流式实现的硬性要求（2026-10 修复）：
    httpx 的 ``client.post()`` 默认 ``stream=False``，会在返回前
    ``await response.aread()`` **把整个响应体读完**。
    如果用它做流式，后端会等模型生成完才把数据推给前端 —— 表现为
    "流式输出跟阻塞一样"。真正的流式必须用 ``client.stream()`` 上下文管理器。
    ``test_llm_streaming_contract.py`` 有契约测试锁住这个行为。
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
    ProviderUnavailableError,
    RateLimitError,
    Usage,
)
from .streaming import extract_delta_text, iter_sse_chunks

# 流式默认参数（可被 provider 配置覆盖）
DEFAULT_STREAM_READ_TIMEOUT = 120.0
DEFAULT_STREAM_TOTAL_TIMEOUT = 600.0
DEFAULT_TIMEOUT = 30.0
DEFAULT_CONNECT_TIMEOUT = 10.0


class OpenAICompatClient:
    """OpenAI 兼容协议客户端。"""

    provider: str = "openai_compat"

    def __init__(
        self,
        config: dict[str, Any],
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """创建客户端。

        :param config: provider 配置块（来自 config/llm.yaml）
        :param api_key: API key（None 时从 env 变量名解析）
        :param transport: httpx 传输层（测试注入 MockTransport 用）
        """
        self._base_url = config["base_url"].rstrip("/")
        self._api_key = api_key or self._resolve_api_key(config)
        self._default_model: str = config.get("default_model", "")

        # ===== 超时策略 =====
        # 非流式：整个响应的总等待上限（超过就失败）
        self._timeout_s: float = float(config.get("timeout_seconds", DEFAULT_TIMEOUT))
        # 流式：两个 chunk 之间的最大间隔（推理模型思考久也不会误杀）
        self._stream_read_timeout: float = float(
            config.get("stream_read_timeout", DEFAULT_STREAM_READ_TIMEOUT)
        )
        # 流式：整条流的总时长上限（防止对端挂死不释放连接）
        self._stream_total_timeout: float = float(
            config.get("stream_total_timeout", DEFAULT_STREAM_TOTAL_TIMEOUT)
        )
        self._max_retries: int = int(config.get("max_retries", 2))
        self._provider_name: str = config.get("provider_name", "openai_compat")

        # 模型规格表（max_output_tokens 等）—— 用于自动补 max_tokens
        self._model_specs: dict[str, Any] = config.get("model_specs") or {}

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
            timeout=httpx.Timeout(self._timeout_s, connect=DEFAULT_CONNECT_TIMEOUT),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    @staticmethod
    def _resolve_api_key(config: dict[str, Any]) -> str:
        env_var = config.get("api_key_env") or ""
        if not env_var:
            return ""
        return os.environ.get(env_var, "")

    async def aclose(self) -> None:
        await self._client.aclose()

    # ===================== max_tokens 自动填充 =====================

    def _resolve_max_tokens(self, model_name: str) -> int | None:
        """按 model_specs 里的 max_output_tokens 补 max_tokens。

        为什么需要：之前章节生成 / 大纲 / 剧情都**没传** max_tokens，
        完全依赖上游 API 的默认值（常见 1024 / 2048），长章节会被静默截断。

        显式传入的 max_tokens 优先，本函数只做兜底。
        """
        spec = self._model_specs.get(model_name)
        if not isinstance(spec, dict):
            return None
        value = spec.get("max_output_tokens")
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    # ===================== 不可达提示 =====================

    def _unavailable_hint(self, exc: BaseException) -> str:
        """生成"provider 连不上"的可操作提示。"""
        base = f"[{self._provider_name}] 无法连接到 {self._base_url}: {exc}"
        if self._provider_name == "ollama":
            return (
                f"{base}\n"
                "  提示：本地 Ollama 未启动。请先运行 `ollama serve`，"
                "并确认已拉取模型（`ollama pull qwen2.5:14b`）。"
            )
        return f"{base}\n  提示：请检查网络连通性、代理设置与 base_url 是否正确。"

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
        effective_max_tokens = (
            max_tokens if max_tokens is not None else (self._resolve_max_tokens(model_name))
        )
        if effective_max_tokens is not None:
            payload["max_tokens"] = effective_max_tokens

        if stream:
            return self._stream_chat(payload)  # type: ignore[return-value]
        return await self._non_stream_chat(payload)

    # ===================== 非流式 =====================

    async def _non_stream_chat(self, payload: dict[str, Any]) -> ChatResponse:
        url = "/chat/completions"

        async def _do_request() -> ChatResponse:
            try:
                resp = await self._client.post(url, json=payload)
            except httpx.ConnectError as e:
                raise ProviderUnavailableError(self._unavailable_hint(e)) from e
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
        """真流式：逐块 yield，不等模型生成完。

        ⚠️ 必须用 ``client.stream()``。用 ``client.post()`` 会让 httpx
        先把整个响应体读完再返回 —— 那样前端等 100 秒后瞬间刷出全文。
        """
        url = "/chat/completions"
        # 流式专用 timeout：read = 两个 chunk 的最大间隔（不设总时长上限，
        # 总时长由 asyncio.timeout 单独兜底），避免推理模型思考久被误杀
        stream_timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=self._stream_read_timeout,
            write=self._stream_read_timeout,
            pool=self._stream_read_timeout,
        )
        try:
            async with asyncio.timeout(self._stream_total_timeout):
                async with self._client.stream(
                    "POST", url, json=payload, timeout=stream_timeout
                ) as resp:
                    if resp.status_code >= 400:
                        # 错误分支：必须先把 body 读完才能拿到错误文本
                        await resp.aread()
                        self._raise_for_status(resp)
                    async for chunk in iter_sse_chunks(resp):
                        text = extract_delta_text(chunk)
                        if text:
                            yield text
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(self._unavailable_hint(e)) from e
        except TimeoutError as e:
            raise LLMError(
                f"LLM stream exceeded total timeout "
                f"({self._stream_total_timeout:.0f}s) for provider={self._provider_name}"
            ) from e
        except httpx.ReadTimeout as e:
            raise LLMError(
                f"LLM stream stalled: no data for {self._stream_read_timeout:.0f}s "
                f"(provider={self._provider_name})"
            ) from e

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
