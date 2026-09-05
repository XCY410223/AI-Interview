"""健康检查路由：GET /health（返回 DB/Redis 状态，规范 §15）。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # 生产环境应返回 DB/Redis 探活结果；骨架阶段先返回静态状态
    return {"status": "ok"}
