"""真题改写合规校验（M4 PR-R5）：改写题与原真题逐字比对（规范 §9.6「禁止照搬」）。"""
from __future__ import annotations

from difflib import SequenceMatcher

# 相似度阈值：改写题与原真题相似度 > 0.95 判违规（M4 计划 §四 PR-R5 / §六）
VERBATIM_THRESHOLD = 0.95


def text_similarity(a: str, b: str) -> float:
    """两段文本相似度（SequenceMatcher ratio，0~1）。"""
    return SequenceMatcher(None, a or "", b or "").ratio()


def is_verbatim(original: str, rewritten: str, threshold: float = VERBATIM_THRESHOLD) -> bool:
    """判断改写题是否照搬原文（相似度超阈值判违规）。"""
    return text_similarity(original, rewritten) > threshold


__all__ = ["VERBATIM_THRESHOLD", "text_similarity", "is_verbatim"]
