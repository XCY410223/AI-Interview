"""面试历史回放 API 集成测试（M4 PR-R7-b）：列表 / 详情 / 重评。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import make_interview, make_user


@pytest.fixture
def replay_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    return client


def test_list_interviews_requires_auth(client):
    resp = client.get("/api/v1/interviews")
    assert resp.status_code == 401


def test_list_interviews(replay_client, monkeypatch):
    i1 = make_interview(interview_id=1, user_id=1, status="completed")
    i2 = make_interview(interview_id=2, user_id=1, status="created")

    async def fake_list(db, *, user_id, page=1, page_size=20):
        return 2, [i1, i2]

    monkeypatch.setattr("app.api.v1.interview.InterviewService.list", fake_list)
    resp = replay_client.get("/api/v1/interviews")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["items"][0]["interview_id"] == 1


def test_get_interview_detail(replay_client, monkeypatch):
    from app.schemas.interview import InterviewReplay

    replay = InterviewReplay(
        interview_id=1, position="后端", difficulty="medium", style="friendly",
        status="completed", question_count=3,
    )

    async def fake_replay(db, *, user_id, interview_id):
        return replay

    monkeypatch.setattr("app.api.v1.interview.InterviewService.get_replay", fake_replay)
    resp = replay_client.get("/api/v1/interviews/1")
    assert resp.status_code == 200
    assert resp.json()["interview_id"] == 1


def test_re_evaluate(replay_client, monkeypatch):
    result = SimpleNamespace(question_index=0, score=8.0, dimensions={"completeness": 8.0}, feedback="重评")

    async def fake_re_eval(db, *, user_id, interview_id, question_index):
        return result

    monkeypatch.setattr("app.api.v1.interview.InterviewService.re_evaluate", fake_re_eval)
    resp = replay_client.post("/api/v1/interviews/1/questions/0/re-evaluate")
    assert resp.status_code == 200
    assert resp.json()["score"] == 8.0
