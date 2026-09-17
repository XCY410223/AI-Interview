# PR2 · feature/m2-pr2-sse-protocol → base feature/m2-pr1-question-generation

**feat(interview): SSE 结构化评分协议，评分独立事件下发（反污染）**

## 变更清单

- 新增 `app/schemas/interview_event.py`：五类事件 meta/chunk/score/next/error
- 新增 `app/services/interview/sse_emitter.py`：强类型事件 → SSE，评分强制 clamp
- 新增 `app/prompts/interview/answer_evaluation.py`：评语流 + 评分 JSON 两条独立模板
- 扩充 `app/core/llm/client.py`：新增 `chat_stream`
- 扩充 `app/services/interview/ai_service.py`：stream_feedback / evaluate_score
- 扩充 `app/services/interview/service.py`：validate_submit / stream_answer（线性推进）
- 扩充 `app/api/v1/interview.py`：`POST /interviews/{id}/answer`（SSE）
- 新增 `docs/M2-面试引擎-SSE协议.md`

## 测试说明

- `test_sse_emitter.py`（SSE-05/06/11：评分 clamp、维度清洗、序列化格式）
- `test_interview_sse_protocol.py`（SSE-01~04/07，含 **SSE-02 反污染**：回答塞 `{"score":10}` 不污染评分）

`pytest` 178 通过，flake8 / mypy 干净。

## 人工评审重点

- 反污染测试是否真的能失败（核心）
- 评分 JSON 与评语流是否彻底分离（红线 5/7）

🤖 Generated with [Claude Code](https://claude.com/claude-code)
