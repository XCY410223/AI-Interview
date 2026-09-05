# 用 Claude Code 实施智能面试平台开发规范 — 执行计划书

> 配套文档：《智能面试平台开发规范.md》v1.3
> 目标：以 Claude Code 为主力编码代理，8 周内完成 M0~M4 全部交付
> 制定日期：2026-09-04

---

## 一、总体思路：人机分工

| 角色 | 职责 |
|---|---|
| **Claude Code** | 写代码、写测试、跑测试并修失败、重构、生成迁移、写文档、按指令执行规范条款 |
| **你（人）** | 架构决策、需求拍板、PR 评审、Alembic 迁移终审、密钥管理、上线操作 |

**核心原则：规范是给 Claude 的，验收是给你的。** 每一步的"退出标准"由人和 CI 共同把关，Claude 只负责让 CI 变绿。

不建议 100% 托管的环节（Claude 可起草，你终审）：
- Alembic 迁移（高危，生成后必须人工读一遍再 `alembic upgrade`）
- 涉及密钥/`.env` 的改动
- 生产部署操作（手动确认环节不交给 agent）

---

## 二、准备阶段（开工前一次性完成，约半天）

### 2.1 安装与初始化

```powershell
npm install -g @anthropic-ai/claude-code
cd D:\python\project\interview-platform   # 新项目目录（示例）
git init
claude                                     # 首次启动，登录 Anthropic 账号
```

### 2.2 把开发规范变成 Claude 的"宪法"（最关键一步）

Claude Code 每次会话自动读取项目根目录的 **CLAUDE.md**。把 v1.3 规范浓缩成机器可执行规则放进去，规范就从"给人看的文档"变成"agent 的执行约束"——这比事后代码评审拦截更前置。

**`CLAUDE.md` 内容草案**（直接复制使用）：

```markdown
# 项目宪法（违反即重做）

## 技术栈（禁止擅自替换）
FastAPI 3.12+ / SQLAlchemy 2.0 async / PostgreSQL 16+JSONB / Celery+Redis
Vue3+Vite+Pinia+Element Plus / pgvector / Docker Compose

## 红线（来自旧项目实测教训，违反必须回退）
1. 禁止重复注册路由；新增路由前先 grep 现有路由
2. 禁止 .env、logs/、uploads/、任何密钥进入 git
3. 上传文件名必须清洗：{user_id}_{uuid}.{ext}，禁止直接拼接用户输入
4. 简历解析/报告生成必须走 Celery 异步，禁止在 HTTP 请求内同步调 LLM
5. LLM 输出禁止用正则从自由文本抠 JSON——统一走结构化输出协议+Pydantic 校验
6. 所有 AI 调用必须走统一 LLM 客户端（超时/重试/降级），禁止直接 new 客户端
7. SSE 事件协议：meta/chunk/score/next/error 五类，新增事件需更新协议文档
8. 文件存对象存储（MinIO/COS），禁止写本地磁盘
9. Prompt 集中管理且带版本号，禁止在业务代码里内联写 prompt
10. 业务代码禁止 import 测试模块；ragas 仅存在于 requirements-dev.txt

## 工作流要求
- 写任何功能前先写/更新对应测试
- 提交前必须跑通：pytest + flake8 + isort + mypy
- commit 格式：<type>(<scope>): <中文描述≤50字>
- 一个功能一个分支：feature/xxx，从 dev 切出
- 改动涉及数据库时生成 Alembic 迁移，但不要自动执行 upgrade
```

### 2.3 权限与安全配置

- Claude Code 权限档位用 **acceptEdits 起步**（自动接受文件编辑，但 shell 命令需确认），跑熟后再按需放开
- `.claude/settings.json` 中把 `alembic upgrade`、`docker compose down -v`、`git push` 加入 `deny` 列表（防误操作数据卷/远端）
- 项目里已有 `.env` 时**先确认在 `.gitignore`** 再让 Claude 接触仓库

### 2.4 基础设施就位

- pre-commit 钩子（black + isort + flake8 + gitleaks 密钥扫描）——让 Claude 装好，之后每次提交自动兜底
- GitHub 仓库建立，分支保护：dev/preview/main 禁止直推

---

## 三、标准执行循环（每个功能单元都走这五步）

