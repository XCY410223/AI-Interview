"""create question_templates (M4 题库模板)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-25

M4 计划 §四 PR-R7-a：题库模板沉淀表（全局共享，无 user 归属）。
reference_points / tags 为 JSONB（§7.2：不参与关系查询，仅回显/注入出题）。

注意：本迁移仅生成，不执行（红线：alembic upgrade 属危险命令，人工终审）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("position", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=10), server_default="medium", nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reference_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_templates_position", "question_templates", ["position"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_question_templates_position", table_name="question_templates")
    op.drop_table("question_templates")
