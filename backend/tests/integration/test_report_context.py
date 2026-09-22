"""面试→报告只读契约 load_for_report 单测（M3 计划 §九）：answer/score 配对 + 质量均值 + 归属。"""
from __future__ import annotations

import asyncio

from app.services.interview.service import InterviewService
from tests.fakes import FakeSession, make_interview, make_interview_message, make_resume


def run(coro):
    return asyncio.run(coro)


def _two_question_interview():
    return make_interview(
        interview_id=1,
        user_id=1,
        question_count=2,
        resume_id=5,
        questions_json=[
            {"question_index": 0, "round": 0, "category": "项目", "content": "介绍项目",
             "reference_points": ["技术选型"], "difficulty": "medium"},
            {"question_index": 1, "round": 0, "category": "知识", "content": "解释索引",
             "reference_points": ["B+树"], "difficulty": "medium"},
        ],
    )


def test_load_for_report_pairs_answer_and_score():
    interview = _two_question_interview()
    resume = make_resume(resume_id=5, user_id=1)
    resume.parsed_content = {"summary": "3年后端"}
    answer = make_interview_message(
        message_id=1, interview_id=1, question_index=0, round_=0,
        role="candidate", content="我的回答", event_type="answer",
    )
    score = make_interview_message(
        message_id=2, interview_id=1, question_index=0, round_=0,
        role="interviewer", content="不错", event_type="score",
        payload_json={"score": 8.0, "dimensions": {"completeness": 8, "accuracy": 8, "depth": 8, "clarity": 8}},
    )
    db = FakeSession().configure(get_map={1: interview, 5: resume}, scalars=[answer, score])

    ctx = run(InterviewService.load_for_report(db, interview_id=1, user_id=1))

    assert ctx is not None
    assert ctx.position == "后端工程师"
    assert ctx.resume_summary == "3年后端"
    assert len(ctx.turns) == 1
    turn = ctx.turns[0]
    assert turn.question == "介绍项目"
    assert turn.answer == "我的回答"
    assert turn.score == 8.0
    assert turn.dimensions == {"completeness": 8.0, "accuracy": 8.0, "depth": 8.0, "clarity": 8.0}
    assert ctx.answer_quality_avg == 8.0


def test_load_for_report_returns_none_for_non_owner():
    interview = make_interview(interview_id=1, user_id=2)
    db = FakeSession().configure(get_map={1: interview})
    assert run(InterviewService.load_for_report(db, interview_id=1, user_id=1)) is None


def test_load_for_report_returns_none_for_missing():
    db = FakeSession().configure(get_map={})
    assert run(InterviewService.load_for_report(db, interview_id=999, user_id=1)) is None
