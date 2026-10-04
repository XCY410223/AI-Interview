"""专项练习服务单测（M4 PR-R7-c）：弱项提取 / 题目包生成 / 归属校验。"""
from __future__ import annotations

import asyncio

import pytest

from app.common.exceptions import PracticeNotFound, ReportNotReady
from app.schemas.interview import QuestionItem
from app.services.practice.service import PracticeService, _weaknesses
from tests.fakes import FakeSession, make_report


def run(coro):
    return asyncio.run(coro)


def _questions(n=2):
    return [
        QuestionItem(question_index=i, category="项目", content=f"练习{i}",
                     reference_points=["a"], difficulty="medium")
        for i in range(n)
    ]


def test_weaknesses_extraction():
    assert _weaknesses({"weaknesses": ["基础不牢", "表达欠佳"]}) == ["基础不牢", "表达欠佳"]


def test_weaknesses_falls_back_to_suggestions():
    assert _weaknesses({"suggestions": ["多看源码"]}) == ["多看源码"]


def test_weaknesses_empty():
    assert _weaknesses({}) == []


def test_create_generates_pack(monkeypatch):
    report = make_report(report_id=1, user_id=1, status="completed",
                         payload_json={"weaknesses": ["基础不牢"]})
    session = FakeSession().configure(get_map={1: report})

    async def fake_generate(*, weaknesses, count):
        assert weaknesses == ["基础不牢"]
        return _questions(count)

    monkeypatch.setattr("app.services.practice.service.ai_service.generate_practice", fake_generate)
    pack = run(PracticeService.create(session, user_id=1, report_id=1, count=2))
    assert pack.count == 2
    assert len(pack.questions_json) == 2
    assert pack.status == "completed"


def test_create_report_not_ready_raises(monkeypatch):
    report = make_report(report_id=1, user_id=1, status="pending")
    session = FakeSession().configure(get_map={1: report})
    with pytest.raises(ReportNotReady):
        run(PracticeService.create(session, user_id=1, report_id=1, count=2))


def test_get_not_found_raises():
    session = FakeSession().configure(get_map={})
    with pytest.raises(PracticeNotFound):
        run(PracticeService.get(session, user_id=1, practice_id=99))


def test_get_forbidden_raises():
    pack = type("P", (), {"id": 1, "user_id": 2, "deleted_at": None})()
    session = FakeSession().configure(get_map={1: pack})
    with pytest.raises(PracticeNotFound):
        run(PracticeService.get(session, user_id=1, practice_id=1))
