"""llm/client embed_texts 单测：统一客户端 embedding 扩展（M4 PR-R3，红线 6）。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from app.core.config import settings
from app.core.llm.client import LLMClient, LLMError


def run(coro):
    return asyncio.run(coro)


def make_embedding_response(vectors: list[list[float]]) -> SimpleNamespace:
    data = [SimpleNamespace(index=i, embedding=v) for i, v in enumerate(vectors)]
    return SimpleNamespace(data=data)


class FakeEmbeddings:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.outcomes:
            raise AssertionError("fake embeddings.create() 被调用次数超出预置 outcomes")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeEmbeddingClient:
    def __init__(self, outcomes):
        self.embeddings = FakeEmbeddings(outcomes)


def status_error(code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.example/v1/embeddings")
    response = httpx.Response(code, request=request)
    return APIStatusError(f"status {code}", response=response, body=None)


def test_embed_texts_success_ordered():
    client = LLMClient(embedding_client=FakeEmbeddingClient([
        make_embedding_response([[0.1, 0.2], [0.3, 0.4]]),
    ]))
    vectors = run(client.embed_texts(["a", "b"]))
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_texts_empty_returns_empty():
    client = LLMClient(embedding_client=FakeEmbeddingClient([]))
    assert run(client.embed_texts([])) == []


def test_embed_texts_uses_default_model():
    client = LLMClient(embedding_client=FakeEmbeddingClient([make_embedding_response([[1.0]])]))
    run(client.embed_texts(["a"]))
    assert client._embedding_client.embeddings.calls[0]["model"] == settings.EMBEDDING_MODEL


def test_embed_texts_not_configured_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "")
    client = LLMClient()
    assert client._embedding_client is None
    with pytest.raises(LLMError):
        run(client.embed_texts(["a"]))


def test_embed_texts_retries_then_succeeds(monkeypatch):
    async def fake_sleep(delay):
        pass

    monkeypatch.setattr("app.core.llm.client.asyncio.sleep", fake_sleep)
    err = APIConnectionError(request=httpx.Request("POST", "https://x"))
    client = LLMClient(embedding_client=FakeEmbeddingClient([
        err, make_embedding_response([[0.5]]),
    ]))
    vectors = run(client.embed_texts(["a"]))
    assert vectors == [[0.5]]
    assert len(client._embedding_client.embeddings.calls) == 2


def test_embed_texts_non_retryable_no_retry():
    client = LLMClient(embedding_client=FakeEmbeddingClient([status_error(400)]))
    with pytest.raises(LLMError):
        run(client.embed_texts(["a"]))
    assert len(client._embedding_client.embeddings.calls) == 1


def test_embed_texts_count_mismatch_raises():
    client = LLMClient(embedding_client=FakeEmbeddingClient([
        make_embedding_response([[1.0]]),  # 1 个向量对应 2 个输入
    ]))
    with pytest.raises(LLMError):
        run(client.embed_texts(["a", "b"]))
    assert len(client._embedding_client.embeddings.calls) == 1
