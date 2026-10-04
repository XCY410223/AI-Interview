"""路由注册（registry）：集中注册各模块路由，便于重复路由检测（规范 §6.2）。

红线：禁止同一 path+method 重复注册；新增路由前先 grep 现有路由。
"""
from fastapi import APIRouter

from app.api.v1 import auth, health, interview, practice, question_bank, report, resume

api_router = APIRouter()

# 各模块按业务 tag 分组（规范 §8.1），统一前缀 /api/v1 由 main.py 挂载
api_router.include_router(health.router, tags=["健康检查"])
api_router.include_router(auth.router, prefix="/auth", tags=["账户"])
api_router.include_router(resume.router, prefix="/resumes", tags=["简历"])
api_router.include_router(interview.router, prefix="/interviews", tags=["面试"])
api_router.include_router(question_bank.router, prefix="/question-bank", tags=["题库"])
api_router.include_router(report.router, prefix="/reports", tags=["报告"])
api_router.include_router(practice.router, prefix="/practice", tags=["专项练习"])
