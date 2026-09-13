"""结构化日志配置（JSON Lines，规范 §13）。

关键业务事件（登录/上传/任务状态变更）必须埋点，且带 request_id 贯穿检索。
request_id 由 main.py 的全局中间件写入 ContextVar，本模块提供读取辅助。
"""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "request_id": request_id_var.get(),
            "event": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            entry.update(extra)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """装配 JSON Lines 根日志（幂等：重复调用覆盖 handler）。"""
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.handlers = [handler]
