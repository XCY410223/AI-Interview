"""llm/client 单测：统一客户端构造、可重试判定、超时/重试/降级/Token 计量/审计。

覆盖 M0-4 验收重点——重试分支（成功重试、重试耗尽降级、非可重试不重试、指数退避）。
全部使用 fake AsyncOpenAI（mock），不发起真实网络请求。
"""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.core.config import settings
from app.core.llm.client import (
    LLMClient,
    LLMError,
    LLMResult,
    _is_retryable,
    _request_fingerprint,
    llm_client,
)

# ---------------------------------------------------------------------------
# 测试用 fake（mock AsyncOpenAI，不触网）
# ---------------------------------------------------------------------------

_UNSET = object()


def make_completion(
    content: str = "{}",
    *,
    prompt_tokens: int = 11,
    completion_tokens: int = 22,
    model: str = "deepseek-chat",
    usage: SimpleNamespace | None = _UNSET,
) -> SimpleNamespace:
    """构造一个与 ChatCompletion 结构兼容的最小对象；usage=_UNSET 时按默认 tokens 生成。"""
    if usage is _UNSET:
        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.outcomes:
            raise AssertionError("fake create() 被调用次数超出预置 outcomes")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeChat:
    def __init__(self, outcomes):
        self.completions = FakeCompletions(outcomes)


class FakeAsyncOpenAI:
    def __init__(self, outcomes, **kwargs):
        self.chat = FakeChat(outcomes)
        self.kwargs = kwargs


def make_client(outcomes) -> tuple[LLMClient, FakeAsyncOpenAI]:
    fake = FakeAsyncOpenAI(outcomes)
    return LLMClient(client=fake), fake


def status_error(code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.example/v1/chat/completions")
    response = httpx.Response(code, request=request)
    return APIStatusError(f"status {code}", response=response, body=None)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 构造
# ---------------------------------------------------------------------------

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
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "")  # 隔离 embedding 子客户端，避免污染 captured
    client = LLMClient()

    assert client._client is not None
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == settings.LLM_BASE_URL
    # 超时：connect/read 按 §9.1 配置；重试关闭（由本封装统一管理）
    assert captured["max_retries"] == 0
    assert isinstance(captured["timeout"], httpx.Timeout)
    assert captured["timeout"].connect == settings.LLM_CONNECT_TIMEOUT
    assert captured["timeout"].read == settings.LLM_READ_TIMEOUT


# ---------------------------------------------------------------------------
# 可重试判定（§9.1：仅 429 / 5xx / 网络 / 超时）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exc",
    [
        status_error(429),
        status_error(500),
        status_error(503),
        APIConnectionError(request=httpx.Request("POST", "https://x")),
        APITimeoutError(request=httpx.Request("POST", "https://x")),
    ],
)
def test_is_retryable_true(exc):
    assert _is_retryable(exc) is True


@pytest.mark.parametrize("exc", [status_error(400), status_error(401), status_error(404), ValueError("boom")])
def test_is_retryable_false(exc):
    assert _is_retryable(exc) is False


def test_request_fingerprint_stable_and_distinct():
    messages = [{"role": "user", "content": "你好"}]
    assert _request_fingerprint("deepseek-chat", messages) == _request_fingerprint("deepseek-chat", messages)
    assert _request_fingerprint("deepseek-chat", messages) != _request_fingerprint(
        "deepseek-chat", [{"role": "user", "content": "不一样"}]
    )
    assert _request_fingerprint("m1", messages) != _request_fingerprint("m2", messages)


# ---------------------------------------------------------------------------
# chat：正常路径 / Token 计量 / json_mode
# ---------------------------------------------------------------------------

def test_chat_success_json_mode_returns_data_and_usage():
    client, fake = make_client([make_completion('{"score": 9}', prompt_tokens=10, completion_tokens=20)])

    result = run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))

    assert isinstance(result, LLMResult)
    assert result.data == {"score": 9}
    assert result.model == settings.LLM_PRIMARY_MODEL
    assert result.fallback_used is False
    assert result.status == "ok"
    assert result.attempts == 1
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 20
    assert result.usage.total_tokens == 30
    assert result.fingerprint
    assert result.duration_ms >= 0
    assert fake.chat.completions.calls[0]["model"] == settings.LLM_PRIMARY_MODEL


