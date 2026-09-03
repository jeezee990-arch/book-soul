"""characters: 人物卡 + 人物卡版本表

Revision ID: 0003_characters
Revises: 0002_novel_extend
Create Date: 2026-09-03

Phase 1.2：建立 characters 和 character_versions 两张表。

注意：characters.current_version_id -> character_versions.id 是循环外键，
按以下顺序建：
1) character_versions 先建（character_id -> characters.id 暂时不建 FK，单独后加）
2) characters 建好
3) 用 batch_alter_table 单独加 characters -> character_versions 的 FK
4) 用 batch_alter_table 单独加 character_versions -> characters 的 FK
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_characters"
down_revision: Union[str, None] = "0002_novel_extend"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 先建 character_versions（无外键，单纯表结构）
    op.create_table(
        "character_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "change_reason",
            sa.String(length=30),
            nullable=False,
            server_default="initial",
        ),
        sa.Column("trigger_event", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_character_versions_character_id",
        "character_versions",
        ["character_id"],
    )

    # 2) 建 characters（FK 到 novels 即可，current_version_id 暂时不建 FK）
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="其他"),
        sa.Column("basic_info", sa.Text(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("habits", sa.Text(), nullable=True),
        sa.Column("thinking", sa.Text(), nullable=True),
        sa.Column("relationships", sa.Text(), nullable=True),
        sa.Column("growth_arc", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.id"],
            name="fk_characters_novel_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_characters_novel_id", "characters", ["novel_id"])
    op.create_index("ix_characters_role", "characters", ["role"])

    # 3) 补外键：character_versions.character_id -> characters.id
    with op.batch_alter_table("character_versions") as batch_op:
        batch_op.create_foreign_key(
            "fk_character_versions_character_id",
            "characters",
            ["character_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # 4) 补外键：characters.current_version_id -> character_versions.id
    with op.batch_alter_table("characters") as batch_op:
        batch_op.create_foreign_key(
            "fk_characters_current_version_id",
            "character_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 5) 补外键：character_versions.parent_version_id -> character_versions.id（自引用）
    with op.batch_alter_table("character_versions") as batch_op:
        batch_op.create_foreign_key(
            "fk_character_versions_parent_version_id",
            "character_versions",
            ["parent_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("character_versions") as batch_op:
        batch_op.drop_constraint(
            "fk_character_versions_parent_version_id", type_="foreignkey"
        )
    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_constraint(
            "fk_characters_current_version_id", type_="foreignkey"
        )
    with op.batch_alter_table("character_versions") as batch_op:
        batch_op.drop_constraint(
            "fk_character_versions_character_id", type_="foreignkey"
        )

    op.drop_index("ix_characters_role", table_name="characters")
    op.drop_index("ix_characters_novel_id", table_name="characters")
    op.drop_table("characters")
    op.drop_index("ix_character_versions_character_id", table_name="character_versions")
    op.drop_table("character_versions")
