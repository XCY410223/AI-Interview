"""JD 解析 Prompt 注册表（规范 §9.2：集中管理 + 版本号）。

业务通过 `get_prompt(version=...)` 选版；改 prompt 必须带版本头并新增版本。
"""
from __future__ import annotations

from app.prompts.jd_parser.v1 import JD_PARSE_PROMPT, VERSION, wrap_jd_text

_REGISTRY: dict[str, str] = {
    VERSION: JD_PARSE_PROMPT,
}

CURRENT_VERSION = VERSION


def get_prompt(version: str | None = None) -> str:
    """按版本返回 prompt 文本；默认取最新（v1）。"""
    if version is None:
        version = CURRENT_VERSION
    if version not in _REGISTRY:
        raise ValueError(f"unknown prompt version: {version}")
    return _REGISTRY[version]


__all__ = ["CURRENT_VERSION", "VERSION", "get_prompt", "wrap_jd_text"]
