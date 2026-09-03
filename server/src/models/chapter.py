"""Chapter 模型（章节 + 版本化）。

设计要点：
- Chapter 是当前态；正文本体在 ChapterVersion 里，Chapter 只存 current_version_id
- 字数（word_count）= 当前版本正文字符数（含标点）。v1 用 len(content) 简单实现，
  后续要做"中文分词字数"再升级（不在 1.3 范围）
- chapter_number 在作品内按用户指定的顺序排（1, 2, 3...），不强制唯一性校验
  在 DB 层做，应用层（service）做"作品内不重复"校验
- status: outline → drafting → written → final 的写作流程
- 重写/选区重写：调用 service.update_content() 写一条新 ChapterVersion
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

# 业务取值集中常量
CHAPTER_STATUSES: tuple[str, ...] = (
    "outline",
    "drafting",
    "written",
    "final",
)

# ChapterVersion.trigger 的取值
VERSION_TRIGGERS: tuple[str, ...] = (
    "user_create",       # 用户创建章节时附 content
    "user_edit",         # 用户直接改正文
    "rewrite",           # 选区/全文 AI 重写
    "llm_generate",      # LLM 生成（章节创作）
    "imported",          # 扫描接入
)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Chapter(Base, TimestampMixin):
    """章节表。"""

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outline: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chapter_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="outline", server_default="outline"
    )

    # 关系：cascade 让删 chapter 时自动删 versions
    versions: Mapped[list[ChapterVersion]] = relationship(
        "ChapterVersion",
        back_populates="chapter",
        foreign_keys="ChapterVersion.chapter_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Chapter id={self.id} novel_id={self.novel_id} "
            f"number={self.chapter_number} status={self.status}>"
        )


class ChapterVersion(Base):
    """章节版本历史表。

    每次写正文（创建/重写/编辑）写一条新版本。
    content 是该时刻的完整正文；diff 留给后续 Phase 4 章节生成补。
    """

    __tablename__ = "chapter_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chapter_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(
        String(30), nullable=False, default="user_create"
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",  # 列名仍是 metadata（避免与 SQLAlchemy reserved 冲突）
        JSON,
        nullable=True,
    )
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )

    chapter: Mapped[Chapter] = relationship(
        "Chapter",
        back_populates="versions",
        foreign_keys=[chapter_id],
    )

    def __repr__(self) -> str:
        return (
            f"<ChapterVersion id={self.id} chapter_id={self.chapter_id} "
            f"trigger={self.trigger} words={self.word_count}>"
        )
