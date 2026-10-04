"""题库 schema 单测：JD 解析契约与入库请求（M4 PR-R1/R4）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.question_bank import (
    IngestRequest,
    JDCapability,
    JDParseRequest,
    JDParseResponse,
)


def _capability(**kw):
    base = {
        "name": "Kafka 消息可靠性",
        "category": "hard_skill",
        "keywords": ["Kafka", "消息队列", "可靠性"],
        "importance": "must",
    }
    base.update(kw)
    return base


def test_jd_parse_request_valid():
    req = JDParseRequest(jd_text="x" * 50)
    assert len(req.jd_text) == 50


def test_jd_parse_request_too_short_rejected():
    with pytest.raises(ValidationError):
        JDParseRequest(jd_text="x" * 49)


def test_jd_parse_request_too_long_rejected():
    with pytest.raises(ValidationError):
        JDParseRequest(jd_text="x" * 20001)


def test_capability_invalid_category_rejected():
    with pytest.raises(ValidationError):
        JDCapability.model_validate(_capability(category="unknown"))


def test_capability_keywords_range():
    with pytest.raises(ValidationError):
        JDCapability.model_validate(_capability(keywords=["only-one"]))


def test_capability_invalid_importance_rejected():
    with pytest.raises(ValidationError):
        JDCapability.model_validate(_capability(importance="maybe"))


def test_jd_parse_response_requires_5_15():
    caps = [_capability(name=f"能力{i}") for i in range(5)]
    resp = JDParseResponse(position_guess="后端", capabilities=caps, parsed_at="2026-09-25T00:00:00Z")
    assert len(resp.capabilities) == 5


def test_jd_parse_response_fewer_than_5_rejected():
    caps = [_capability(name="能力")]
    with pytest.raises(ValidationError):
        JDParseResponse(position_guess="后端", capabilities=caps, parsed_at="2026-09-25T00:00:00Z")


def test_ingest_request_valid_default_difficulty():
    req = IngestRequest(company="字节", position="后端", content="一段面经")
    assert req.difficulty == "medium"


def test_ingest_request_source_url_optional():
    req = IngestRequest(company="字节", position="后端", content="一段面经", source_url="https://example.com/x")
    assert req.source_url == "https://example.com/x"