def test_chat_json_mode_passes_response_format():
    client, fake = make_client([make_completion("{}")])
    run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))
    assert fake.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_chat_text_mode_omits_response_format():
    client, fake = make_client([make_completion("plain text")])
    result = run(client.chat([{"role": "user", "content": "hi"}]))
    assert "response_format" not in fake.chat.completions.calls[0]
    assert result.data is None
    assert result.content == "plain text"


def test_chat_usage_none_handled():
    client, _ = make_client([make_completion("{}", usage=None)])
    result = run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))
    assert result.usage.prompt_tokens == 0
    assert result.usage.completion_tokens == 0
    assert result.usage.total_tokens == 0


# ---------------------------------------------------------------------------
# 重试分支（M0-4 验收重点）
# ---------------------------------------------------------------------------

def test_chat_retries_then_succeeds(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.core.llm.client.asyncio.sleep", fake_sleep)

    err = APIConnectionError(request=httpx.Request("POST", "https://x"))
    ok = make_completion('{"score": 8}', model="deepseek-chat")
    client, fake = make_client([err, err, ok])

    result = run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))

    assert result.data == {"score": 8}
    assert result.attempts == 3
    assert result.fallback_used is False
    assert len(fake.chat.completions.calls) == 3
    # 指数退避：0.5s → 1.0s
    assert delays == [0.5, 1.0]


def test_chat_retry_exhaustion_falls_back(monkeypatch):
    async def fake_sleep(delay):
        pass

    monkeypatch.setattr("app.core.llm.client.asyncio.sleep", fake_sleep)

    err = APIConnectionError(request=httpx.Request("POST", "https://x"))
    ok_fallback = make_completion('{"score": 7}', model=settings.LLM_FALLBACK_MODEL)
    # 主模型 4 次（1 + 3 重试）全部失败后，降级备用模型 1 次成功
    client, fake = make_client([err, err, err, err, ok_fallback])

    result = run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))

    assert result.fallback_used is True
    assert result.status == "degraded"
    assert result.model == settings.LLM_FALLBACK_MODEL
    assert result.data == {"score": 7}
    assert result.attempts == 1  # 备用模型一次成功
    models = [c["model"] for c in fake.chat.completions.calls]
    assert models == [settings.LLM_PRIMARY_MODEL] * 4 + [settings.LLM_FALLBACK_MODEL]


def test_chat_both_models_fail_raises(monkeypatch):
    async def fake_sleep(delay):
        pass

    monkeypatch.setattr("app.core.llm.client.asyncio.sleep", fake_sleep)

    err = status_error(500)
    # 主模型 4 次 + 备用模型 4 次全部失败
    client, fake = make_client([err] * 8)

    with pytest.raises(LLMError):
        run(client.chat([{"role": "user", "content": "hi"}]))

    assert len(fake.chat.completions.calls) == 8


def test_chat_non_retryable_no_retry_no_fallback():
    client, fake = make_client([status_error(400)])

    with pytest.raises(LLMError):
        run(client.chat([{"role": "user", "content": "hi"}]))

    # 400 不重试、不降级，仅调用一次
    assert len(fake.chat.completions.calls) == 1


def test_chat_invalid_json_raises_without_fallback():
    client, fake = make_client([make_completion("不是 JSON", model="deepseek-chat")])

    with pytest.raises(LLMError):
        run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))

    # 非法 JSON 属协议层错误，不降级
    assert len(fake.chat.completions.calls) == 1


def test_chat_empty_content_json_mode_raises():
    client, fake = make_client([make_completion("")])
    with pytest.raises(LLMError):
        run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))
    assert len(fake.chat.completions.calls) == 1


def test_chat_non_object_json_raises():
    client, fake = make_client([make_completion('[1, 2, 3]')])
    with pytest.raises(LLMError):
        run(client.chat([{"role": "user", "content": "hi"}], json_mode=True))
    assert len(fake.chat.completions.calls) == 1


def test_chat_no_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    client = LLMClient()
    with pytest.raises(LLMError):
        run(client.chat([{"role": "user", "content": "hi"}]))
