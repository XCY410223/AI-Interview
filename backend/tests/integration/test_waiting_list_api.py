"""Waiting List API 集成测试（M4 PR-R7-d）：公开订阅 / 导出。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import make_user


def test_subscribe_public_success(client, monkeypatch):
    monkeypatch.setattr("app.services.waiting_list.service.WaitingListService.enqueue",
                        staticmethod(lambda email: "task-1"))
    # 公开接口，无需登录
    resp = client.post("/api/v1/waiting-list", json={"email": "user@example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["already_subscribed"] is False


def test_subscribe_invalid_email_rejected(client):
    resp = client.post("/api/v1/waiting-list", json={"email": "not-an-email"})
    assert resp.status_code == 422


@pytest.fixture
def export_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    return client


def test_export_requires_auth(client):
    resp = client.get("/api/v1/waiting-list/export")
    assert resp.status_code == 401


def test_export_streams_csv(export_client, monkeypatch):
    e1 = SimpleNamespace(email="a@b.com", created_at=None, deleted_at=None)
    e2 = SimpleNamespace(email="c@d.com", created_at=None, deleted_at=None)

    async def fake_list_all(db):
        return [e1, e2]

    monkeypatch.setattr("app.api.v1.waiting_list.WaitingListService.list_all", fake_list_all)
    resp = export_client.get("/api/v1/waiting-list/export")
    assert resp.status_code == 200
    body = resp.text
    assert "email,created_at" in body
    assert "a@b.com" in body
    assert "c@d.com" in body
    assert resp.headers["content-type"].startswith("text/csv")
