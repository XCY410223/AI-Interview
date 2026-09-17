"""AI 编排单测：出题（QG-01~06），全 mock，不触网。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.core.llm.client import LLMError
from app.schemas.interview import QuestionItem
from app.services.interview.ai_service import InterviewAIService


def _result(data=None, content=""):
    return SimpleNamespace(data=data, content=content, model="deepseek-chat")


def _questions(n: int) -> dict:
    return {"questions": [
        {"category": "项目", "content": f"题{i}", "reference_points": ["a", "b", "c"], "difficulty": "medium"}
        for i in range(n)
    ]}


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
