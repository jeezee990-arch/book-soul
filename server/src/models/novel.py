"""Novel 模型（作品）。

字段约束（Phase 1.1 补全）：
- name 必填，1-200 字
- genre 必填，受 config/genres/ 词表约束（运行时校验，本层不锁）
- style 可选
- description 可选，最长 2000 字
- status 必填，默认 'draft'，取值：draft / writing / paused / completed / abandoned
- outline_mode 可选，取值：'complete' / 'semi_open' / 'freedom'
- file_path 可选，本地文件路径
- imported 默认 False（扫描接入标志）
- read_only 默认 False
- sort_order 手动排序序号（2026-10-30 素材库管理）：下标越小越靠前
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

# 业务取值集中常量（service / schema 引用）
NOVEL_STATUSES: tuple[str, ...] = (
    "draft",
    "writing",
    "paused",
    "completed",
    "abandoned",
)
OUTLINE_MODES: tuple[str, ...] = ("complete", "semi_open", "freedom")


class Novel(Base, TimestampMixin):
    """作品表。"""

    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    outline_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    imported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    read_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", index=True
    )
    """手动排序序号（下标越小越靠前）。素材库「作品」Tab 用它持久化用户排的顺序。"""

    def __repr__(self) -> str:
        return f"<Novel id={self.id} name={self.name!r} status={self.status}>"
