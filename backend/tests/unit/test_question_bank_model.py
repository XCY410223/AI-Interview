"""题库 ORM 模型单测（M4 PR-R3）：表结构 / vector 列 / 唯一约束 / 索引 / 状态常量。"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import UniqueConstraint

from app.models.question import (
    QUESTION_BANK_STATUS_COMPLETED,
    QUESTION_BANK_STATUS_FAILED,
    QUESTION_BANK_STATUS_PENDING,
    QUESTION_BANK_STATUS_PROCESSING,
    QuestionBankItem,
)


def test_table_name_and_embedding_type():
    assert QuestionBankItem.__tablename__ == "question_bank_items"
    emb = QuestionBankItem.__table__.columns["embedding"]
    assert isinstance(emb.type, Vector)
    assert emb.type.dim == 1024  # bge-m3 维度


def test_content_hash_unique_constraint():
    names = [c.name for c in QuestionBankItem.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert "uq_question_bank_items_content_hash" in names


def test_company_position_difficulty_index():
    idx_names = {idx.name for idx in QuestionBankItem.__table__.indexes}
    assert "ix_question_bank_items_company_position_difficulty" in idx_names


def test_status_constants():
    assert QUESTION_BANK_STATUS_PENDING == "pending"
    assert QUESTION_BANK_STATUS_PROCESSING == "processing"
    assert QUESTION_BANK_STATUS_COMPLETED == "completed"
    assert QUESTION_BANK_STATUS_FAILED == "failed"


def test_embedding_nullable_for_job_rows():
    # 入库作业行无 embedding，仅 chunk 行有（检索据此过滤）
    assert QuestionBankItem.__table__.columns["embedding"].nullable is True
