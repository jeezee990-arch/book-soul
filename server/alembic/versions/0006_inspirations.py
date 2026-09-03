"""inspirations: 灵感库表

Revision ID: 0006_inspirations
Revises: 0005_outlines
Create Date: 2026-09-03

Phase 1.5：建立 inspirations 表。
- novel_id 可空（通用灵感 vs 作品灵感）
- type + content JSON（按 type 存不同形状）
- tags 用 JSON array
- 仅 created_at，无 updated_at
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_inspirations"
down_revision: Union[str, None] = "0005_outlines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inspirations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("novel_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="note"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.id"],
            name="fk_inspirations_novel_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_inspirations_novel_id", "inspirations", ["novel_id"])
    op.create_index("ix_inspirations_type", "inspirations", ["type"])


def downgrade() -> None:
    op.drop_index("ix_inspirations_type", table_name="inspirations")
    op.drop_index("ix_inspirations_novel_id", table_name="inspirations")
    op.drop_table("inspirations")
