"""弱项练习 Prompt 注册表（规范 §9.2：集中管理 + 版本号）。"""
from __future__ import annotations

from app.prompts.practice.v1 import PRACTICE_GENERATION_PROMPT, VERSION

_REGISTRY: dict[str, str] = {
    VERSION: PRACTICE_GENERATION_PROMPT,
}

CURRENT_VERSION = VERSION


def get_prompt(version: str | None = None) -> str:
    if version is None:
        version = CURRENT_VERSION
    if version not in _REGISTRY:
        raise ValueError(f"unknown prompt version: {version}")
    return _REGISTRY[version]


__all__ = ["CURRENT_VERSION", "VERSION", "get_prompt"]
