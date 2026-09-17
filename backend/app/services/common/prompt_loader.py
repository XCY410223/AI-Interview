"""带版本号的 Prompt 加载器（红线 9 / 规范 §9.2，M2 计划 §一/§3.2）。

所有 prompt 模块必须声明非空 `VERSION` 字符串头；加载时校验，缺失即报错，
保证「改 prompt 不升版本」无法静默合入。
"""
from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType


class PromptVersionError(ValueError):
    """Prompt 缺少 version 头或模板为空。"""


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    template: str


def require_version(module: ModuleType) -> str:
    """断言模块存在非空 `VERSION` 版本头，返回版本号。"""
    version = getattr(module, "VERSION", None)
    if not isinstance(version, str) or not version.strip():
        raise PromptVersionError(f"prompt 模块 {getattr(module, '__name__', '?')} 缺少 VERSION 版本头")
    return version.strip()


def load_template(module: ModuleType, attr: str) -> PromptTemplate:
    """加载模块的指定模板常量（带版本头校验）。"""
    version = require_version(module)
    template = getattr(module, attr, None)
    if not isinstance(template, str) or not template.strip():
        raise PromptVersionError(f"prompt 模块 {getattr(module, '__name__', '?')}.{attr} 为空")
    return PromptTemplate(name=module.__name__, version=version, template=template)


__all__ = ["PromptTemplate", "PromptVersionError", "load_template", "require_version"]
