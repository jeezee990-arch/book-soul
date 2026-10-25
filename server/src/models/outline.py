"""Outline 模型（大纲）。

设计：
- 每个作品可有多份大纲（不同时期的不同版本）
- ``outline_type`` 区分大纲模式：
  - "complete"：完整版（分卷/章/节 树状结构）—— 从开头写到全书结束，适合短篇
  - "semi_open"：半开放式（只写前期 + 悬念钩子）—— 后续由作者自行创作或 AI 续写
  - "freedom"：创作型（文字描述 + 关键节拍 + 主题）
- ``structure`` 是 JSON 字段，具体 schema 由 outline_type 决定；
  DB 层不强校验，应用层（service / Pydantic）做软校验
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

# 业务取值
OUTLINE_TYPES: tuple[str, ...] = ("complete", "semi_open", "freedom")


class Outline(Base, TimestampMixin):
    """大纲表。"""

    __tablename__ = "outlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outline_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="complete", index=True
    )
    structure: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"<Outline id={self.id} novel_id={self.novel_id} type={self.outline_type}>"
