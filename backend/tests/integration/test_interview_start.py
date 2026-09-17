"""面试开始 API 集成测试（QG-02/04/08/10，M2-PR1）。"""
from __future__ import annotations

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import FakeAIService, make_resume, make_user


@pytest.fixture
def interview_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)
    state["ai"] = FakeAIService()

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    monkeypatch.setattr("app.services.interview.service.ai_service", state["ai"])
    return client


def _payload(**config):
    cfg = {"position": "后端工程师", "difficulty": "medium", "question_count": 3, "style": "friendly"}
    cfg.update(config)
    return {"resume_id": 1, "config": cfg}


def test_start_success(interview_client):
    resume = make_resume(resume_id=1, user_id=1, status="completed")
    resume.parsed_content = {"summary": "3年后端经验"}
    interview_client.state["db"].configure(get_map={1: resume})
    resp = interview_client.post("/api/v1/interviews", json=_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["interview_id"] == 1
    assert data["total_questions"] == 3
    assert data["first_question"]["question_index"] == 0
    assert data["estimated_minutes"] == 6
    assert interview_client.state["ai"].generate_calls[0]["resume_summary"] == "3年后端经验"


def test_start_empty_resume_generic(interview_client):
    interview_client.state["db"].configure(get_map={})
    resp = interview_client.post("/api/v1/interviews", json=_payload())
    assert resp.status_code == 201
    assert interview_client.state["ai"].generate_calls[0]["resume_summary"] == ""


def test_start_question_count_16_rejected(interview_client):
    resp = interview_client.post("/api/v1/interviews", json=_payload(question_count=16))
    assert resp.status_code == 422


def test_start_two_interviews_distinct_ids(interview_client):
    resume = make_resume(resume_id=1, user_id=1)
    interview_client.state["db"].configure(get_map={1: resume})
    r1 = interview_client.post("/api/v1/interviews", json=_payload()).json()
    r2 = interview_client.post("/api/v1/interviews", json=_payload()).json()
    assert r1["interview_id"] != r2["interview_id"]


def test_start_requires_auth(client):
    resp = client.post("/api/v1/interviews", json=_payload())
    assert resp.status_code == 401
