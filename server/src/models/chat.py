"""聊天模块的 ORM 模型（项目 / 对话 / 消息）。

三层结构
--------
- :class:`ChatProject` —— **项目**：一个话题容器，可以接入素材库里的素材
- :class:`ChatConversation` —— **对话**：项目内的多个话题分支
- :class:`ChatMessage` —— **消息**：对话里的 user / assistant 轮次

设计取舍
--------
- 素材接入用 ``materials`` JSON 存 **inspiration id 列表**（不建关联表）：
  素材本身可能被删，关联表会留孤儿行；JSON 存 id 天然"删了就没了"。
- 消息不继承 ``TimestampMixin``（消息只追加，不改），但仍保留 ``created_at``。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

# 消息角色
CHAT_ROLES: tuple[str, ...] = ("user", "assistant", "system")


def _utcnow_naive() -> datetime:
    """UTC 当前时间（naive 形式，SQLite 友好）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class ChatProject(Base, TimestampMixin):
    """聊天项目表。"""

    __tablename__ = "chat_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 接入的素材 id 列表（对应 ``inspirations.id``）
    materials: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    def __repr__(self) -> str:
        return f"<ChatProject id={self.id} name={self.name!r}>"


class ChatConversation(Base, TimestampMixin):
    """聊天对话表（属于某个项目）。"""

    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新对话")
    #: 本次对话用的模型名（留空 = 跟随设置页）
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    def __repr__(self) -> str:
        return f"<ChatConversation id={self.id} project_id={self.project_id}>"


class ChatMessage(Base):
    """聊天消息表。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} conv={self.conversation_id} role={self.role}>"
