"""Settings Pydantic schemas（Phase 2.4）。

层级：
- LLMConfig：LLM 相关（provider / model）
- UIConfig：UI 偏好（theme）
- SecurityConfig：安全（encryption_enabled）
- SettingsBase：合并上面的子模型
- SettingsRead：API 返回（包含 key 存在性，但不返回 key 值）
- SettingsUpdate：部分更新（所有字段可选）
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

LLM_PROVIDERS = ("minimax", "openai", "ollama")
UI_THEMES = ("dark", "light")


class LLMConfig(BaseModel):
    """LLM 配置。"""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        default="minimax",
        description=f"LLM provider，取值之一：{', '.join(LLM_PROVIDERS)}",
    )
    model: str = Field(
        default="MiniMax-Text-01",
        max_length=100,
        description="当前 provider 的模型名",
    )


class UIConfig(BaseModel):
    """UI 偏好。"""

    model_config = ConfigDict(extra="forbid")

    theme: str = Field(
        default="dark",
        description=f"主题，取值之一：{', '.join(UI_THEMES)}",
    )


class SecurityConfig(BaseModel):
    """安全设置。"""

    model_config = ConfigDict(extra="forbid")

    encryption_enabled: bool = Field(
        default=False,
        description="是否对敏感字段启用 Fernet 加密（改后需重启服务）",
    )


class SettingsBase(BaseModel):
    """Settings 共有字段。"""

    model_config = ConfigDict(extra="forbid")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


class SettingsRead(SettingsBase):
    """API 返回：包含哪些 provider 已配置 key（不返回 key 值）。"""

    api_key_configured: dict[str, bool] = Field(
        default_factory=dict,
        description="key=provider name, value=key 是否已存 keyring",
    )


class SettingsUpdate(BaseModel):
    """部分更新（所有字段可选）。"""

    model_config = ConfigDict(extra="forbid")

    llm: LLMConfig | None = None
    ui: UIConfig | None = None
    security: SecurityConfig | None = None


class APIKeyUpdate(BaseModel):
    """API Key 录入。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=500, description="要保存的 API key")
