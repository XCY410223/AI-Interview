"""Waiting List schema（M4 PR-R7-d）：公开订阅（邮箱校验 + 防重防刷）。"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class WaitingListSubscribeRequest(BaseModel):
    email: EmailStr


class WaitingListSubscribeResponse(BaseModel):
    email: str
    already_subscribed: bool = False


__all__ = ["WaitingListSubscribeRequest", "WaitingListSubscribeResponse"]
