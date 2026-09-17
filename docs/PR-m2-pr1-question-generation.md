# PR1 · feature/m2-pr1-question-generation → base feature/resume

**feat(interview): 出题服务，简历+岗位生成结构化题目并落库**

> 注：本 PR 含前置 `chore(ci): 测试覆盖率卡点升至 80%（M2 起）`。

## 变更清单

- 新增 `app/models/interview.py`：interviews 表（style/current_round/questions_json/config_json 预埋）
- 新增 `app/schemas/interview.py`：InterviewConfig / StartInterviewRequest / QuestionItem / StartInterviewResponse
- 新增 `app/prompts/interview/` 包：`question_generation.py`（带 `VERSION` 头）+ `CHANGELOG.md`（红线 9）
- 新增 `app/services/common/prompt_loader.py`：带版本头校验的加载器
- 新增 `app/services/interview/ai_service.py`：出题编排（结构化输出 + 重试 1 次 + 兜底题）
- 新增 `app/services/interview/service.py`：`start`（出题落库 + 返回首题）
- 扩充 `app/api/v1/interview.py`：`POST /api/v1/interviews`
- 扩充 `app/common/exceptions.py`：INTERVIEW_NOT_FOUND / FORBIDDEN / INVALID_STATE
- 迁移 `20260917_0003_create_interviews.py`
- 删除 `app/prompts/interview.py`（单文件 → 包）

## 测试说明

- `test_ai_service_question_generation.py`（QG-01~06：正常 / 空简历 / 上限 / 重试 / 兜底）
- `test_interview_start.py`（QG-10 端到端：start → 落库 → 首题）
- `test_prompt_loader.py`（QG-07 版本头校验）

`pytest` 156 通过，flake8 / mypy 干净。

## 人工评审重点

- Prompt 版本头是否齐全（红线 9）
- 迁移是否只建表不写业务逻辑（规范 §7.3）
- 兜底路径是否落日志

🤖 Generated with [Claude Code](https://claude.com/claude-code)
