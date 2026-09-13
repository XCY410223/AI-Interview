"""schemas/auth 单测：弱密码（<8 位）与邮箱格式校验（M1 计划 §3.5）。"""
import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest


def test_register_weak_password_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="short")


def test_register_valid():
    r = RegisterRequest(email="a@b.com", password="password123")
    assert r.email == "a@b.com"


def test_register_invalid_email_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="password123")


def test_login_accepts_any_nonempty_password():
    r = LoginRequest(email="a@b.com", password="x")
    assert r.password == "x"
