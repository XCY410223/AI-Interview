"""真题入库管线纯函数（M4 PR-R4）：切片 / 去重 / embedding 维度断言（spec §9.6）。

纯函数无 DB/LLM 依赖，供单测；DB 编排在 tasks/rag.py（Celery 任务），embedding 走统一客户端。
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable

from app.core.config import settings

# 切片窗口（spec §9.6）：300~500 字，优先句读边界
SLICE_MIN = 300
SLICE_MAX = 500

# 去重阈值（spec §9.6）：同 company+position 域内 cosine > 0.92 → 丢弃
DEDUP_THRESHOLD = 0.92

_SENTENCE_END = "。！？；!?;\n"


def slice_text(text: str, *, min_chars: int = SLICE_MIN, max_chars: int = SLICE_MAX) -> list[str]:
    """切片：300~500 字，优先在句号/换行等句读边界切，超长句硬切（§9.6）。"""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # 在 [start+min_chars, end] 内找最后一个句读边界
            boundary = -1
            search_from = min(start + min_chars, end)
            for i in range(end - 1, search_from - 1, -1):
                if text[i] in _SENTENCE_END:
                    boundary = i + 1
                    break
            if boundary != -1:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def content_hash(company: str, position: str, content: str) -> str:
    """幂等键：sha256(company + position + content)（§9.6 溯源/幂等）。"""
    raw = f"{company}\x00{position}\x00{content}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """两向量余弦相似度；空向量/维度不符返回 0（防御）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def should_drop(
    existing_vectors: Iterable[list[float]],
    candidate: list[float],
    threshold: float = DEDUP_THRESHOLD,
) -> bool:
    """与同域既有向量集的最大 cosine 相似度 > 阈值 → 判定丢弃（§9.6 去重）。"""
    return any(cosine_similarity(candidate, existing) > threshold for existing in existing_vectors)


def assert_embedding_dim(vector: list[float]) -> None:
    """维度断言（§十二）：embedding 维度必须与 settings.EMBEDDING_DIM（bge-m3=1024）一致。"""
    if len(vector) != settings.EMBEDDING_DIM:
        raise ValueError(f"embedding 维度不符：期望 {settings.EMBEDDING_DIM}，实际 {len(vector)}")


def batch_chunks(chunks: list[str], size: int | None = None) -> list[list[str]]:
    """按批大小切分（默认 settings.EMBEDDING_BATCH_SIZE ≤32/批，§9.6）。"""
    size = size or settings.EMBEDDING_BATCH_SIZE
    return [chunks[i : i + size] for i in range(0, len(chunks), size)]


__all__ = [
    "SLICE_MIN",
    "SLICE_MAX",
    "DEDUP_THRESHOLD",
    "slice_text",
    "content_hash",
    "cosine_similarity",
    "should_drop",
    "assert_embedding_dim",
    "batch_chunks",
]
