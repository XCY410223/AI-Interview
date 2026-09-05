# 项目宪法（违反即重做）

> 配套文档：`docs/智能面试平台开发规范.md` v1.3
> 执行计划：`docs/Claude Code 实施开发规范计划书.md`
> 规范升级到 v1.4+ 时，必须同步修订本文件红线。

## 角色分工

| 角色 | 职责 |
|---|---|
| Claude Code | 写代码、写测试、跑测试并修失败、重构、生成迁移、写文档、执行本文件全部条款 |
| 人 | 架构决策、需求拍板、PR 评审、Alembic 迁移终审、密钥管理、上线操作 |

核心原则：**规范是给 Claude 的，验收是给人的。** Claude 的目标是让 CI 变绿，退出标准由人和 CI 共同把关。

Claude 可起草但必须人工终审的环节（不得自行执行）：
- Alembic 迁移的 `alembic upgrade` 执行
- 任何涉及密钥 / `.env` 的改动
- 生产部署操作

## 技术栈（禁止擅自替换）

- 后端：FastAPI (Python 3.12+) / SQLAlchemy 2.0 async / PostgreSQL 16+ (JSONB, pgvector) / Celery + Redis
- 前端：Vue3 + Vite + Pinia + Element Plus
- 基础设施：Docker Compose、MinIO/COS 对象存储
- AI：统一 LLM 客户端（AsyncOpenAI 兼容封装）；embedding 用 bge-m3；评估 judge 用 DeepSeek + t=0（配置锁死，不得更改）

## 红线（来自旧项目实测教训，违反必须回退）

1. 禁止重复注册路由；新增路由前先 grep 现有路由
2. 禁止 `.env`、`logs/`、`uploads/`、任何密钥进入 git
3. 上传文件名必须清洗：`{user_id}_{uuid}.{ext}`，禁止直接拼接用户输入
4. 简历解析/报告生成必须走 Celery 异步，禁止在 HTTP 请求内同步调 LLM
5. LLM 输出禁止用正则从自由文本抠 JSON——统一走结构化输出协议 + Pydantic 校验
6. 所有 AI 调用必须走统一 LLM 客户端（超时/重试/降级），禁止直接 new 客户端
7. SSE 事件协议：`meta / chunk / score / next / error` 五类；评分 JSON 用独立 `score` 事件下发，前端不解析文本。新增事件需更新协议文档
8. 文件存对象存储（MinIO/COS），禁止写本地磁盘
9. Prompt 集中管理且带版本号（含 style 参数：friendly/stress/deep），禁止在业务代码里内联写 prompt
10. 业务代码禁止 import 测试模块；ragas 仅存在于 requirements-dev.txt

## 目录结构

```
app/
├── api/        # 路由层，路由注册走 registry
├── services/   # 业务逻辑
├── models/     # SQLAlchemy 模型
├── schemas/    # Pydantic schema（接口与报告 schema 先行冻结）
├── core/       # 配置、LLM 统一客户端、安全
eval/           # Ragas 评估脚本 + 黄金样本
```

## 工作流要求

- **先规划后写码**：任何功能先输出实现计划（涉及文件、模型变更、接口签名），经人确认后再实现
- **TDD 强制**：写任何功能前先写/更新对应测试；先跑红再实现到绿
- **提交前必须跑通**：`pytest + flake8 + isort + mypy`
- **覆盖率卡点**：M0~M1 阶段 ≥60%，M2 起升至 ≥80%
- commit 格式：`<type>(<scope>): <中文描述≤50字>`
- 分支模型：一个功能一个分支 `feature/xxx`，从 `dev` 切出；`dev/preview/main` 禁止直推
- 涉及数据库变更时生成 Alembic 迁移，**但不要自动执行 `upgrade`**（人工终审）
- 长会话上下文失焦时主动提醒人 `/clear` 重开；重要决策回写本文件

## 危险命令（禁止执行）

以下命令属于 deny 列表，永远不要执行，只能提示用户手动操作：
- `alembic upgrade`
- `docker compose down -v`（清数据卷）
- `git push` 到受保护分支
- 任何生产部署命令

## 领域规则（按模块）

### 面试引擎（M2）
- 追问状态机：每题 ≤3 轮追问，`question_index + round` 双键推进
- Prompt 变更流程：更新版本号入库 → 跑黄金样本集（20 条）回归 → 输出新旧评分对比表；偏差 >1 分的样本交人工复盘
- SSE 测试要求：故意输入含 `{"score":10}` 的回答，评分不受污染

### RAG（M4）
- 入库管线：切片 → 去重 → embedding（bge-m3 + pgvector）
- 改写后引用必须标注来源
- Ragas 回归阈值：precision ≥ 0.8 / faithfulness ≥ 0.9；judge 配置（DeepSeek + t=0）锁死

## 任务收尾自查（每次提交前）

对照红线 1~10 自查本分支 diff，输出逐条检查结果：
- [ ] 无重复路由（已 grep）
- [ ] 无敏感信息入 git
- [ ] 文件名已清洗、存对象存储
- [ ] LLM 调用全部走统一客户端且异步化
- [ ] 结构化输出，无正则抠 JSON
- [ ] SSE 事件符合五类协议
- [ ] Prompt 集中管理且有版本号
- [ ] 测试全绿，覆盖率达标
- [ ] 数据库变更已生成迁移（未执行 upgrade）
