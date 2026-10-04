"""drop waiting_list（下线抢先体验/等候名单功能）

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-04

移除增长机制（M4 PR-R7-d）的 waiting_list 表：抢先体验订阅功能整体下线。
前端 WaitingListCard、后端 /waiting-list 路由、模型与服务一并删除。

注意：本迁移仅生成，不执行（红线：alembic upgrade 属危险命令，人工终审）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("waiting_list")


def downgrade() -> None:
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
