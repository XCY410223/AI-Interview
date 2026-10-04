"""报告 API 集成测试（TestClient + 内存 fakes，M3 计划 §七/§十二）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import FakeStorage, make_report, make_user


def _completed_interview():
    return SimpleNamespace(id=1, user_id=1, status="completed", deleted_at=None)


@pytest.fixture
def report_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)
    state["storage"] = FakeStorage({"reports/1.pdf": b"%PDF-1.4 fake"})
    state["interview"] = _completed_interview()

    async def get_current_user_override():
        return state["user"]

    async def fake_get_owned(db, *, user_id, interview_id):
        return state.get("interview")

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    monkeypatch.setattr("app.api.v1.report.get_storage", lambda: state["storage"])
    monkeypatch.setattr("app.services.interview.service.InterviewService.get_owned_or_none", fake_get_owned)
    # 拦截任务投递（避免连真实 broker）
    monkeypatch.setattr(
        "app.tasks.report.generate_report_task", SimpleNamespace(delay=lambda **kw: SimpleNamespace(id="gen"))
    )
    monkeypatch.setattr(
        "app.tasks.report.export_report_pdf_task", SimpleNamespace(delay=lambda **kw: SimpleNamespace(id="pdf"))
    )
    return client


def test_create_report_not_found_404(report_client):
    report_client.state["interview"] = None
    resp = report_client.post("/api/v1/reports", json={"interview_id": 1})
    assert resp.status_code == 404
    assert resp.json()["code"] == "REPORT_NOT_FOUND"


def test_create_report_interview_not_finished_409(report_client):
    report_client.state["interview"] = SimpleNamespace(id=1, user_id=1, status="created", deleted_at=None)
    resp = report_client.post("/api/v1/reports", json={"interview_id": 1})
    assert resp.status_code == 409
    assert resp.json()["code"] == "INTERVIEW_NOT_FINISHED"


def test_create_report_new_202(report_client):
    report_client.state["db"].configure(scalar_one_or_none=None)
    resp = report_client.post("/api/v1/reports", json={"interview_id": 1})
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["report_id"] >= 1


def test_create_report_existing_200(report_client):
    existing = make_report(report_id=9, interview_id=1, status="completed")
    report_client.state["db"].configure(scalar_one_or_none=existing)
    resp = report_client.post("/api/v1/reports", json={"interview_id": 1})
    assert resp.status_code == 200
    assert resp.json()["report_id"] == 9


def test_get_report_success(report_client):
    report = make_report(
        report_id=1, user_id=1, status="completed", overall_score=8.5, grade="良好",
        payload_json={"summary": "不错", "dimensions": [], "strengths": [], "weaknesses": [],
                      "suggestions": [], "question_scores": []},
    )
    report_client.state["db"].configure(get_map={1: report})
    resp = report_client.get("/api/v1/reports/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_id"] == 1
    assert data["overall_score"] == 8.5
    assert data["grade"] == "良好"


def test_get_report_other_user_404(report_client):
    other = make_report(report_id=1, user_id=2, status="completed")
    report_client.state["db"].configure(get_map={1: other})
    resp = report_client.get("/api/v1/reports/1")
    assert resp.status_code == 404
    assert resp.json()["code"] == "REPORT_NOT_FOUND"


def test_list_reports_pagination(report_client):
    r1 = make_report(report_id=1, user_id=1, status="completed", overall_score=8.0)
    r2 = make_report(report_id=2, user_id=1, status="pending")
    report_client.state["db"].configure(scalar_one=2, scalars=[r2, r1])
    resp = report_client.get("/api/v1/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_export_pdf_not_ready_409(report_client):
    report = make_report(report_id=1, user_id=1, status="pending")
    report_client.state["db"].configure(get_map={1: report})
    resp = report_client.post("/api/v1/reports/1/pdf")
    assert resp.status_code == 409
    assert resp.json()["code"] == "REPORT_NOT_READY"


def test_export_pdf_trigger_202(report_client):
    report = make_report(report_id=1, user_id=1, status="completed", pdf_object_key=None)
    report_client.state["db"].configure(get_map={1: report})
    resp = report_client.post("/api/v1/reports/1/pdf")
    assert resp.status_code == 202


def test_download_pdf_success(report_client):
    report = make_report(report_id=1, user_id=1, status="completed", pdf_object_key="reports/1.pdf")
    report_client.state["db"].configure(get_map={1: report})
    resp = report_client.get("/api/v1/reports/1/pdf")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake"
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]


def test_download_pdf_not_ready_409(report_client):
    report = make_report(report_id=1, user_id=1, status="completed", pdf_object_key=None)
    report_client.state["db"].configure(get_map={1: report})
    resp = report_client.get("/api/v1/reports/1/pdf")
    assert resp.status_code == 409
    assert resp.json()["code"] == "REPORT_NOT_READY"
