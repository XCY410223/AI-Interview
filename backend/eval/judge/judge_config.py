"""Judge 配置锁死（红线 + 规范 §9.7）。

评估 judge 固定为 DeepSeek + temperature=0；改 judge 必须重跑全量基线，否则分数不可比。
统一 LLM 客户端当前由 settings 驱动模型，此处配置为回归脚本的记录/审计基线。
"""
from __future__ import annotations

JUDGE_CONFIG = {
    "model": "deepseek-chat",
    "temperature": 0.0,  # 锁死
    "max_tokens": 2000,
    "response_format": {"type": "json_object"},
}

__all__ = ["JUDGE_CONFIG"]
