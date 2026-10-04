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
    result = _result({"score": 7.0, "dimensions": {"completeness": 8.0}, "feedback": "ok"})
    svc = InterviewAIService(client=FakeLLM([result]))
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
    result = _result({"need_follow_up": True, "follow_up_hint": "细节？", "reason": "缺细节"})
    svc = InterviewAIService(client=FakeLLM([result]))
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


# ---- M4 R2：JD 能力项注入（prompt v2）----
def _cap(**kw):
    base = {"name": "Kafka 消息可靠性", "category": "hard_skill", "keywords": ["Kafka", "消息队列"], "importance": "must"}
    base.update(kw)
    from app.schemas.question_bank import JDCapability

    return JDCapability.model_validate(base)


def test_generate_questions_no_capabilities_equivalent_v1():
    fake = FakeLLM([_result(_questions(3))])
    svc = InterviewAIService(client=fake)
    run(svc.generate_questions(position="后端", difficulty="easy", resume_summary="x", question_count=3))
    system = fake.calls[0]["messages"][0]["content"]
    assert "无 JD 定制" in system  # 无 JD 时注入段为占位，行为等价 v1


def test_generate_questions_injects_capabilities():
    fake = FakeLLM([_result(_questions(3))])
    svc = InterviewAIService(client=fake)
    run(svc.generate_questions(
        position="后端", difficulty="easy", resume_summary="x", question_count=3,
        capabilities=[_cap()],
    ))
    system = fake.calls[0]["messages"][0]["content"]
    assert "Kafka 消息可靠性" in system
    assert "Kafka" in system
    assert "必备" in system  # must → 必备


# ---- M4 R5：真题改写融合 ----
def _real_questions_data(n=2):
    return {"questions": [
        {
            "category": "项目", "content": f"改写真题{i}", "reference_points": ["a", "b"],
            "difficulty": "medium", "source": "字节·https://example.com/x",
        }
        for i in range(n)
    ]}


def _chunk(content="真题原文片段", source_url="https://example.com/x"):
    from app.schemas.question_bank import QuestionBankSearchItem

    return QuestionBankSearchItem(id=1, company="字节", position="后端", difficulty="medium",
                                  content=content, source_url=source_url)


def test_rewrite_real_questions_outputs_source():
    fake = FakeLLM([_result(_real_questions_data(2))])
    svc = InterviewAIService(client=fake)
    qs = run(svc.rewrite_real_questions(
        chunks=[_chunk()], position="后端", difficulty="medium", resume_summary="x", count=2,
    ))
    assert len(qs) == 2
    assert all(q.source == "字节·https://example.com/x" for q in qs)


def test_generate_questions_with_real_fuses_and_reindexes():
    # 2 个真题 chunk → 改写 2 题；剩余 2 题走普通出题 → 共 4 题
    fake = FakeLLM([_result(_real_questions_data(2)), _result(_questions(2))])
    svc = InterviewAIService(client=fake)
    qs = run(svc.generate_questions(
        position="后端", difficulty="medium", resume_summary="x", question_count=4,
        real_questions=[_chunk(), _chunk()],
    ))
    assert len(qs) == 4
    assert [q.question_index for q in qs] == [0, 1, 2, 3]  # 重排连续
    assert qs[0].source == "字节·https://example.com/x"  # 真题题在前，带 source
    assert qs[2].source is None  # 普通题无 source


def test_generate_questions_with_real_rewrite_failure_falls_back():
    # 改写两次失败 → 返回 [] → 全部走普通出题
    fake = FakeLLM([LLMError("bad"), LLMError("bad"), _result(_questions(3))])
    svc = InterviewAIService(client=fake)
    qs = run(svc.generate_questions(
        position="后端", difficulty="medium", resume_summary="x", question_count=3,
        real_questions=[_chunk()],
    ))
    assert len(qs) == 3
    assert all(q.source is None for q in qs)
