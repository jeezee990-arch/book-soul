"""initial: novels 表

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-03

模块 0.6 初始 migration：建立 novels 表。
Phase 1 起会继续加 chapters / characters / outlines / inspirations 等表。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "novels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("genre", sa.String(length=50), nullable=False),
        sa.Column("style", sa.String(length=50), nullable=True),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_novels_genre", "novels", ["genre"])


def downgrade() -> None:
    op.drop_index("ix_novels_genre", table_name="novels")
    op.drop_table("novels")
