"""简历解析 Prompt 注册表（规范 §9.2：集中管理 + 版本号）。

业务通过 `get_prompt(version=...)` 选版；改 prompt 必须带 version 头并新增版本。
"""
from __future__ import annotations

from app.prompts.resume_parser.v1 import PROMPT_V1, VERSION_V1

_REGISTRY: dict[str, str] = {
    VERSION_V1: PROMPT_V1,
}


def get_prompt(version: str | None = None) -> str:
    """按版本返回 prompt 文本；默认取最新（v1）。"""
    if version is None:
        version = VERSION_V1
    if version not in _REGISTRY:
        raise ValueError(f"unknown prompt version: {version}")
    return _REGISTRY[version]


__all__ = ["get_prompt", "VERSION_V1"]
