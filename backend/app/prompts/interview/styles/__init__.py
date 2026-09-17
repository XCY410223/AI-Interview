"""面试官风格 Prompt 注册（M2-PR4）：friendly / stress / deep。

每个风格文件定义三个常量（system/followup_tone/feedback_tone），由 style_resolver 拼接到主 prompt。
"""
from __future__ import annotations

from app.prompts.interview.styles import deep, friendly, stress

STYLES = {"friendly": friendly, "stress": stress, "deep": deep}

__all__ = ["STYLES", "friendly", "stress", "deep"]
