"""create practice_packs + waiting_list (M4 剩余功能)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-25

M4 计划 §四 PR-R7-c/d：弱项专项练习（practice_packs）+ 增长机制（waiting_list）。
questions_json 为 JSONB 快照（§7.2）；waiting_list.email 唯一防重。

注意：本迁移仅生成，不执行（红线：alembic upgrade 属危险命令，人工终审）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_packs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="completed", nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("questions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_packs_user_id", "practice_packs", ["user_id"], unique=False)
    op.create_index("ix_practice_packs_report_id", "practice_packs", ["report_id"], unique=False)

    op.create_table(
        "waiting_list",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_waiting_list_email"),
    )


def downgrade() -> None:
    op.drop_table("waiting_list")
    op.drop_index("ix_practice_packs_report_id", table_name="practice_packs")
    op.drop_index("ix_practice_packs_user_id", table_name="practice_packs")
    op.drop_table("practice_packs")
