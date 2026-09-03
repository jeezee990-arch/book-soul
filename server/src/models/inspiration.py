"""Inspiration 模型（灵感库）。

设计：
- novel_id 可空：通用灵感（不属于任何作品）vs 作品灵感
- 没有 updated_at：灵感创建后基本不改（保留 history 通过 service 层加版本需要时再说）
- type 决定 content 形状（service 层按 type 校验）
- tags 用 JSON array 而非 TEXT（便于按 tag 检索，后续可加索引/查询）
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# 业务取值
INSPIRATION_TYPES: tuple[str, ...] = (
    "keyword",  # 关键词灵感
    "plot",  # 情节灵感
    "snippet",  # 片段/句子
    "image",  # 画面描述
    "note",  # 通用备注
)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Inspiration(Base):
    """灵感表。"""

    __tablename__ = "inspirations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("novels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="note", index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)

    def __repr__(self) -> str:
        return f"<Inspiration id={self.id} type={self.type} novel_id={self.novel_id}>"
