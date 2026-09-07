"""llm/client 单测：统一客户端按 settings 构造、chat 尚未实现。"""
import asyncio

import pytest

from app.core.config import settings
from app.core.llm.client import LLMClient, llm_client


def test_llm_client_singleton_exists():
    assert isinstance(llm_client, LLMClient)


def test_llm_client_no_client_without_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    client = LLMClient()
    assert client._client is None


def test_llm_client_builds_client_with_key(monkeypatch):
    captured = {}

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.core.llm.client.AsyncOpenAI", _FakeAsyncOpenAI)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    client = LLMClient()

    assert client._client is not None
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == settings.LLM_BASE_URL


def test_chat_not_implemented():
    with pytest.raises(NotImplementedError):
        asyncio.run(llm_client.chat([{"role": "user", "content": "hi"}]))
