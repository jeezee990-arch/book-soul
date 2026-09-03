"""Ollama 客户端。

Ollama 暴露 ``/v1`` 兼容端点（Ollama 0.3.4+），所以我们可以直接复用 OpenAI 兼容协议。
唯一区别：本地无 key，传一个假 key 即可（Ollama 会忽略）。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .openai_compat import OpenAICompatClient


class OllamaClient(OpenAICompatClient):
    """Ollama 客户端（继承 OpenAI 兼容实现，覆盖 key 处理）。"""

    provider: str = "ollama"

    def __init__(self, config: dict[str, Any], api_key: str | None = None) -> None:
        # Ollama 不需要真 key，给个占位即可
        config = {**config, "provider_name": config.get("provider_name", "ollama")}
        if not config.get("api_key_env"):
            # 本地不需要鉴权，给个任意值防止 OpenAICompatClient 抛 AuthError
            api_key = api_key or "ollama-local-no-auth"
        super().__init__(config, api_key=api_key)
        logger.debug("Ollama client initialized: base_url={}", self._base_url)