```
① 需求输入 ──► ② Claude 规划(Plan mode) ──► ③ 生成实现+测试
                                                      │
⑤ 合并 ◄── ④ 人工评审+CI 门禁 ◄────────────────────┘
```

**第 ② 步强制使用 Plan mode**（Shift+Tab 切换）：让 Claude 先输出实现计划而非直接写码，你审完计划再放行。这一步的价值是：错误在"纸面计划"阶段拦截，成本远低于写完代码再回退。

**给 Claude 的标准任务提示词模板**：

```text
阅读 CLAUDE.md 和《智能面试平台开发规范.md》§X.X。
在 feature/xxx 分支实现：<功能描述>。
要求：
1. 先给出实现计划（涉及文件、模型变更、接口签名），等我确认后再写码
2. 遵守 TDD：先写测试再实现，测试要覆盖 <边界情况>
3. 完成后运行 pytest -k <相关模块>，全绿后提交
```

**循环里的人工动作只有三个**：审计划（2~5 分钟）、审 PR（对照 §16 评审清单）、合并。

---

## 四、里程碑执行计划

### M0 基建（第 1 周）— 让 Claude 打地基

| 步骤 | 内容 | 提示词要点 | 验收 |
|---|---|---|---|
| M0-1 | 目录骨架 + 分层结构 | "按规范 §4 目录结构生成，含 `app/{api,services,models,core,schemas}`，路由注册走 registry" | 树形结构对照规范 |
| M0-2 | docker-compose（dev+prod）| "按 §15：app/celery-worker/celery-beat/postgres/redis/nginx + healthcheck + 非root + 多阶段构建" | `docker compose up` 一条命令起全栈 |
| M0-3 | CI 流水线 | "按 §14.2 建 GitHub Actions：quick-check/test/lint-frontend/build 四阶段，覆盖率卡点先设 60%（M2 后升 80%）" | 空提交触发 CI 全绿 |
| M0-4 | 统一 LLM 客户端 | "实现 §9.1：AsyncOpenAI 兼容封装，含超时/重试/降级/token 计量，单测用 mock" | 单测覆盖重试分支 |

**M0 退出：CI 绿 + 本地起全栈 + LLM 客户端可用。**

### M1 账户+简历（第 2~3 周）

| 单元 | 提示词要点 | 人工重点 |
|---|---|---|
| 注册/登录/JWT 双 token | "先写 pytest 用例（成功/重复注册/错误密码/token 过期），再实现" | 审 refresh 轮换逻辑 |
| 上传接口 | "文件名清洗规则：uuid 化 + 白名单后缀；存 MinIO，本地不留副本" | 路径穿越测试用例是否覆盖 |
| Celery 解析任务 | "上传接口只存文件+建记录（status=pending）即返回；解析走 Celery；参考 §10.2 状态机" | **重点评审**：这是旧项目最大的坑 |
| 前端简历展示 | "Element Plus + 轮询任务状态，完成后渲染结构化 JSON" | 交互是否反馈等待进度 |

**M1 退出：上传→解析→展示全链路 < 30s（异步感知：秒级返回+进度提示）。**

### M2 面试引擎（第 3~5 周）— 全项目最难，拆最细

按周拆为四个 PR 序列，每个都走完整循环：

1. **出题服务**：简历+岗位 → 题目 JSONB；prompt 走集中管理 v1
2. **SSE 结构化协议**：五类事件（meta/chunk/score/next/error）；**评分 JSON 用独立 score 事件下发，前端不再解析文本**——这是与旧项目的分水岭，测试要求"故意输入含 `{"score":10}` 的回答，评分不受污染"
3. **追问状态机**：每题 ≤3 轮追问，`question_index + round` 双键推进；黄金样本集（20 条）建库
4. **风格切换**：prompt 模板加 style 参数（friendly/stress/deep），接口不变

**人工重点**：每次 prompt 变更后，让 Claude 跑黄金样本回归并输出对比表——评分偏差 >1 分的样本人工复盘。

**M2 退出：10 轮面试零解析失败 + 评分稳定 + 三风格可切。**

### M3 报告（第 6 周）

- 报告生成走 Celery + 结果缓存；报告 schema 先行（Pydantic 定义冻结后再写生成逻辑）
- 前端 ECharts 雷达图 + 导出 PDF（后端 WeasyPrint 或前端截图，让 Claude 评估二选一并给理由）

### M4 打磨（第 7~8 周）— RAG 主战场

