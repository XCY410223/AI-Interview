"""报告服务单测：幂等创建、归属校验、序列化空值兜底（M3 计划 §二/§七/§十一）。"""
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.common.exceptions import ReportNotFound
from app.services.report.service import ReportService
from tests.fakes import FakeSession, make_report


def run(coro):
    return asyncio.run(coro)


def test_create_pending_new():
    db = FakeSession().configure(scalar_one_or_none=None)
    report = run(ReportService.create_pending(db, interview_id=1, user_id=1, prompt_version="1.0"))
    assert report.id == 1
    assert report.status == "pending"
    assert report.interview_id == 1


def test_create_pending_idempotent():
    existing = make_report(report_id=5, interview_id=1, status="pending")
    db = FakeSession().configure(scalar_one_or_none=existing)
    report = run(ReportService.create_pending(db, interview_id=1, user_id=1, prompt_version="1.0"))
    assert report.id == 5  # 返回既有行，不新建


def test_get_ownership_violation_raises_not_found():
    other = make_report(report_id=1, user_id=2)
    db = FakeSession().configure(get_map={1: other})
    with pytest.raises(ReportNotFound):
        run(ReportService.get(db, user_id=1, report_id=1))


def test_get_not_found():
    db = FakeSession().configure(get_map={})
    with pytest.raises(ReportNotFound):
        run(ReportService.get(db, user_id=1, report_id=999))


def test_build_detail_falls_back_on_empty_jsonb():
    report = make_report(
        report_id=1, interview_id=9, status="completed", overall_score=Decimal("8.5"),
        grade="良好", payload_json=None, dimensions_json=None,
    )
    detail = ReportService.build_detail(report)
    assert detail.report_id == 1
    assert detail.overall_score == 8.5
    assert detail.grade == "良好"
    assert detail.dimensions == []
    assert detail.pdf_ready is False


def test_build_detail_with_payload():
    report = make_report(
        report_id=1, interview_id=9, status="completed", overall_score=8.0, grade="良好",
        payload_json={
            "summary": "整体不错",
            "dimensions": [{"key": "fundamentals", "name": "基础知识", "score": 8.0}],
            "strengths": ["基础扎实"],
            "weaknesses": [],
            "suggestions": [],
            "hire_recommendation": "推荐",
            "question_scores": [{"question_index": 0, "round": 0, "question": "q", "score": 8.0}],
            "answer_quality_avg": 7.5,
        },
        pdf_object_key="reports/1.pdf",
    )
    detail = ReportService.build_detail(report)
    assert detail.summary == "整体不错"
    assert detail.dimensions[0].name == "基础知识"
    assert detail.answer_quality_avg == 7.5
    assert detail.pdf_ready is True
