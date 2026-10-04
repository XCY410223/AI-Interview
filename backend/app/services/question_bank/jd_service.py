"""JD 解析服务（M4-PR1）：JD 原文 → 能力项清单。

- 走统一 LLM 客户端（红线 6），json_mode + Pydantic 校验（红线 5）；
- 用户 JD 文本包进分隔符，指令只信任 system 段（§9.4 注入防护）；
- LLM 失败 / 返回非法 JSON / 校验失败 → QuestionBankParseError（422，提示重贴）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.common.exceptions import QuestionBankParseError
from app.core.llm.client import LLMClient, LLMError, llm_client
from app.prompts.jd_parser import get_prompt, wrap_jd_text
from app.schemas.question_bank import JDCapability, JDParseResponse

logger = logging.getLogger(__name__)


def _parse_capabilities(raw: Any) -> list[JDCapability]:
    """逐项 Pydantic 校验能力项；任一非法 → ValueError（上层转 422）。"""
    if not isinstance(raw, list):
        raise ValueError("capabilities 非数组")
    items = [JDCapability.model_validate(item) for item in raw]
    if not (5 <= len(items) <= 15):
        raise ValueError(f"能力项数量越界：{len(items)}（须 5~15）")
    return items


async def parse_jd(jd_text: str, *, client: LLMClient | None = None) -> JDParseResponse:
    """调用统一 LLM 客户端解析 JD 为能力项清单。失败统一抛 QuestionBankParseError。"""
    client = client if client is not None else llm_client

    messages = [
        {"role": "system", "content": get_prompt()},
        {"role": "user", "content": wrap_jd_text(jd_text)},
    ]
    try:
        result = await client.chat(messages, json_mode=True)
        data = result.data or {}
        capabilities = _parse_capabilities(data.get("capabilities"))
    except (LLMError, ValueError, TypeError) as exc:
        logger.warning("JD 解析失败: %s", exc)
        raise QuestionBankParseError() from exc

    position_guess = str(data.get("position_guess") or "").strip() or "未知岗位"
    return JDParseResponse(
        position_guess=position_guess,
        capabilities=capabilities,
        parsed_at=datetime.now(timezone.utc),
    )


__all__ = ["parse_jd"]
