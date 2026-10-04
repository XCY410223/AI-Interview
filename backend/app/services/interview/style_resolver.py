"""风格参数 → Prompt 拼接（M2-PR4）：friendly/stress/deep → 三个 tone 片段。

接口签名零变更：style 仅影响 prompt 拼接，不改变路由（M2 计划 §二 PR4）。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.prompts.interview.styles import STYLES
from app.services.common.prompt_loader import require_version


@dataclass(frozen=True)
class StylePrompts:
    system_prompt: str
    followup_tone: str
    feedback_tone: str


def resolve_style(style: str) -> StylePrompts:
    """按风格名解析三个 tone 片段；非法风格抛 ValueError（Pydantic 已拦截，兜底）。"""
    module = STYLES.get(style)
    if module is None:
        raise ValueError(f"unknown style: {style}")
    require_version(module)  # SS-07：风格 prompt 必须带版本头
    return StylePrompts(
        system_prompt=module.STYLE_SYSTEM_PROMPT,
        followup_tone=module.STYLE_FOLLOWUP_TONE,
        feedback_tone=module.STYLE_FEEDBACK_TONE,
    )


__all__ = ["StylePrompts", "resolve_style"]
