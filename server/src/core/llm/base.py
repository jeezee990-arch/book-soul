"""LLM 抽象层基础类型。

设计：
- 自研 Protocol（不用 LangChain）
- ChatMessage/ChatResponse 用 dataclass（轻、零依赖）
- 异常分层：LLMError（基类）/ AuthError / RateLimitError / ModelNotFoundError / ContextOverflowError
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ===================== 数据类 =====================


@dataclass
class ChatMessage:
    """一条聊天消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class Usage:
    """Token 用量统计（来自上游）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Usage:
        if not d:
            return cls()
        return cls(
            prompt_tokens=int(d.get("prompt_tokens", 0)),
            completion_tokens=int(d.get("completion_tokens", 0)),
            total_tokens=int(d.get("total_tokens", 0)),
        )


@dataclass
class ChatResponse:
    """单次 chat 调用的完整响应。"""

    content: str
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    raw: dict[str, Any] = field(default_factory=dict)


# ===================== 异常 =====================


class LLMError(Exception):
    """LLM 抽象层的基础异常。"""


class AuthError(LLMError):
    """鉴权失败（key 无效/过期）。"""


class RateLimitError(LLMError):
    """触发限流。"""


class ModelNotFoundError(LLMError):
    """请求的模型不存在。"""


class ContextOverflowError(LLMError):
    """上下文超出模型窗口。"""


def describe_llm_error(e: BaseException) -> str:
    """把 LLM 调用异常转成一句话（异常类型 + 消息 + 响应 body 片段）。

    httpx 超时/网络异常的 ``str(e)`` 经常是空字符串，直接 ``f"{e}"``
    会得到 ``"LLM call failed: "`` 这种没有任何细节的信息（用户无法排查）。
    """
    err_type = type(e).__name__
    extra = ""
    resp_obj = getattr(e, "response", None)
    if resp_obj is not None:
        try:
            body = (resp_obj.text or "")[:200]
            if body:
                extra = f" body={body!r}"
        except Exception:  # noqa: BLE001
            pass
    detail = str(e) or "(no message)"
    return f"LLM call failed: {err_type}: {detail}{extra}"


# ===================== Protocol =====================


@runtime_checkable
class BaseLLMClient(Protocol):
    """LLM 客户端接口（自研 Protocol）。

    业务代码依赖这个接口而非具体实现，方便切 provider。
    """

    provider: str

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncIterator[str]:
        """发送聊天请求。

        - ``stream=False``（默认）：返回完整 :class:`ChatResponse`
        - ``stream=True``：返回 :class:`AsyncIterator[str]`，每次 yield 一个 delta 文本
        """
        ...

    async def aclose(self) -> None:
        """关闭底层资源（httpx client 等）。"""
        ...
