"""真题检索单测（M4 PR-R5）：缓存 key / 查询文本 / cosine 检索 / 缓存命中与回填。"""
from __future__ import annotations

import asyncio
import json

from app.schemas.question_bank import QuestionBankSearchItem
from app.services.question_bank.retrieval import (
    build_query_text,
    cache_key,
    cosine_search,
    search,
)
from tests.fakes import FakeRedis, FakeSession, make_question_bank_item


def run(coro):
    return asyncio.run(coro)


def test_cache_key_format():
    assert cache_key("字节", "后端", "medium") == "qbank:search:字节:后端:medium"


def test_build_query_text():
    assert "字节" in build_query_text("字节", "后端", "medium")
    assert "面试真题" in build_query_text("字节", "后端", "medium")


def test_cosine_search_returns_rows():
    chunk = make_question_bank_item(item_id=5, embedding=[0.1] * 1024, status="completed")
    session = FakeSession().configure(scalars=[chunk])
    rows = run(cosine_search(session, query_vector=[0.1] * 1024, company="字节", position="后端", difficulty="medium"))
    assert rows == [chunk]


def test_search_cache_hit_skips_embedding():
    item = QuestionBankSearchItem(id=5, company="字节", position="后端", difficulty="medium", content="真题")
    redis = FakeRedis()
    redis._data[cache_key("字节", "后端", "medium")] = json.dumps([item.model_dump()], ensure_ascii=False)

    called = {"n": 0}

    async def embed(texts):
        called["n"] += 1
        return [[0.0] * 1024 for _ in texts]

    session = FakeSession().configure(scalars=[])
    result = run(search(session, company="字节", position="后端", difficulty="medium", redis=redis, embed_fn=embed))
    assert called["n"] == 0  # 命中缓存，未调用 embedding
    assert result[0].content == "真题"


def test_search_cache_miss_embeds_and_fills_cache():
    chunk = make_question_bank_item(item_id=5, embedding=[0.1] * 1024, status="completed")
    session = FakeSession().configure(scalars=[chunk])
    redis = FakeRedis()

    async def embed(texts):
        return [[0.1] * 1024 for _ in texts]

    result = run(search(session, company="字节", position="后端", difficulty="medium", redis=redis, embed_fn=embed))
    assert len(result) == 1
    assert result[0].id == 5
    # 回填缓存
    assert cache_key("字节", "后端", "medium") in redis._data


def test_search_zero_hit_returns_empty():
    session = FakeSession().configure(scalars=[])
    redis = FakeRedis()

    async def embed(texts):
        return [[0.1] * 1024 for _ in texts]

    result = run(search(session, company="字节", position="后端", difficulty="medium", redis=redis, embed_fn=embed))
    assert result == []
