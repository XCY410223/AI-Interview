"""create interview_messages

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-17

PR-4 面试消息（M2 计划 §二 PR3）：interview_messages 表，含 event_type/round/payload_json 与复合索引。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.BigInteger(), nullable=False),
        sa.Column("question_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("round", sa.Integer(), server_default="0", nullable=False),
        sa.Column("role", sa.String(length=16), server_default="candidate", nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(length=16), server_default="chunk", nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_messages_interview_id", "interview_messages", ["interview_id"], unique=False)
    op.create_index(
        "ix_interview_messages_interview_qidx_round",
        "interview_messages",
        ["interview_id", "question_index", "round"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interview_messages_interview_qidx_round", table_name="interview_messages")
    op.drop_index("ix_interview_messages_interview_id", table_name="interview_messages")
    op.drop_table("interview_messages")
