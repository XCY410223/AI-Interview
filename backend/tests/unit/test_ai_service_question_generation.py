"""AI 编排单测：出题 / 评分 / 追问决策（QG-01~06 / SSE-04/12），全 mock，不触网。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.core.llm.client import LLMError
from app.schemas.interview import QuestionItem
from app.services.interview.ai_service import FALLBACK_SCORE, InterviewAIService
from app.services.interview.style_resolver import resolve_style


def _result(data=None, content=""):
    return SimpleNamespace(data=data, content=content, model="deepseek-chat")


def _questions(n: int) -> dict:
    return {"questions": [
        {"category": "项目", "content": f"题{i}", "reference_points": ["a", "b", "c"], "difficulty": "medium"}
        for i in range(n)
    ]}


def _q() -> QuestionItem:
    return QuestionItem(question_index=0, category="项目", content="介绍你的项目",
                        reference_points=["技术选型", "难点"], difficulty="medium")


class FakeLLM:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def chat(self, messages, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def run(coro):
    return asyncio.run(coro)


def test_generate_questions_normal():
    svc = InterviewAIService(client=FakeLLM([_result(_questions(8))]))
    qs = run(svc.generate_questions(position="后端", difficulty="easy", resume_summary="有经验", question_count=8))
    assert len(qs) == 8
    assert all(isinstance(q, QuestionItem) for q in qs)
    assert qs[0].question_index == 0 and qs[0].round == 0


def test_generate_questions_empty_resume_no_raise():
    svc = InterviewAIService(client=FakeLLM([_result(_questions(3))]))
    qs = run(svc.generate_questions(position="后端", difficulty="easy", resume_summary="", question_count=3))
    assert len(qs) == 3


def test_generate_questions_max_count_15():
    svc = InterviewAIService(client=FakeLLM([_result(_questions(15))]))
    qs = run(svc.generate_questions(position="后端", difficulty="easy", resume_summary="", question_count=15))
    assert len(qs) == 15


def test_generate_questions_retry_then_success():
    fake = FakeLLM([LLMError("bad json"), _result(_questions(4))])
    svc = InterviewAIService(client=fake)
    qs = run(svc.generate_questions(position="后端", difficulty="easy", resume_summary="x", question_count=4))
    assert len(qs) == 4
    assert len(fake.calls) == 2


def test_generate_questions_fallback_after_two_failures():
    fake = FakeLLM([LLMError("bad"), LLMError("bad")])
    svc = InterviewAIService(client=fake)
    qs = run(svc.generate_questions(position="后端", difficulty="easy", resume_summary="x", question_count=5))
    assert len(qs) == 5
    assert all(q.category and q.content for q in qs)


def test_evaluate_score_ok():
    svc = InterviewAIService(client=FakeLLM([_result({"score": 7.0, "dimensions": {"completeness": 8.0}, "feedback": "ok"})]))
    score = run(svc.evaluate_score(question=_q(), answer="我的项目用了 Django"))
    assert score.score == 7.0
    assert score.dimensions == {"completeness": 8.0}


def test_evaluate_score_missing_dimensions_ok():
    svc = InterviewAIService(client=FakeLLM([_result({"score": 7.0, "feedback": "ok"})]))
    score = run(svc.evaluate_score(question=_q(), answer="y"))
    assert score.score == 7.0
    assert score.dimensions == {}


def test_evaluate_score_fallback_after_two_failures():
    svc = InterviewAIService(client=FakeLLM([LLMError("bad"), LLMError("bad")]))
    score = run(svc.evaluate_score(question=_q(), answer="y"))
    assert score.score == FALLBACK_SCORE == 5.0
    assert score.dimensions == {}


def test_decide_follow_up_true():
    svc = InterviewAIService(client=FakeLLM([_result({"need_follow_up": True, "follow_up_hint": "细节？", "reason": "缺细节"})]))
    d = run(svc.decide_follow_up(question=_q(), answer_history=["x"], current_round=0, style=resolve_style("friendly")))
    assert d.need_follow_up is True
    assert d.follow_up_hint == "细节？"


def test_decide_follow_up_fallback():
    svc = InterviewAIService(client=FakeLLM([LLMError("bad"), LLMError("bad")]))
    d = run(svc.decide_follow_up(question=_q(), answer_history=["x"], current_round=0, style=resolve_style("friendly")))
    assert d.need_follow_up is False


def test_stream_feedback_uses_chat_stream():
    class StreamingLLM(FakeLLM):
        async def chat_stream(self, messages):
            for piece in ["你", "不错"]:
                yield piece

    svc = InterviewAIService(client=StreamingLLM([_result(_questions(1))]))

    async def collect():
        return [p async for p in svc.stream_feedback(question=_q(), answer="y", style=resolve_style("friendly"))]

    assert asyncio.run(collect()) == ["你", "不错"]


def test_stream_feedback_falls_back_to_chunking():
    content = "回答不错，有深度，技术选型合理，但是对性能瓶颈的分析还可以更深入一些。"
    svc = InterviewAIService(client=FakeLLM([_result(content=content)]))

    async def collect():
        return [p async for p in svc.stream_feedback(question=_q(), answer="y", style=resolve_style("friendly"))]

    pieces = asyncio.run(collect())
    assert "".join(pieces) == content
    assert len(pieces) > 1
