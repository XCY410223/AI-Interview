"""题库 API 集成测试：JD 解析（鉴权 / 限流 / 成功，M4 PR-R1）。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.v1 import deps
from app.main import app
from app.schemas.question_bank import JDParseResponse, JDCapability
from tests.fakes import make_user


@pytest.fixture
def qb_client(client, monkeypatch):
    state = client.state
    state["user"] = make_user(user_id=1)

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    return client


def _cap(name="能力"):
    return JDCapability(
        name=name, category="hard_skill", keywords=["k", "v"], importance="must"
    )


def _payload():
    return {"jd_text": "x" * 60}


def test_jd_parse_requires_auth(client):
    resp = client.post("/api/v1/question-bank/jd/parse", json=_payload())
    assert resp.status_code == 401


def test_jd_parse_too_short_rejected(qb_client):
    resp = qb_client.post("/api/v1/question-bank/jd/parse", json={"jd_text": "x" * 49})
    assert resp.status_code == 422


def test_jd_parse_success(qb_client, monkeypatch):
    async def _fake_parse(jd_text):
        return JDParseResponse(
            position_guess="后端工程师",
            capabilities=[_cap(f"能力{i}") for i in range(5)],
            parsed_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.api.v1.question_bank.parse_jd", _fake_parse)
    resp = qb_client.post("/api/v1/question-bank/jd/parse", json=_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["position_guess"] == "后端工程师"
    assert len(data["capabilities"]) == 5


def test_jd_parse_rate_limited(qb_client, monkeypatch):
    async def _fake_parse(jd_text):
        return JDParseResponse(
            position_guess="后端工程师",
            capabilities=[_cap(f"能力{i}") for i in range(5)],
            parsed_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("app.api.v1.question_bank.parse_jd", _fake_parse)
    # 超过 AI_RATE_LIMIT_PER_HOUR（20）次后触发 429
    for _ in range(20):
        qb_client.post("/api/v1/question-bank/jd/parse", json=_payload())
    resp = qb_client.post("/api/v1/question-bank/jd/parse", json=_payload())
    assert resp.status_code == 429
    assert resp.json()["code"] == "AI_RATE_LIMITED"


# ---- 真题入库（M4 PR-R4）----
def _ingest_payload(**kw):
    base = {"company": "字节", "position": "后端", "difficulty": "medium", "content": "一段面经"}
    base.update(kw)
    return base


def _patch_enqueue(monkeypatch):
    monkeypatch.setattr(
        "app.services.question_bank.service.QuestionBankService.enqueue",
        staticmethod(lambda item_id: "task-1"),
    )


def test_ingest_requires_auth(client):
    resp = client.post("/api/v1/question-bank/ingest", json=_ingest_payload())
    assert resp.status_code == 401


def test_ingest_success(qb_client, monkeypatch):
    _patch_enqueue(monkeypatch)
    resp = qb_client.post("/api/v1/question-bank/ingest", json=_ingest_payload())
    assert resp.status_code == 202
    data = resp.json()
    assert data["item_id"] == 1
    assert data["status"] == "pending"
    assert data["task_id"] == "task-1"


def test_ingest_invalid_source_url_rejected(qb_client, monkeypatch):
    _patch_enqueue(monkeypatch)
    resp = qb_client.post(
        "/api/v1/question-bank/ingest",
        json=_ingest_payload(source_url="file:///etc/passwd"),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "QUESTION_BANK_INVALID_SOURCE"


def test_search_returns_items(qb_client, monkeypatch):
    from app.schemas.question_bank import QuestionBankSearchItem

    item = QuestionBankSearchItem(id=5, company="字节", position="后端", difficulty="medium", content="真题")

    async def fake_search(db, *, company, position, difficulty, top_k=8, redis=None):
        return [item]

    monkeypatch.setattr("app.api.v1.question_bank.retrieval.search", fake_search)
    resp = qb_client.get(
        "/api/v1/question-bank/search",
        params={"company": "字节", "position": "后端", "difficulty": "medium"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["content"] == "真题"


def test_search_requires_auth(client):
    resp = client.get("/api/v1/question-bank/search", params={"company": "字节", "position": "后端"})
    assert resp.status_code == 401


# ---- 题库模板 CRUD（M4 PR-R7-a）----
def _template_payload():
    return {
        "position": "后端", "difficulty": "medium", "category": "项目",
        "content": "介绍一下分布式事务", "reference_points": ["一致性"], "tags": ["分布式"],
    }


def test_template_create_requires_auth(client):
    resp = client.post("/api/v1/question-bank/templates", json=_template_payload())
    assert resp.status_code == 401


def test_template_create_and_get(qb_client):
    resp = qb_client.post("/api/v1/question-bank/templates", json=_template_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == 1
    assert data["content"] == "介绍一下分布式事务"
    assert data["usage_count"] == 0
