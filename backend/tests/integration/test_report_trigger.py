"""面试结束自动触发报告（M3 计划 §七/§十二）：done 分支建 pending 行 + 投递任务。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.models.interview import INTERVIEW_STATUS_COMPLETED
from app.models.report import REPORT_STATUS_PENDING, Report
from app.services.interview.service import InterviewService
from tests.fakes import FakeAIService, FakeSession, make_interview


def _one_question_interview():
    return make_interview(
        interview_id=1,
        user_id=1,
        question_count=1,
        status="created",
        current_question_index=0,
        current_round=0,
        questions_json=[
            {"question_index": 0, "round": 0, "category": "项目", "content": "介绍你最复杂的项目",
             "reference_points": ["技术选型", "难点"], "difficulty": "medium"}
        ],
    )


def test_interview_done_triggers_report(monkeypatch):
    interview = _one_question_interview()
    db = FakeSession().configure(get_map={1: interview})

    ai = FakeAIService()
    ai.score = SimpleNamespace(
        score=8.0,
        dimensions={"completeness": 8, "accuracy": 8, "depth": 8, "clarity": 8},
        feedback="不错",
    )
    ai.followup = SimpleNamespace(need_follow_up=False, follow_up_hint="", reason="回答完整")
    monkeypatch.setattr("app.services.interview.service.ai_service", ai)

    enqueued: list[int] = []
    monkeypatch.setattr(
        "app.services.report.service.ReportService.enqueue",
        lambda report_id: enqueued.append(report_id) or "task-1",
    )

    async def consume():
        async for _ in InterviewService.stream_answer(db, interview=interview, content="我的回答", round_=0):
            pass

    asyncio.run(consume())

    assert interview.status == INTERVIEW_STATUS_COMPLETED
    reports = [o for o in db.added if isinstance(o, Report)]
    assert len(reports) == 1
    assert reports[0].interview_id == 1
    assert reports[0].status == REPORT_STATUS_PENDING
    assert enqueued == [reports[0].id]
