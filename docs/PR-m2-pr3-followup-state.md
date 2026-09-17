# PR3 · feature/m2-pr3-followup-state → base feature/m2-pr2-sse-protocol

**feat(interview): 追问状态机与历史回放，黄金样本回归**

## 变更清单

- 新增 `app/services/interview/state_machine.py`：≤3 轮追问 + 双键推进 + 低分快速翻页
- 新增 `app/models/interview_message.py` + `app/schemas/interview_message.py`：消息回放
- 新增 `app/prompts/interview/follow_up_decision.py`：追问决策 prompt
- 扩充 `ai_service.py` / `service.py` / `api`：decide_follow_up、get_messages、Redis 互斥锁
- 迁移 `20260917_0004_create_interview_messages.py`
- 新增黄金样本 20×3 条（fixtures + eval/datasets，防漂移测试锁定）
- 新增 eval 脚本（run_golden_regression.py / compare_versions.py）+ judge 配置锁死（DeepSeek + t=0）
- 新增 `docs/M2-面试引擎-追问状态机.md` + `.github/workflows/m2-sse-regression.yml`

## 测试说明

- `test_state_machine.py`（FS-01~05/09）
- `test_interview_followup_state.py`（FS-06/08/10，含 FS-08 反污染）
- `test_golden_samples.py`（结构 + 防漂移 + 版本对比逻辑）

`pytest` 200 通过，flake8 / mypy 干净。

## 人工评审重点

- 3 轮上限是否合理（跑真实面试看节奏）
- 黄金样本覆盖是否充分
- 并发锁（Redis SET NX EX）是否正确

🤖 Generated with [Claude Code](https://claude.com/claude-code)
