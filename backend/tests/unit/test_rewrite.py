"""真题改写合规校验单测（M4 PR-R5）：相似度 / 禁照搬判定。"""
from __future__ import annotations

from app.services.question_bank.rewrite import is_verbatim, text_similarity


def test_text_similarity_identical():
    assert text_similarity("完全相同的文本", "完全相同的文本") == 1.0


def test_text_similarity_different():
    assert text_similarity("如何设计高并发系统", "请谈谈你的职业规划") < 0.5


def test_is_verbatim_flags_copy():
    original = "请描述 Kafka 的消息可靠性机制及其在分布式系统中的应用。"
    assert is_verbatim(original, original) is True  # 照搬原文 → 违规


def test_is_verbatim_allows_rewrite():
    original = "请描述 Kafka 的消息可靠性机制及其在分布式系统中的应用。"
    rewritten = "在你的项目里，如何保证消息队列不丢消息、不重复消费？"
    assert is_verbatim(original, rewritten) is False  # 改写 → 合规
