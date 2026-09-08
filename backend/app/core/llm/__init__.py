"""统一 LLM 客户端公共 API（规范 §9.1）：业务代码从这里导入，禁止裸建 client。"""
from app.core.llm.client import (
    LLMClient,
    LLMError,
    LLMResult,
    LLMUsage,
    llm_client,
)

__all__ = ["LLMClient", "LLMError", "LLMResult", "LLMUsage", "llm_client"]
