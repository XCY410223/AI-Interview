"""面经入库任务单测（M4 PR-R4）：幂等短路 / 切片入库 / 去重 / 重试 / 失败。"""
from __future__ import annotations

import asyncio

import pytest

from app.tasks.rag import _run_ingest
from tests.fakes import FakeSession, make_question_bank_item


def run(coro):
    return asyncio.run(coro)


class _RetrySentinel(Exception):
    pass


class _FakeTask:
    def __init__(self):
        self.retry_calls = 0

    def retry(self, exc=None):
        self.retry_calls += 1
        raise _RetrySentinel()


def _fake_embed(vectors):
    async def embed(texts):
        # 每个 chunk 返回一个 1024 维向量（值为 texts 的哈希稳定映射）
        out = []
        for t in texts:
            v = [float(len(t) % 7) / 7.0] * 1024
            out.append(v)
        return out

    return embed


def _session(job, existing=None):
    return FakeSession().configure(get_map={job.id: job}, scalars=existing or [])


def test_run_not_found():
    session = FakeSession().configure(get_map={})
    result = run(_run_ingest(1, session_factory=lambda: session))
    assert result["status"] == "not_found"


def test_run_skips_completed():
    job = make_question_bank_item(item_id=1, status="completed")
    result = run(_run_ingest(1, session_factory=lambda: _session(job)))
    assert result["status"] == "skipped"


def test_run_short_content_inserts_one_chunk():
    job = make_question_bank_item(item_id=1, status="pending", content="一段不超过 500 字的面经")
    session = _session(job)
    result = run(_run_ingest(1, session_factory=lambda: session, embed_fn=_fake_embed(None)))
    assert result["status"] == "completed"
    assert result["chunks_total"] == 1
    assert result["chunks_inserted"] == 1
    assert job.status == "completed"
    # chunk 行已落库（status=completed、带 embedding）
    assert len(session.added) == 1
    chunk = session.added[0]
    assert chunk.embedding is not None
    assert chunk.status == "completed"


def test_run_idempotent_rerun_no_duplicate_rows():
    job = make_question_bank_item(item_id=1, status="pending", content="一段面经")
    # 已有同 content_hash 的 chunk → hash 去重跳过，不重复落行
    existing = make_question_bank_item(item_id=2, company=job.company, position=job.position,
                                       content="一段面经", embedding=[0.0] * 1024, status="completed")
    session = _session(job, existing=[existing])
    result = run(_run_ingest(1, session_factory=lambda: session, embed_fn=_fake_embed(None)))
    assert result["status"] == "completed"
    assert result["chunks_inserted"] == 0
    assert len(session.added) == 0


def test_run_cosine_dedup_drops_similar():
    job = make_question_bank_item(item_id=1, status="pending", content="面经内容")
    # 既有 chunk 向量与候选向量相同 → cosine=1.0 > 0.92 → 丢弃
    vec = [1.0] + [0.0] * 1023
    existing = make_question_bank_item(item_id=2, company=job.company, position=job.position,
                                       content="别的面经", embedding=vec, status="completed")

    async def embed_identical(texts):
        return [vec for _ in texts]

    session = _session(job, existing=[existing])
    result = run(_run_ingest(1, session_factory=lambda: session, embed_fn=embed_identical))
    assert result["chunks_deduped"] == 1
    assert result["chunks_inserted"] == 0


def test_run_embed_error_retries(monkeypatch):
    job = make_question_bank_item(item_id=1, status="pending", content="面经", retry_count=0)
    session = _session(job)

    async def failing_embed(texts):
        raise ValueError("embedding 挂了")

    task = _FakeTask()
    with pytest.raises(_RetrySentinel):
        run(_run_ingest(1, task=task, session_factory=lambda: session, embed_fn=failing_embed))
    assert task.retry_calls == 1
    assert job.retry_count == 1
    assert job.status == "pending"


def test_run_embed_error_exhausted_marks_failed():
    job = make_question_bank_item(item_id=1, status="pending", content="面经", retry_count=3)
    session = _session(job)

    async def failing_embed(texts):
        raise ValueError("embedding 挂了")

    result = run(_run_ingest(1, session_factory=lambda: session, embed_fn=failing_embed))
    assert result["status"] == "failed"
    assert job.retry_count == 4
    assert job.status == "failed"
    assert job.error_message
