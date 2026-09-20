"""create reports

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-20

PR-报告（M3 计划 §三）：reports 表，含生成状态机、interview_id 唯一约束、
JSONB 快照（dimensions_json / payload_json）与 PDF 产物 key。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("prompt_version", sa.String(length=16), nullable=False),
        sa.Column("overall_score", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("grade", sa.String(length=16), nullable=True),
        sa.Column("dimensions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pdf_object_key", sa.String(length=512), nullable=True),
        sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id", name="uq_reports_interview_id"),
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"], unique=False)
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_user_id", table_name="reports")
    op.drop_table("reports")
