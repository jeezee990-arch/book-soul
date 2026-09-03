"""chapters: 章节 + 章节版本表

Revision ID: 0004_chapters
Revises: 0003_characters
Create Date: 2026-09-03

Phase 1.3：建立 chapters 和 chapter_versions 两张表。

循环 FK 顺序同 0003：
1) chapter_versions 先建（无 FK）
2) chapters 建好
3) 回填 character_versions 引用 chapters
4) 回填 chapters.current_version_id 引用 chapter_versions
5) 回填 chapter_versions.parent_version_id 自引用
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_chapters"
down_revision: Union[str, None] = "0003_characters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) chapter_versions 先建（无 FK）
    op.create_table(
        "chapter_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chapter_id", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("diff", sa.Text(), nullable=True),
        sa.Column(
            "trigger",
            sa.String(length=30),
            nullable=False,
            server_default="user_create",
        ),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_chapter_versions_chapter_id", "chapter_versions", ["chapter_id"]
    )

    # 2) chapters 建好（FK 到 novels；current_version_id 暂不建 FK）
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("outline", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="outline",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.id"],
            name="fk_chapters_novel_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_chapters_novel_id", "chapters", ["novel_id"])
    op.create_index("ix_chapters_chapter_number", "chapters", ["chapter_number"])

    # 3) chapter_versions.chapter_id -> chapters.id
    with op.batch_alter_table("chapter_versions") as batch_op:
        batch_op.create_foreign_key(
            "fk_chapter_versions_chapter_id",
            "chapters",
            ["chapter_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # 4) chapters.current_version_id -> chapter_versions.id
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.create_foreign_key(
            "fk_chapters_current_version_id",
            "chapter_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 5) chapter_versions.parent_version_id 自引用
    with op.batch_alter_table("chapter_versions") as batch_op:
        batch_op.create_foreign_key(
            "fk_chapter_versions_parent_version_id",
            "chapter_versions",
            ["parent_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("chapter_versions") as batch_op:
        batch_op.drop_constraint(
            "fk_chapter_versions_parent_version_id", type_="foreignkey"
        )
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.drop_constraint(
            "fk_chapters_current_version_id", type_="foreignkey"
        )
    with op.batch_alter_table("chapter_versions") as batch_op:
        batch_op.drop_constraint(
            "fk_chapter_versions_chapter_id", type_="foreignkey"
        )

    op.drop_index("ix_chapters_chapter_number", table_name="chapters")
    op.drop_index("ix_chapters_novel_id", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("ix_chapter_versions_chapter_id", table_name="chapter_versions")
    op.drop_table("chapter_versions")
