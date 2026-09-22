"""add reports.pdf_error_message

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23

PDF 导出永久失败时回写原因（报告本身已完成，故不占用 error_message）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("pdf_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "pdf_error_message")
