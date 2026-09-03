"""SQLAlchemy 2.x 模型基类。

约定：
- 所有 ORM 模型继承 :class:`Base`
- 包含 created_at / updated_at 的表用 :class:`TimestampMixin`
- 表名用复数 snake_case（AGENTS.md 命名规范）
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """UTC 当前时间（naive 形式，SQLite 友好）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


class TimestampMixin:
    """created_at / updated_at 自动维护。

    使用方式：``class Novel(Base, TimestampMixin): ...``
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
