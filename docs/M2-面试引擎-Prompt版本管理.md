# M2 面试引擎 · Prompt 版本管理

> 配套：CLAUDE.md 红线 9 / `M2 面试引擎实施计划书.md` §三
> 状态：M2-PR4 交付

## 1. 文件命名规范

```
app/prompts/interview/
├── question_generation.py     # 出题 prompt（VERSION 常量）
├── answer_evaluation.py       # 评分 + 评语流 prompt（两条独立模板）
├── follow_up_decision.py      # 追问决策 prompt
├── styles/
│   ├── friendly.py            # 友好（STYLE_SYSTEM_PROMPT / FOLLOWUP_TONE / FEEDBACK_TONE）
│   ├── stress.py              # 压力
│   └── deep.py                # 深挖
└── CHANGELOG.md               # 变更登记表
```

每个 prompt 模块必须声明非空 `VERSION = "x.y"`（字符串）与 `CHANGELOG = [...]`。
加载器 `services/common/prompt_loader.py` 的 `require_version()` 在加载时断言版本头存在，缺失即 `PromptVersionError`。

## 2. CHANGELOG.md 格式

| version | date | author | changelog | 回归结果 | 偏差复盘 |
|---|---|---|---|---|---|
| 1.0 | 2026-09-17 | Claude Code | M2 初版 | 基线建立（20×3） | - |

## 3. 黄金样本回归 SOP（任何 prompt 变更必走）

```
1. git 自动备份旧 prompt
2. 更新 prompt 文件，version +0.1，登记 CHANGELOG
3. python eval/scripts/run_golden_regression.py --dataset eval/datasets/golden_v1_followups.jsonl --kind followups --output artifacts/golden_v1_followups.json
4. python eval/scripts/compare_versions.py --baseline artifacts/golden_v1_baseline.json --current artifacts/golden_v1_followups.json --threshold 1.0
   → 输出对比表 | sample_id | old_score | new_score | diff | flag |
5. 偏差 >1 分的样本（flag=DRIFT）逐条人工复盘 → 结论写进 CHANGELOG.md
6. 通过后 commit + tag（git tag prompts/v2.0）
```

## 4. 风格切换（M2-PR4）

`config.style ∈ {friendly, stress, deep}` 仅影响 prompt 拼接（`style_resolver.py` 拼接三个 tone 片段），
**接口签名零变更**；题目内容在 `start` 时一次性确定，风格不改变 `questions_json`。
