"""Celery 应用实例（规范 §3.3/§10）。

worker 与 beat 分离部署；任务幂等、time_limit/soft_time_limit、完成后回写 DB 状态。
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai-interview",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    # 任务级超时与重试在各自 task 上声明（规范 §10.2）
)

celery_app.autodiscover_tasks(["app.tasks"])
