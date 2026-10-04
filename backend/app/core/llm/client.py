"""统一 LLM 客户端（规范 §9.1）——所有模型调用必须走这里，禁止在业务代码裸建 client。

要求（§9.1）：
- 超时：connect 5s / read 60s / 总超时 120s；
- 重试：指数退避重试 3 次，仅对 429 / 5xx / 网络 / 超时 错误；
- 降级：主模型失败自动降级备用模型（deepseek-chat → deepseek-reasoner）；
- Token 统计：每次调用记录 prompt/completion tokens（供成本分析）；
- 审计：每次调用记录 model、请求指纹、耗时、结果状态、尝试次数。

实现要点：
- 使用 AsyncOpenAI，兼容 DeepSeek/通义等 OpenAI 协议；
- 关闭 SDK 内置重试（max_retries=0），重试由本封装统一管理，保证"仅可重试错误才重试"的边界；
- 非可重试错误（4xx 业务错误、非法 JSON 等）不重试、不降级，直接抛出，交由上层按 §9.3 处理。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# 指数退避基数（秒）：0.5 → 1 → 2 → ...（规范 §9.1）
_BACKOFF_BASE_SECONDS = 0.5


@dataclass
class LLMUsage:
    """Token 计量（规范 §9.1）：prompt/completion tokens，供成本分析。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResult:
    """一次 LLM 调用的完整结果：内容 + 结构化数据 + 计量 + 审计。"""

    content: str
    model: str
    usage: LLMUsage
    fingerprint: str
    duration_ms: int
    attempts: int
    fallback_used: bool = False
    status: str = "ok"  # ok / degraded（触发降级）
    data: dict | None = None  # json_mode 时解析出的顶层 JSON 对象


class LLMError(Exception):
    """LLM 调用最终失败（未配置、主/备模型均不可用、返回非法 JSON 等）。"""


