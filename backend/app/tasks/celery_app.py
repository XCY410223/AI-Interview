"""Celery 应用实例（规范 §3.3/§10）。

worker 与 beat 分离部署；任务幂等、time_limit/soft_time_limit、完成后回写 DB 状态。
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai-interview",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # 显式 include 注册任务模块。
    # 注意：不能用 autodiscover_tasks(["app.tasks"])——autodiscover 按
    # "<pkg>.<related_name>"（默认 related_name="tasks"）查找，会去找
    # app.tasks.tasks 这个不存在的模块，导致 worker 注册表为空，
    # 任务被丢弃（"Received unregistered task of type 'resume.parse'"）。
    # 新增任务模块（email/report/rag）时在此同步追加。
    include=[
        "app.tasks.resume_parser",
        "app.tasks.report",
    ],
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
