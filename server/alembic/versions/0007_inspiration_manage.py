"""inspirations: 素材库管理（title / pinned / sort_order）

Revision ID: 0007_inspiration_manage
Revises: 0006_inspirations
Create Date: 2026-10-29

2026-10-29 素材库管理需求：
- title：用户自定义显示名（覆盖式）。为空时前端按 content 派生摘要标签。
- pinned：是否置顶。列表排序里置顶项永远在前。
- sort_order：手动排序序号（下标越小越靠前）。

⚠️ 注意：本迁移**不会**被自动执行（alembic 未接入启动流程）。
既有库升级靠 ``src/db.py::init_db`` 里的幂等补列兜底；本文件用于
手动执行 ``alembic upgrade head`` 的场景。

⚠️ 2026-10-29 评审：本迁移**必须幂等**。
   应用启动过一次后 ``init_db`` 已经把三列补上了，
   再跑 ``alembic upgrade head`` 就会撞 ``duplicate column name`` → 迁移中断。
   （以前靠"两条路互补"的说法是错的 —— 两条路都会执行，只是顺序不同。）
   现在先查 ``PRAGMA table_info``，只补缺的列。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_inspiration_manage"
down_revision: Union[str, None] = "0006_inspirations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 列名 → 列定义
_ADDED_COLUMNS: dict[str, sa.Column] = {
    "title": sa.Column("title", sa.String(length=200), nullable=True, server_default=None),
    "pinned": sa.Column(
        "pinned",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    "sort_order": sa.Column(
        "sort_order",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
}


def upgrade() -> None:
    """加三列（**幂等**：已存在的列跳过）。

    带 server_default 是关键：SQLite 的 ``ADD COLUMN ... NOT NULL`` 必须有默认值，
    否则既有行会拿到 NULL 而不是 0/FALSE。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "inspirations" not in inspector.get_table_names():
        # 表还没建（首次启动走 create_all）→ 没什么可补的
        return
    existing = {c["name"] for c in inspector.get_columns("inspirations")}
    for name, column in _ADDED_COLUMNS.items():
        if name in existing:
            continue
        op.add_column("inspirations", column)


def downgrade() -> None:
    """回退：SQLite 3.35+ 支持 DROP COLUMN；老版本 SQLite 会报错（可接受）。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "inspirations" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("inspirations")}
    for name in ("sort_order", "pinned", "title"):
        if name in existing:
            op.drop_column("inspirations", name)
