"""入库管线纯函数单测（M4 PR-R4）：切片 / hash / 相似度 / 去重 / 维度断言 / 溯源 URL。"""
from __future__ import annotations

import pytest

from app.common.exceptions import QuestionBankInvalidSource
from app.services.question_bank.ingest import (
    assert_embedding_dim,
    batch_chunks,
    content_hash,
    cosine_similarity,
    job_content_hash,
    should_drop,
    slice_text,
)
from app.services.question_bank.service import validate_source_url


# ---- 切片 ----
def test_slice_short_text_single_chunk():
    assert slice_text("短文本") == ["短文本"]


def test_slice_exactly_max():
    text = "字" * 500
    assert slice_text(text) == [text]


def test_slice_long_text_boundaries():
    # 两个以句号结尾的 400 字句子 → 应切出两块，每块 ≤500
    sentence = ("句" * 399) + "。"
    text = sentence + sentence
    chunks = slice_text(text)
    assert len(chunks) == 2
    assert all(len(c) <= 500 for c in chunks)
    assert chunks[0].endswith("。")


def test_slice_no_punctuation_hard_cut():
    text = "字" * 1000  # 无句读 → 硬切
    chunks = slice_text(text)
    assert len(chunks) == 2
    assert all(len(c) == 500 for c in chunks)


def test_slice_empty():
    assert slice_text("") == []


# ---- content_hash ----
def test_content_hash_deterministic_and_distinct():
    h1 = content_hash("字节", "后端", "题")
    h2 = content_hash("字节", "后端", "题")
    assert h1 == h2
    assert content_hash("字节", "后端", "另一题") != h1
    assert content_hash("阿里", "后端", "题") != h1
    assert len(h1) == 64


def test_job_content_hash_distinct_from_chunk_hash():
    # 短文本（单 chunk == 原文）：作业行与 chunk 行同表，hash 必须区分，否则撞 UNIQUE
    assert job_content_hash("字节", "后端", "题") != content_hash("字节", "后端", "题")
    assert len(job_content_hash("字节", "后端", "题")) == 64


# ---- 相似度 / 去重 ----
def test_cosine_similarity_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_mismatch_returns_zero():
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_should_drop_above_threshold():
    assert should_drop([[1.0, 0.0]], [0.99, 0.01]) is True  # 相似度 > 0.92


def test_should_drop_below_threshold():
    assert should_drop([[1.0, 0.0]], [0.5, 0.5]) is False  # 相似度 ≈0.71 < 0.92


# ---- 维度断言 ----
def test_assert_embedding_dim_ok():
    assert_embedding_dim([0.0] * 1024)


def test_assert_embedding_dim_mismatch_raises():
    with pytest.raises(ValueError):
        assert_embedding_dim([0.0] * 128)


# ---- 批大小 ----
def test_batch_chunks():
    chunks = ["a"] * 10
    batches = batch_chunks(chunks, size=4)
    assert [len(b) for b in batches] == [4, 4, 2]


# ---- 溯源 URL ----
def test_validate_source_url_ok():
    validate_source_url("https://example.com/post/1")
    validate_source_url("http://example.com")


def test_validate_source_url_empty_ok():
    validate_source_url(None)
    validate_source_url("")


def test_validate_source_url_bad_scheme_raises():
    with pytest.raises(QuestionBankInvalidSource):
        validate_source_url("file:///etc/passwd")


def test_validate_source_url_no_netloc_raises():
    with pytest.raises(QuestionBankInvalidSource):
        validate_source_url("javascript:alert(1)")
