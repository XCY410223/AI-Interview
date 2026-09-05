"""通用 schema：统一响应与分页（规范 §6.3/§8.1）。

统一响应：{"code", "message", "data"}；分页：{"total", "items"}，page_size 上限 100。
"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None


class Page(BaseModel, Generic[T]):
    total: int
    items: list[T]
