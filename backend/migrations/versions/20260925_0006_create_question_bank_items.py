"""create question_bank_items (M4 RAG 题库)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-25

M4 计划 §四 PR-R3：真题表 + vector 扩展 + HNSW cosine 索引 + content_hash 唯一幂等键。
入库作业行（content=原始面经、embedding 空）与切片 chunk 行（带 embedding）共用本表，
检索只查 embedding IS NOT NULL 的 chunk 行（见 app/models/question.py）。

注意：本迁移仅生成，不执行（红线：alembic upgrade 属危险命令，人工终审）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector 扩展（幂等）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "question_bank_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("company", sa.String(length=100), nullable=False),
        sa.Column("position", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.String(length=10), server_default="medium", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash", name="uq_question_bank_items_content_hash"),
    )
    op.create_index("ix_question_bank_items_user_id", "question_bank_items", ["user_id"], unique=False)
    op.create_index("ix_question_bank_items_status", "question_bank_items", ["status"], unique=False)
    op.create_index(
        "ix_question_bank_items_company_position_difficulty",
        "question_bank_items",
        ["company", "position", "difficulty"],
        unique=False,
    )
    # HNSW cosine 索引（pgvector）
    op.execute(
        "CREATE INDEX ix_question_bank_items_embedding_hnsw "
        "ON question_bank_items USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_question_bank_items_embedding_hnsw")
    op.drop_index("ix_question_bank_items_company_position_difficulty", table_name="question_bank_items")
    op.drop_index("ix_question_bank_items_status", table_name="question_bank_items")
    op.drop_index("ix_question_bank_items_user_id", table_name="question_bank_items")
    op.drop_table("question_bank_items")
    # 不 DROP EXTENSION：vector 可能被其他表共用（规范 §9.6）
