"""LLM 抽象层。

子模块：
- base: Protocol + 数据类 + 异常
- openai_compat: 走 OpenAI 兼容协议（minimax、OpenAI 等）
- ollama: 走 Ollama 的 /v1 兼容接口
- factory: 工厂模式创建客户端
- streaming: SSE 流式响应解析
- model_checker: 模型能力校验（章节硬限等）

公共 API（业务代码从这里 import）：
- create_llm_client
- create_llm_client_for_scene
- check_model_capability
- ChatMessage / ChatResponse / Usage
- LLMError / AuthError / RateLimitError / ModelNotFoundError / ContextOverflowError
"""

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
from .factory import (
    create_llm_client,
    create_llm_client_for_scene,
    get_default_provider,
    get_provider_config,
    load_llm_config,
    resolve_provider_for_scene,
)
from .model_checker import ModelCheckResult, ModelWarning, check_model_capability

__all__ = [
    # 数据类
    "ChatMessage",
    "ChatResponse",
    "Usage",
    # 异常
    "LLMError",
    "AuthError",
    "RateLimitError",
    "ModelNotFoundError",
    "ContextOverflowError",
    # 工厂
    "create_llm_client",
    "create_llm_client_for_scene",
    "get_default_provider",
    "get_provider_config",
    "load_llm_config",
    "resolve_provider_for_scene",
    # 模型能力
    "ModelCheckResult",
    "ModelWarning",
    "check_model_capability",
]
