"""outlines: 大纲表

Revision ID: 0005_outlines
Revises: 0004_chapters
Create Date: 2026-09-03

Phase 1.4：建立 outlines 表。
- structure 是 JSON 字段，存分卷/章节树（complete）或文字+节拍（freedom）
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_outlines"
down_revision: Union[str, None] = "0004_chapters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column(
            "outline_type",
            sa.String(length=20),
            nullable=False,
            server_default="complete",
        ),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.id"],
            name="fk_outlines_novel_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_outlines_novel_id", "outlines", ["novel_id"])
    op.create_index("ix_outlines_outline_type", "outlines", ["outline_type"])


def downgrade() -> None:
    op.drop_index("ix_outlines_outline_type", table_name="outlines")
    op.drop_index("ix_outlines_novel_id", table_name="outlines")
    op.drop_table("outlines")
