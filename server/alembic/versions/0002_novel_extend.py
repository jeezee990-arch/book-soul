"""novel_extend: 补 novels 表的 outline_mode / file_path / imported / read_only 字段

Revision ID: 0002_novel_extend
Revises: 0001_initial
Create Date: 2026-09-03

Phase 1.1：补全 Novel 模型字段。
- outline_mode  TEXT  NULL  ('complete' / 'freedom')
- file_path     TEXT  NULL  (本地文件路径)
- imported      INT   NOT NULL DEFAULT 0
- read_only     INT   NOT NULL DEFAULT 0
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_novel_extend"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("novels") as batch_op:
        batch_op.add_column(sa.Column("outline_mode", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("file_path", sa.String(length=1000), nullable=True))
        batch_op.add_column(
            sa.Column(
                "imported",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "read_only",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("novels") as batch_op:
        batch_op.drop_column("read_only")
        batch_op.drop_column("imported")
        batch_op.drop_column("file_path")
        batch_op.drop_column("outline_mode")
