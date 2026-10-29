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
手动执行 ``alembic upgrade head`` 的场景，两条路都能把列补上。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_inspiration_manage"
down_revision: Union[str, None] = "0006_inspirations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """加三列。

    带 server_default 是关键：SQLite 的 ``ADD COLUMN ... NOT NULL`` 必须有默认值，
    否则既有行会拿到 NULL 而不是 0/FALSE。
    """
    op.add_column(
        "inspirations",
        sa.Column("title", sa.String(length=200), nullable=True, server_default=None),
    )
    op.add_column(
        "inspirations",
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "inspirations",
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """回退：SQLite 3.35+ 支持 DROP COLUMN；老版本 SQLite 会报错（可接受）。"""
    op.drop_column("inspirations", "sort_order")
    op.drop_column("inspirations", "pinned")
    op.drop_column("inspirations", "title")
