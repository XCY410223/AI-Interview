"""面试历史回放单测（M4 PR-R7-b）：列表 / 详情聚合 / 重评（双 score 共存）。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.common.exceptions import InterviewForbidden, InterviewInvalidState, InterviewNotFound
from app.services.interview.service import InterviewService
from tests.fakes import FakeSession, make_interview, make_interview_message, make_report


def run(coro):
    return asyncio.run(coro)


def test_list_returns_owned_interviews():
    i1 = make_interview(interview_id=2, user_id=1, status="completed")
    i2 = make_interview(interview_id=1, user_id=1, status="created")
    session = FakeSession().configure(scalars=[i1, i2], scalar_one=2)
    total, items = run(InterviewService.list(session, user_id=1))
    assert total == 2
    assert [i.id for i in items] == [2, 1]


def test_build_list_item():
    i = make_interview(interview_id=1, status="completed")
    item = InterviewService.build_list_item(i)
    assert item.interview_id == 1
    assert item.status == "completed"


def test_get_replay_aggregates_questions_messages_report():
    interview = make_interview(
        interview_id=1, user_id=1, status="completed",
        questions_json=[{"question_index": 0, "round": 0, "category": "项目", "content": "题",
                         "reference_points": [], "difficulty": "medium", "source": None}],
    )
    msg = make_interview_message(message_id=10, interview_id=1, question_index=0, round_=0)
    report = make_report(report_id=1, interview_id=1, user_id=1, status="completed",
                         payload_json={"summary": "整体不错"})
    session = FakeSession().configure(
        get_map={1: interview}, scalars=[msg], scalar_one_or_none=report,
    )
    replay = run(InterviewService.get_replay(session, user_id=1, interview_id=1))
    assert replay.interview_id == 1
    assert len(replay.questions) == 1
    assert len(replay.messages) == 1
    assert replay.report_summary == "整体不错"


def test_get_replay_forbidden():
    interview = make_interview(interview_id=1, user_id=2)
    session = FakeSession().configure(get_map={1: interview})
    with pytest.raises(InterviewForbidden):
        run(InterviewService.get_replay(session, user_id=1, interview_id=1))


def test_re_evaluate_appends_new_score_and_keeps_original(monkeypatch):
    interview = make_interview(
        interview_id=1, user_id=1, status="completed",
        questions_json=[{"question_index": 0, "round": 0, "category": "项目", "content": "题",
                         "reference_points": [], "difficulty": "medium", "source": None}],
    )
    answer = make_interview_message(message_id=10, interview_id=1, question_index=0, round_=0,
                                    role="candidate", content="我的回答")
    session = FakeSession().configure(get_map={1: interview}, scalars=[answer])

    async def fake_eval(*, question, answer):
        return SimpleNamespace(score=8.0, dimensions={"completeness": 8.0}, feedback="重新评分")

    monkeypatch.setattr("app.services.interview.service.ai_service.evaluate_score", fake_eval)
    result = run(InterviewService.re_evaluate(session, user_id=1, interview_id=1, question_index=0))
    assert result.score == 8.0
    # 追加的 score message 带 re_evaluated 标记，原 answer/原分不被修改
    added_scores = [m for m in session.added if m.event_type == "score"]
    assert len(added_scores) == 1
    assert added_scores[0].payload_json["re_evaluated"] is True
    assert added_scores[0].payload_json["score"] == 8.0


def test_re_evaluate_no_answer_raises():
    interview = make_interview(
        interview_id=1, user_id=1, status="completed",
        questions_json=[{"question_index": 0, "round": 0, "category": "项目", "content": "题",
                         "reference_points": [], "difficulty": "medium", "source": None}],
    )
    session = FakeSession().configure(get_map={1: interview}, scalars=[])
    with pytest.raises(InterviewInvalidState):
        run(InterviewService.re_evaluate(session, user_id=1, interview_id=1, question_index=0))


def test_re_evaluate_not_found():
    session = FakeSession().configure(get_map={})
    with pytest.raises(InterviewNotFound):
        run(InterviewService.re_evaluate(session, user_id=1, interview_id=1, question_index=0))
