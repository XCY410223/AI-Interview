"""create interviews

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17

PR-3 面试场次（M2 计划 §二 PR1）：interviews 表，含 style/current_round/questions_json/config_json。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("resume_id", sa.BigInteger(), nullable=True),
        sa.Column("position", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=16), server_default="medium", nullable=False),
        sa.Column("question_count", sa.Integer(), server_default="8", nullable=False),
        sa.Column("style", sa.String(length=16), server_default="friendly", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="created", nullable=False),
        sa.Column("current_question_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_round", sa.Integer(), server_default="0", nullable=False),
        sa.Column("questions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interviews_user_id", "interviews", ["user_id"], unique=False)
    op.create_index("ix_interviews_resume_id", "interviews", ["resume_id"], unique=False)
    op.create_index("ix_interviews_status", "interviews", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interviews_status", table_name="interviews")
    op.drop_index("ix_interviews_resume_id", table_name="interviews")
    op.drop_index("ix_interviews_user_id", table_name="interviews")
    op.drop_table("interviews")
