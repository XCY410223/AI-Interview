"""JD 解析服务单测：正常解析 / 非法 JSON 降级 / 校验失败降级 / 注入防护（M4 PR-R1）。"""
from __future__ import annotations

import asyncio

import pytest

from app.common.exceptions import QuestionBankParseError
from app.core.llm.client import LLMError
from app.schemas.question_bank import JDParseResponse
from app.services.question_bank.jd_service import parse_jd


def run(coro):
    return asyncio.run(coro)


class _FakeClient:
    def __init__(self, data=None, exc=None):
        self._data = data
        self._exc = exc
        self.calls: list = []

    async def chat(self, messages, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if self._exc is not None:
            raise self._exc
        result = type("R", (), {})()
        result.data = self._data
        return result


def _cap(**kw):
    base = {
        "name": "Kafka 消息可靠性",
        "category": "hard_skill",
        "keywords": ["Kafka", "消息队列"],
        "importance": "must",
    }
    base.update(kw)
    return base


def _valid_data():
    return {
        "position_guess": "后端工程师",
        "capabilities": [_cap(name=f"能力{i}") for i in range(5)],
    }


def test_parse_jd_success(monkeypatch):
    client = _FakeClient(data=_valid_data())
    monkeypatch.setattr("app.services.question_bank.jd_service.llm_client", client)
    resp = run(parse_jd("x" * 60))
    assert isinstance(resp, JDParseResponse)
    assert resp.position_guess == "后端工程师"
    assert len(resp.capabilities) == 5
    # 分层消息：system 为指令，user 为包裹在分隔符内的 JD 原文（§9.4）
    assert client.calls[0]["json_mode"] is True
    assert client.calls[0]["messages"][0]["role"] == "system"
    assert client.calls[0]["messages"][1]["role"] == "user"
    assert "<JD>" in client.calls[0]["messages"][1]["content"]
    assert "</JD>" in client.calls[0]["messages"][1]["content"]


def test_parse_jd_llm_error_raises_422(monkeypatch):
    monkeypatch.setattr("app.services.question_bank.jd_service.llm_client", _FakeClient(exc=LLMError("boom")))
    with pytest.raises(QuestionBankParseError):
        run(parse_jd("x" * 60))


def test_parse_jd_invalid_json_raises_422(monkeypatch):
    monkeypatch.setattr("app.services.question_bank.jd_service.llm_client", _FakeClient(data={"capabilities": []}))
    with pytest.raises(QuestionBankParseError):
        run(parse_jd("x" * 60))


def test_parse_jd_capability_out_of_range_raises_422(monkeypatch):
    data = {"position_guess": "后端", "capabilities": [_cap(name="能力")]}  # 仅 1 项 < 5
    monkeypatch.setattr("app.services.question_bank.jd_service.llm_client", _FakeClient(data=data))
    with pytest.raises(QuestionBankParseError):
        run(parse_jd("x" * 60))


def test_parse_jd_invalid_capability_field_raises_422(monkeypatch):
    data = {"position_guess": "后端", "capabilities": [_cap(category="bogus") for _ in range(5)]}
    monkeypatch.setattr("app.services.question_bank.jd_service.llm_client", _FakeClient(data=data))
    with pytest.raises(QuestionBankParseError):
        run(parse_jd("x" * 60))


def test_parse_jd_missing_position_guess_falls_back(monkeypatch):
    data = {"capabilities": [_cap(name=f"能力{i}") for i in range(5)]}
    monkeypatch.setattr("app.services.question_bank.jd_service.llm_client", _FakeClient(data=data))
    resp = run(parse_jd("x" * 60))
    assert resp.position_guess == "未知岗位"
