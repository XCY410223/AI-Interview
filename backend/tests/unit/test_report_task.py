"""报告任务单测：状态机全路径、幂等短路、重试、PDF 导出（M3 计划 §六/§十一）。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.core.llm.client import LLMError
from app.models.report import (
    REPORT_STATUS_COMPLETED,
    REPORT_STATUS_FAILED,
    REPORT_STATUS_PENDING,
)
from app.schemas.report import DIMENSION_KEYS
from app.services.interview.service import InterviewContext
from app.tasks.report import _run_export_pdf, _run_generate
from tests.fakes import FakeRedis, FakeSession, FakeStorage, make_report


def run(coro):
    return asyncio.run(coro)


def _ctx(**kw) -> InterviewContext:
    defaults = dict(
        interview_id=1, user_id=1, position="后端工程师", difficulty="medium", style="friendly",
        resume_summary="3年后端", questions=[], turns=[], answer_quality_avg=7.5,
    )
    defaults.update(kw)
    return InterviewContext(**defaults)


def _session_factory(report):
    def factory():
        return FakeSession().configure(get_map={report.id: report})

    return factory


def _payload():
    return {
        "summary": "整体不错",
        "dimensions": [{"key": k, "score": 8.0} for k in DIMENSION_KEYS],
        "strengths": ["基础扎实"],
        "weaknesses": [],
        "suggestions": [],
        "hire_recommendation": "推荐",
        "question_scores": [],
    }


def _patch(monkeypatch, *, payload=None, exc=None, ctx=None):
    async def fake_chat(messages, json_mode=False):
        if exc is not None:
            raise exc
        return SimpleNamespace(data=payload)

    async def fake_load(db, interview_id, user_id):
        return ctx if ctx is not None else _ctx()

    monkeypatch.setattr("app.tasks.report.llm_client.chat", fake_chat)
    monkeypatch.setattr("app.tasks.report.InterviewService.load_for_report", fake_load)
    monkeypatch.setattr(
        "app.tasks.report.export_report_pdf_task", SimpleNamespace(delay=lambda **kw: None)
    )


def test_generate_completed_short_circuits(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_COMPLETED)
    _patch(monkeypatch, payload=_payload())
    result = run(_run_generate(1, session_factory=_session_factory(report), redis_factory=lambda: FakeRedis()))
    assert result["status"] == "skipped"
    assert report.status == REPORT_STATUS_COMPLETED


def test_generate_success(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_PENDING)
    _patch(monkeypatch, payload=_payload())
    result = run(_run_generate(1, session_factory=_session_factory(report), redis_factory=lambda: FakeRedis()))
    assert result["status"] == "completed"
    assert report.status == REPORT_STATUS_COMPLETED
    assert report.overall_score == 8.0
    assert report.grade == "良好"
    assert report.payload_json["answer_quality_avg"] == 7.5


def test_generate_llm_error_retries_and_returns_pending(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_PENDING, retry_count=0)
    _patch(monkeypatch, exc=LLMError("LLM 挂了"))
    with pytest.raises(LLMError):
        run(_run_generate(1, session_factory=_session_factory(report), redis_factory=lambda: FakeRedis()))
    assert report.retry_count == 1
    assert report.status == REPORT_STATUS_PENDING


def test_generate_exhausted_marks_failed(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_PENDING, retry_count=3)
    _patch(monkeypatch, exc=LLMError("LLM 挂了"))
    result = run(_run_generate(1, session_factory=_session_factory(report), redis_factory=lambda: FakeRedis()))
    assert result["status"] == "failed"
    assert report.status == REPORT_STATUS_FAILED
    assert report.retry_count == 4


def test_export_pdf_renders_and_uploads(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_COMPLETED, payload_json=_payload())
    storage = FakeStorage()
    monkeypatch.setattr("app.tasks.report._render_pdf", lambda html: b"%PDF-fake")
    result = run(_run_export_pdf(1, session_factory=_session_factory(report), storage=storage))
    assert result["status"] == "completed"
    assert report.pdf_object_key == "reports/1.pdf"
    assert storage.objects["reports/1.pdf"] == b"%PDF-fake"


def test_export_pdf_not_ready(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_PENDING)
    result = run(_run_export_pdf(1, session_factory=_session_factory(report), storage=FakeStorage()))
    assert result["status"] == "not_ready"


def test_export_pdf_skips_if_exists(monkeypatch):
    report = make_report(report_id=1, status=REPORT_STATUS_COMPLETED, pdf_object_key="reports/1.pdf")
    result = run(_run_export_pdf(1, session_factory=_session_factory(report), storage=FakeStorage()))
    assert result["status"] == "skipped"
