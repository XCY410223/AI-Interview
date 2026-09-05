"""统一 LLM 客户端（规范 §9.1）——所有模型调用必须走这里，禁止在业务代码裸建 client。

要求：超时(connect 5s / read 60s / total 120s)、指数退避重试 3 次(仅 429/5xx/网络错误)、
主模型失败自动降级备用模型、Token 计量、调用审计。
使用 AsyncOpenAI，兼容 DeepSeek/通义等 OpenAI 协议。
"""
from openai import AsyncOpenAI

from app.core.config import settings


class LLMClient:
    """统一封装；M0-4 落地超时/重试/降级/token 计量分支。"""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TOTAL_TIMEOUT,
        )

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        json_mode: bool = False,
    ) -> dict:
        """结构化输出调用：默认走主模型，失败按 §9.1 降级。"""
        raise NotImplementedError("M0-4 实现：超时/重试/降级/token 计量")


llm_client = LLMClient()
