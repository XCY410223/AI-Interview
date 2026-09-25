# 面试 Prompt 版本台账（红线 9 / M2 计划 §3.2）

改 prompt 必须：升版本号 → 在此登记 → 跑黄金样本回归（`eval/scripts/run_golden_regression.py`）→ 输出新旧对比表，偏差 >1 分样本交人工复盘。

| 模块 | 版本 | 变更 | 回归要求 |
|---|---|---|---|
| question_generation | 1.0 | M2-PR1 初版：简历+岗位 → N 道题 JSON | — |
| question_generation | 2.0 | M4-PR2：新增可选 JD 能力项注入段（无 JD 行为等价 v1） | 无 JD 等价性回归 + 有 JD 命中率 ≥80% |
| question_generation | 2.1 | M4-PR7-a：新增可选题库模板参考注入段（无模板行为等价 v2.0） | 无模板等价性回归 |
| answer_evaluation | 1.0 | M2-PR2 初版：评分 JSON 与评语流分离 | — |
| follow_up_decision | 1.0 | M2-PR3 初版：基于回答历史决定是否追问 | — |
