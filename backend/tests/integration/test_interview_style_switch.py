"""风格切换集成测试（SS-01~05/08/10，M2-PR4）。"""
from __future__ import annotations

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import FakeAIService, make_interview, make_resume, make_user


@pytest.fixture
def style_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)
    state["ai"] = FakeAIService()

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    monkeypatch.setattr("app.services.interview.service.ai_service", state["ai"])
    return client


def _payload(style):
    return {"resume_id": 1, "config": {"position": "后端", "difficulty": "medium", "question_count": 3, "style": style}}


def test_style_switch_same_endpoint(style_client):
    resume = make_resume(resume_id=1, user_id=1)
    style_client.state["db"].configure(get_map={1: resume})
    for style in ("friendly", "stress", "deep"):
        resp = style_client.post("/api/v1/interviews", json=_payload(style))
        assert resp.status_code == 201
        assert resp.json()["total_questions"] == 3


def test_invalid_style_422(style_client):
    resp = style_client.post("/api/v1/interviews", json=_payload("rude"))
    assert resp.status_code == 422


def test_style_does_not_change_questions(style_client):
    resume = make_resume(resume_id=1, user_id=1)
    style_client.state["db"].configure(get_map={1: resume})
    style_client.post("/api/v1/interviews", json=_payload("friendly"))
    style_client.post("/api/v1/interviews", json=_payload("stress"))
    calls = style_client.state["ai"].generate_calls
    assert calls[0]["position"] == calls[1]["position"]
    assert calls[0]["difficulty"] == calls[1]["difficulty"]


def test_style_passed_to_feedback_tone(style_client):
    style_client.state["db"].configure(get_map={1: make_interview(interview_id=1, style="stress", question_count=3)})
    style_client.post("/api/v1/interviews/1/answer", json={"content": "x", "round": 0})
    style_arg = style_client.state["ai"].stream_calls[0]["style"]
    assert "薄弱" in style_arg.feedback_tone  # stress 文风
