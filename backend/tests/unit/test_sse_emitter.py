"""SSE 发射器单测：评分 clamp、维度清洗、序列化格式（SSE-05/06/11）。"""
from __future__ import annotations

import asyncio

from app.schemas.interview_event import ChunkEvent, MetaEvent, ScoreEvent
from app.services.interview.sse_emitter import SSEEmitter, clamp_score, sanitize_dimensions


def test_clamp_over_max():
    assert clamp_score(11.5) == 10.0


def test_clamp_under_min():
    assert clamp_score(-1.0) == 0.0


def test_clamp_one_decimal():
    assert clamp_score(9.12) == 9.1


def test_sanitize_dimensions_filters_non_numeric():
    assert sanitize_dimensions({"a": 8.0, "b": "bad", "c": 7}) == {"a": 8.0, "c": 7.0}


def test_sanitize_dimensions_none():
    assert sanitize_dimensions(None) == {}


def test_emitter_score_clamps():
    ev = SSEEmitter.score({"score": 11.5, "dimensions": {"a": 8}, "feedback": "x"})
    assert isinstance(ev, ScoreEvent)
    assert ev.score == 10.0
    assert ev.dimensions == {"a": 8.0}


def test_emitter_score_negative_clamps():
    assert SSEEmitter.score({"score": -1.0}).score == 0.0


def test_emitter_score_missing_defaults_zero():
    ev = SSEEmitter.score({})
    assert ev.score == 0.0
    assert ev.dimensions == {}


def test_meta_and_chunk():
    m = SSEEmitter.meta(12, 3, 1)
    assert isinstance(m, MetaEvent)
    assert (m.interview_id, m.question_index, m.round) == (12, 3, 1)
    c = SSEEmitter.chunk("hi")
    assert isinstance(c, ChunkEvent) and c.content == "hi"


def test_serialize_format():
    async def gen():
        yield SSEEmitter.chunk("a")
        yield SSEEmitter.chunk("b")

    async def collect():
        return [line async for line in SSEEmitter.serialize(gen())]

    lines = asyncio.run(collect())
    assert lines == [
        'data: {"type":"chunk","content":"a"}\n\n',
        'data: {"type":"chunk","content":"b"}\n\n',
    ]