def _is_retryable(exc: BaseException) -> bool:
    """规范 §9.1：仅 429 / 5xx / 网络 / 超时 可重试；其余（4xx 业务错误等）不重试。"""
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def _request_fingerprint(model: str, messages: list[dict]) -> str:
    """请求指纹（规范 §9.1 审计）：model + messages 的稳定哈希。"""
    payload = json.dumps(
        {"model": model, "messages": messages}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class LLMClient:
    """统一封装：超时 / 重试 / 降级 / Token 计量 / 审计。

    `client` 参数用于测试注入 fake AsyncOpenAI；不传时按 settings 构建真实客户端。
    """

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        embedding_client: Any | None = None,
    ) -> None:
        self._client = client if client is not None else self._build_client()
        # embedding 走独立端点（EMBEDDING_BASE_URL/API_KEY），与 LLM 分离；测试可注入 fake
        self._embedding_client = embedding_client if embedding_client is not None else self._build_embedding_client()

    def _build_client(self) -> AsyncOpenAI | None:
        if not settings.LLM_API_KEY:
            return None
        return AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=self._timeout(),
            max_retries=0,  # 重试由本封装统一管理（指数退避 + 仅限可重试错误）
        )

    def _build_embedding_client(self) -> AsyncOpenAI | None:
        """构建 OpenAI 兼容 embeddings 客户端（bge-m3）；未配置 BASE_URL 返回 None（快速失败）。"""
        if not settings.EMBEDDING_BASE_URL:
            return None
        return AsyncOpenAI(
            api_key=settings.EMBEDDING_API_KEY or "not-set",
            base_url=settings.EMBEDDING_BASE_URL,
            timeout=self._timeout(),
            max_retries=0,
        )

    @staticmethod
    def _timeout() -> httpx.Timeout:
        """connect 5s / read 60s / 总超时 120s（规范 §9.1）。"""
        return httpx.Timeout(
            connect=settings.LLM_CONNECT_TIMEOUT,
            read=settings.LLM_READ_TIMEOUT,
            write=settings.LLM_READ_TIMEOUT,
            pool=settings.LLM_CONNECT_TIMEOUT,
        )

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """指数退避：0.5s → 1s → 2s → ...（attempt 为 0 起）。"""
        return _BACKOFF_BASE_SECONDS * (2 ** attempt)

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        json_mode: bool = False,
    ) -> LLMResult:
        """发起一次对话调用：默认走主模型，主模型不可用时降级备用模型（§9.1）。

        返回 LLMResult；最终失败抛 LLMError。
        """
        primary = model or settings.LLM_PRIMARY_MODEL
        models = [primary]
        if settings.LLM_FALLBACK_MODEL and settings.LLM_FALLBACK_MODEL != primary:
            models.append(settings.LLM_FALLBACK_MODEL)

        last_error: BaseException | None = None
        for index, current_model in enumerate(models):
            try:
                result = await self._call_with_retry(
                    messages, model=current_model, json_mode=json_mode, fallback=index > 0
                )
            except LLMError:
                # 未配置 / 非法 JSON 等协议层错误：换模型无意义，直接抛出
                raise
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc):
                    raise LLMError(f"LLM 调用失败（{current_model}）: {exc}") from exc
                logger.warning("LLM 模型 %s 不可用，尝试降级: %s", current_model, exc)
                continue
            self._audit(result)
            return result

        raise LLMError(f"LLM 主/备模型均不可用: {last_error}") from last_error

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """流式调用（评语流，规范 §8.2）：逐 token 产出内容片段。

        与 chat() 的区别：不重试、不降级——流式中途失败无法安全重放，
        网络/超时错误直接抛 LLMError，由上层转 error 事件（§8.2）。
        """
        client = self._client
        if client is None:
            raise LLMError("LLM 未配置（缺少 LLM_API_KEY）")
        current = model or settings.LLM_PRIMARY_MODEL
        try:
            kwargs: dict[str, Any] = {"model": current, "messages": messages, "stream": True}
            stream = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"LLM 流式调用失败（{current}）: {exc}") from exc
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = (getattr(delta, "content", None) or "") if delta else ""
            if content:
                yield content

    async def embed_texts(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """批量 embedding（OpenAI 兼容 embeddings API，EMBEDDING_MODEL 驱动，红线 6 统一客户端扩展）。

        - 未配置 EMBEDDING_BASE_URL → LLMError（快速失败，§十二）；
        - 仅可重试错误（429/5xx/网络/超时）指数退避重试；
        - 返回按输入顺序排列的向量列表（按返回 index 排序，数量不符判失败）。
        """
        if not texts:
            return []
        client = self._embedding_client
        if client is None:
            raise LLMError("embedding 未配置（缺少 EMBEDDING_BASE_URL）")
        current = model or settings.EMBEDDING_MODEL
        last_error: BaseException | None = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                resp = await client.embeddings.create(model=current, input=list(texts))
                data = sorted((getattr(resp, "data", None) or []), key=lambda d: getattr(d, "index", 0))
                vectors = [list(getattr(d, "embedding", None) or []) for d in data]
                if len(vectors) != len(texts) or any(not v for v in vectors):
                    raise LLMError(f"embedding 返回向量数量不符（{current}）")
                return vectors
            except LLMError:
                raise
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc) or attempt >= settings.LLM_MAX_RETRIES:
                    raise LLMError(f"embedding 调用失败（{current}）: {exc}") from exc
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "embedding 调用失败（%s 第 %d 次尝试）: %s；%.2fs 后重试",
                    current, attempt + 1, exc, delay,
                )
                await asyncio.sleep(delay)
        raise LLMError(f"embedding 调用失败（{current}）: {last_error}") from last_error  # pragma: no cover

    async def _call_with_retry(
        self,
        messages: list[dict],
        *,
        model: str,
        json_mode: bool,
        fallback: bool,
    ) -> LLMResult:
        client = self._client
        if client is None:
            raise LLMError("LLM 未配置（缺少 LLM_API_KEY）")

        max_retries = settings.LLM_MAX_RETRIES
        fingerprint = _request_fingerprint(model, messages)
        last_error: BaseException | None = None

        for attempt in range(max_retries + 1):  # 1 次原始 + max_retries 次重试
            attempts = attempt + 1
            start = time.perf_counter()
            try:
                completion = await self._create(client, messages, model=model, json_mode=json_mode)
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc) or attempt >= max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "LLM 调用失败（%s 第 %d 次尝试）: %s；%.2fs 后重试",
                    model, attempts, exc, delay,
                )
                await asyncio.sleep(delay)
                continue
            return self._build_result(
                completion,
                model=model,
                json_mode=json_mode,
                fingerprint=fingerprint,
                start=start,
                attempts=attempts,
                fallback=fallback,
            )

        # 防御性兜底：正常配置下循环内必 return 或 raise，此分支仅在 max_retries 为负等异常配置时可达
        raise LLMError(f"LLM 调用失败（{model}）: {last_error}") from last_error  # pragma: no cover

    @staticmethod
    async def _create(client: AsyncOpenAI, messages: list[dict], *, model: str, json_mode: bool):
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return await client.chat.completions.create(**kwargs)

    @staticmethod
    def _build_result(
        completion: Any,
        *,
        model: str,
        json_mode: bool,
        fingerprint: str,
        start: float,
        attempts: int,
        fallback: bool,
    ) -> LLMResult:
        duration_ms = int((time.perf_counter() - start) * 1000)

        choices = getattr(completion, "choices", None) or []
        content = ""
        if choices:
            message = getattr(choices[0], "message", None)
            content = (getattr(message, "content", None) or "") if message else ""

        data: dict | None = None
        if json_mode:
            if not content:
                raise LLMError(f"LLM 返回空内容（{model}）")
            try:
                parsed = json.loads(content)
            except (json.JSONDecodeError, TypeError) as exc:
                raise LLMError(f"LLM 返回非法 JSON（{model}）: {exc}") from exc
            if not isinstance(parsed, dict):
                raise LLMError(f"LLM JSON 顶层非对象（{model}）")
            data = parsed

        usage_obj = getattr(completion, "usage", None)
        usage = LLMUsage(
            prompt_tokens=(usage_obj.prompt_tokens or 0) if usage_obj else 0,
            completion_tokens=(usage_obj.completion_tokens or 0) if usage_obj else 0,
            total_tokens=(usage_obj.total_tokens or 0) if usage_obj else 0,
        )

        return LLMResult(
            content=content,
            model=model,
            usage=usage,
            fingerprint=fingerprint,
            duration_ms=duration_ms,
            attempts=attempts,
            fallback_used=fallback,
            status="degraded" if fallback else "ok",
            data=data,
        )

    @staticmethod
    def _audit(result: LLMResult) -> None:
        """审计日志（规范 §9.1）：model、请求指纹、耗时、结果状态、Token。"""
        logger.info(
            "LLM audit model=%s status=%s tokens=%s/%s duration_ms=%s attempts=%s fingerprint=%s",
            result.model,
            result.status,
            result.usage.prompt_tokens,
            result.usage.completion_tokens,
            result.duration_ms,
            result.attempts,
            result.fingerprint,
        )


llm_client = LLMClient()
