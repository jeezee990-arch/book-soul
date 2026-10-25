"""聊天模块的 Pydantic schemas（输入/输出契约）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_NAME_MAX = 120
_TITLE_MAX = 200
_CONTENT_MAX = 20_000


# ===== 项目 =====


class ChatProjectCreate(BaseModel):
    """新建项目。"""

    name: str = Field(min_length=1, max_length=_NAME_MAX, description="项目名")
    description: str | None = Field(default=None, max_length=2000)
    materials: list[int] = Field(
        default_factory=list, max_length=100, description="接入的素材 id（inspirations.id）"
    )


class ChatProjectUpdate(BaseModel):
    """更新项目（部分更新）。"""

    name: str | None = Field(default=None, min_length=1, max_length=_NAME_MAX)
    description: str | None = Field(default=None, max_length=2000)
    materials: list[int] | None = Field(
        default=None, max_length=100, description="接入的素材 id（整体替换）"
    )


class ChatProjectRead(BaseModel):
    """项目返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    materials: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ===== 对话 =====


class ChatConversationCreate(BaseModel):
    """新建对话。"""

    title: str = Field(default="新对话", max_length=_TITLE_MAX)
    model: str | None = Field(default=None, max_length=120)


class ChatConversationUpdate(BaseModel):
    """更新对话（重命名 / 换模型）。"""

    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    model: str | None = Field(default=None, max_length=120)


class ChatConversationRead(BaseModel):
    """对话返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    model: str | None = None
    created_at: datetime
    updated_at: datetime


# ===== 消息 =====


class ChatMessageRead(BaseModel):
    """消息返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    model: str | None = None
    created_at: datetime


class ChatSendRequest(BaseModel):
    """发送一条消息。"""

    content: str = Field(min_length=1, max_length=_CONTENT_MAX, description="用户消息正文")
    model: str | None = Field(default=None, max_length=120, description="指定模型；缺省跟随设置页")


class ChatSendResponse(BaseModel):
    """非流式发送结果。"""

    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    model: str = ""
