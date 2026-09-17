"""追问状态机（M2-PR3）：每题 ≤3 轮追问，question_index + round 双键推进。

转移规则（M2 计划 §二 PR3）：
- 评分 ≤3.0 → 快速翻页（不追问，直接下一题）；
- round ≥3 → 强制进入下一题（兜底，最多 3 轮追问）；
- need_follow_up=True 且未达上限 → 同题 round+1；
- 否则 → 下一题（question_index+1，round 归零）；
- 总题数耗尽 → done（INTERVIEW_DONE）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 每题追问轮数上限（红线 / M2 计划）
FOLLOW_UP_MAX_ROUND = 3
# 评分 ≤ 该阈值 → 快速翻页（不追问）
FAST_FORWARD_SCORE_THRESHOLD = 3.0

ActionKind = Literal["follow_up", "next_question", "done"]


@dataclass(frozen=True)
class NextAction:
    kind: ActionKind
    question_index: int
    round: int


def decide_next(
    *,
    question_index: int,
    round_: int,
    need_follow_up: bool,
    score: float,
    total_questions: int,
) -> NextAction:
    """根据当前回答的评分与追问信号，决定下一步（追问 / 下一题 / 结束）。"""
    if round_ < 0:
        raise ValueError("round 不能为负数")
    if round_ >= FOLLOW_UP_MAX_ROUND or score <= FAST_FORWARD_SCORE_THRESHOLD:
        return _advance(question_index, total_questions)
    if need_follow_up:
        return NextAction(kind="follow_up", question_index=question_index, round=round_ + 1)
    return _advance(question_index, total_questions)


def _advance(question_index: int, total_questions: int) -> NextAction:
    nxt = question_index + 1
    if nxt >= total_questions:
        return NextAction(kind="done", question_index=question_index, round=0)
    return NextAction(kind="next_question", question_index=nxt, round=0)


__all__ = [
    "FOLLOW_UP_MAX_ROUND",
    "FAST_FORWARD_SCORE_THRESHOLD",
    "NextAction",
    "decide_next",
]