| 单元 | 要点 |
|---|---|
| JD 定制 | JD 解析 → 能力项清单 → 出题 prompt 注入；验收：关键词命中率 ≥ 80%（脚本自动算） |
| 真题 RAG | pgvector + bge-m3；入库管线（切片→去重→embedding）跑通；改写后引用标注来源 |
| Ragas 评估 | `eval/` 目录 + 黄金样本 20~50 条；让 Claude 写评估脚本但**judge 配置你锁死**（DeepSeek + t=0）；回归阈值 precision≥0.8 / faithfulness≥0.9 |
| 剩余 | 题库沉淀、历史回放、专项练习、Waiting List |

**注意**：若两周排不下，按预先定好的降级顺序砍——先降级 Ragas 为"入库管线+人工抽检"，**不砍 RAG 功能本身**。

---

## 五、给 Claude 的高频提示词库（收藏直接用）

| 场景 | 提示词 |
|---|---|
| 测试驱动开发 | "为 <模块> 写 pytest 测试，覆盖：正常路径、空输入、LLM 返回非法 JSON、超时降级。先跑红再实现到绿" |
| 修测试失败 | "运行 pytest，把失败逐个修复；禁止修改测试断言来让测试通过，除非断言本身与规范冲突并说明理由" |
| 规范自查 | "对照 CLAUDE.md 红线 1~10 自查本分支 diff，输出逐条检查结果" |
| 代码评审预审 | "按 §16 评审清单检查本 PR：路由重复/敏感信息/迁移存在/测试覆盖/AI 统一封装/无同步阻塞，输出报告" |
| 重构 | "提取 <重复代码> 为公共模块，行为不变，跑全量测试验证" |
| Prompt 变更 | "更新 <prompt> 到 v2 并入库；然后用黄金样本集跑回归，输出新旧评分对比表" |

---

## 六、质量门禁（自动化，人不参与的部分）

```
Claude 提交 → pre-commit（格式+密钥扫描）
           → CI：flake8/isort/mypy + pytest 覆盖率≥80% + 前端 eslint
           → PR 评审清单（Claude 预审 + 人终审）
           → preview 环境自动部署，人工冒烟
           → tag → 手动确认上生产
```

**覆盖率卡点必须在 M0 就建好**——单人开发 + AI 生成代码的最大风险就是"看起来能跑"，没有 CI 卡点，测试永远补不回来。

---

## 七、风险与对策（本计划书特有）

| 风险 | 对策 |
|---|---|
| Claude 生成的代码"幻觉"用不存在的 API | CI 全量编译/测试卡点兜底；对不熟悉的第三方库先让 Claude 查文档再写 |
| 上下文窗口内规范失焦 | CLAUDE.md 红线已浓缩；长会话定期 `/clear` 重开，重要决策写进 CLAUDE.md |
| agent 误执行危险命令 | settings.json deny 列表（§2.3）；迁移/部署保留人工步骤 |
| 过度依赖 AI，架构理解脱节 | Plan mode 强制审计划；每个里程碑你自己走读一遍核心模块 |
| API 费用失控 | 简单任务（改文案、格式）不启用 Claude；核心逻辑开发才用 |

---

## 八、每周节奏（参考）

| 时间 | 动作 |
|---|---|
| 周一 | 定本周目标 → 拆 PR → 开分支 |
| 周二~周四 | 执行标准循环（Claude 实现 + 你审 PR），每天 3~5 个循环 |
| 周五 | 里程碑验收（跑退出标准）+ Claude 做周报（`总结本周 diff 与规范符合度`） |
| 每晚 | preview 环境冒烟 10 分钟 |

---

## 九、启动检查单（今天就能做的事）

- [ ] `npm install -g @anthropic-ai/claude-code` 并登录
- [ ] 建项目目录 + `git init`
- [ ] 把 §2.2 的 CLAUDE.md 草案放进根目录（后续随规范版本同步更新）
- [ ] 复制《智能面试平台开发规范.md》进项目 `docs/`（Claude 可引用原文）
- [ ] 配置 §2.3 权限与 deny 列表
- [ ] 发起 M0-1：骨架生成的 Plan mode 会话

---

*本计划书与《智能面试平台开发规范.md》v1.3 配套使用；规范变更为 v1.4+ 时同步修订 CLAUDE.md 红线。*
