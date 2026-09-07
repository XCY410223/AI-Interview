"""exceptions 单测：AppError 默认值/覆盖、子类状态码。"""
import pytest

from app.common.exceptions import AIOverloadError, AITimeoutError, AppError


def test_app_error_defaults():
    err = AppError()
    assert err.code == "INTERNAL_ERROR"
    assert err.message == "服务内部错误"
    assert err.http_status == 500


def test_app_error_overrides():
    err = AppError(message="超时了", code="AI_TIMEOUT")
    assert err.message == "超时了"
    assert err.code == "AI_TIMEOUT"


def test_ai_timeout_error():
    err = AITimeoutError()
    assert err.code == "AI_TIMEOUT"
    assert err.http_status == 503


def test_ai_overload_error():
    err = AIOverloadError()
    assert err.code == "AI_OVERLOAD"
    assert err.http_status == 503


def test_app_error_is_exception():
    with pytest.raises(AppError):
        raise AppError("boom")
