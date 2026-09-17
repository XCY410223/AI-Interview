"""追问状态机单测：≤3 轮追问、双键推进、快速翻页、结束判定（FS-01~05/09）。"""
from __future__ import annotations

import pytest

from app.services.interview.state_machine import decide_next


def test_round0_complete_answer_advances():
    a = decide_next(question_index=0, round_=0, need_follow_up=False, score=8.0, total_questions=8)
    assert a.kind == "next_question"
    assert a.question_index == 1
    assert a.round == 0


def test_round0_vague_answer_follows_up():
    a = decide_next(question_index=0, round_=0, need_follow_up=True, score=6.0, total_questions=8)
    assert a.kind == "follow_up"
    assert a.question_index == 0
    assert a.round == 1


def test_round1_vague_answer_follows_up_again():
    a = decide_next(question_index=0, round_=1, need_follow_up=True, score=6.0, total_questions=8)
    assert a.kind == "follow_up"
    assert a.round == 2


def test_round3_forces_next_even_if_follow_up():
    a = decide_next(question_index=0, round_=3, need_follow_up=True, score=6.0, total_questions=8)
    assert a.kind == "next_question"
    assert a.question_index == 1
    assert a.round == 0


def test_low_score_fast_forwards():
    a = decide_next(question_index=0, round_=0, need_follow_up=True, score=2.0, total_questions=8)
    assert a.kind == "next_question"
    assert a.question_index == 1


def test_last_question_done():
    a = decide_next(question_index=7, round_=0, need_follow_up=False, score=8.0, total_questions=8)
    assert a.kind == "done"


def test_follow_up_last_question_then_done():
    a = decide_next(question_index=7, round_=0, need_follow_up=True, score=6.0, total_questions=8)
    assert a.kind == "follow_up"


def test_negative_round_raises():
    with pytest.raises(ValueError):
        decide_next(question_index=0, round_=-1, need_follow_up=False, score=8.0, total_questions=8)
