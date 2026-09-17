# PR4 · feature/m2-pr4-style-switch → base feature/m2-pr3-followup-state

**feat(interview): 面试官风格切换（friendly/stress/deep），接口零变更**

## 变更清单

- 新增 `app/prompts/interview/styles/`（friendly/stress/deep，各带 VERSION）
- 新增 `app/services/interview/style_resolver.py`：style → 三个 tone 片段
- 扩充 `answer_evaluation.py` / `follow_up_decision.py`：注入 tone 占位符
- 扩充 `ai_service.py` / `service.py`：stream_feedback / decide_follow_up 接受 style
- 新增 `docs/M2-面试引擎-Prompt版本管理.md` + `docs/M2-完成报告.md`

## 测试说明

- `test_style_resolver.py`（SS-05/07/09）
- `test_interview_style_switch.py`（SS-01~05/08/10：同接口切换、风格不改变题目、文风注入）

`pytest` 209 通过，覆盖率 93.88%（≥80%），flake8 / mypy 干净。

## 人工评审重点

- 接口契约零变更（diff 路由确认）
- 三风格文风是否真的差异化（跑 3 场真实面试对比）

🤖 Generated with [Claude Code](https://claude.com/claude-code)
