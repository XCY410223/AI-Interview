"""面试 Prompt 注册（红线 9 / 规范 §9.2）：出题。

所有子模块带 `VERSION` 版本头；改 prompt 必须升版本并在 CHANGELOG.md 登记（M2 计划 §3.2）。
"""
from __future__ import annotations

from app.prompts.interview import question_generation

__all__ = ["question_generation"]
