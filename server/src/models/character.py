"""Character 模型（人物卡 + 版本化）。

设计要点：
- Character 是当前态；所有可演化的字段（personality / habits / thinking /
  relationships / growth_arc）都跟 CharacterVersion 一起保留历史
- growth_arc 是自动追加字段，由 service.update_growth() 维护，不要外部直接改
- current_version_id 指向最新的 CharacterVersion；首次创建后由 service 设值
- is_active 用于标记角色"退场/死亡"等场景的软状态
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

# 业务取值集中常量
CHARACTER_ROLES: tuple[str, ...] = (
    "主角",
    "主角团",
    "反派",
    "正派",
    "队友",
    "其他",
)


def _utcnow_naive() -> datetime:
    """UTC 当前时间（naive 形式，SQLite 友好）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class Character(Base, TimestampMixin):
    """人物卡表。"""

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="其他", index=True)
    basic_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    habits: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationships: Mapped[str | None] = mapped_column(Text, nullable=True)
    growth_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("character_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    # 关系：cascade 让删 character 时自动删 versions
    versions: Mapped[list[CharacterVersion]] = relationship(
        "CharacterVersion",
        back_populates="character",
        foreign_keys="CharacterVersion.character_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Character id={self.id} name={self.name!r} role={self.role}>"


class CharacterVersion(Base):
    """人物卡版本历史表。

    每次重要变更（创建、性格变化）写一条新版本；
    snapshot 是该时刻关键字段的 JSON 快照，便于后续 diff / 回滚。
    """

    __tablename__ = "character_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("character_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(30), nullable=False, default="initial")
    trigger_event: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)

    character: Mapped[Character] = relationship(
        "Character",
        back_populates="versions",
        foreign_keys=[character_id],
    )

    def __repr__(self) -> str:
        return (
            f"<CharacterVersion id={self.id} character_id={self.character_id} "
            f"reason={self.change_reason}>"
        )
