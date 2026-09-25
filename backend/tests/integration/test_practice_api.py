"""专项练习 API 集成测试（M4 PR-R7-c）：鉴权 / 生成 / 查询。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import make_user


@pytest.fixture
def practice_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    return client


def _pack():
    return SimpleNamespace(
        id=1, report_id=1, count=2,
        questions_json=[
            {"question_index": 0, "round": 0, "category": "项目", "content": "练习1",
             "reference_points": ["a"], "difficulty": "medium", "source": None},
        ],
    )


def test_create_practice_requires_auth(client):
    resp = client.post("/api/v1/practice", json={"report_id": 1, "count": 2})
    assert resp.status_code == 401


def test_create_practice_success(practice_client, monkeypatch):
    async def fake_create(db, *, user_id, report_id, count):
        return _pack()

    monkeypatch.setattr("app.api.v1.practice.PracticeService.create", fake_create)
    resp = practice_client.post("/api/v1/practice", json={"report_id": 1, "count": 2})
    assert resp.status_code == 201
    data = resp.json()
    assert data["practice_id"] == 1
    assert data["questions"][0]["content"] == "练习1"


def test_get_practice_success(practice_client, monkeypatch):
    async def fake_get(db, *, user_id, practice_id):
        return _pack()

    monkeypatch.setattr("app.api.v1.practice.PracticeService.get", fake_get)
    resp = practice_client.get("/api/v1/practice/1")
    assert resp.status_code == 200
    assert resp.json()["practice_id"] == 1
