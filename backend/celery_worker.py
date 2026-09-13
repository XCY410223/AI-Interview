"""Celery Worker 入口（独立进程，规范 §3.3/§10）。"""
from app.tasks.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()
