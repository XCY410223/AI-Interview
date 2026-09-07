"""celery_app 单测：实例名、broker/backend、序列化配置。"""
from app.core.config import settings
from app.tasks.celery_app import celery_app


def test_celery_app_name():
    assert celery_app.main == "ai-interview"


def test_celery_broker_from_settings():
    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL


def test_celery_backend_from_settings():
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND


def test_celery_json_serialization():
    assert celery_app.conf.task_serializer == "json"
    assert "json" in celery_app.conf.accept_content
