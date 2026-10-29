# AI-Interview — 智能面试平台（求职者模拟面试增强版）

> 技术栈：FastAPI (Python 3.12+) / SQLAlchemy 2.0 async / PostgreSQL 16 (JSONB + pgvector) / Celery + Redis / Vue3 + Vite + Pinia + Element Plus
> 项目宪法：根目录 `CLAUDE.md`（红线条款，违反即重做）
> 开发规范：`docs/智能面试平台开发规范.md` v1.3
> 目录结构参考旧项目 `ai-interview` 的实际分层，并按规范 v1.3 收敛（去 admin/backoffice、`db/` 并入 `core/`、`schedule/` 改 `tasks/`、新增 `prompts/` 与 `eval/`）。

## 目录骨架

```
AI-Interview/
├── backend/                          # FastAPI 后端（模块化单体）
│   ├── app/
│   │   ├── main.py                   # 应用入口（仅组装）
│   │   ├── core/                     # 基础设施
│   │   │   ├── config.py             #   配置（.env，密钥不入库）
│   │   │   ├── security.py           #   JWT / 密码哈希 / 文件名清洗
│   │   │   ├── log_config.py         #   结构化日志（JSON Lines）
│   │   │   ├── redis.py              #   Redis 客户端封装
│   │   │   ├── database.py           #   引擎 + session 工厂（async）
│   │   │   └── llm/client.py         #   统一 LLM 客户端（超时/重试/降级/计量）
│   │   ├── api/v1/                   # 唯一对外 API 层
│   │   │   ├── router_registry.py    #   路由注册 registry（防重复注册）
│   │   │   ├── deps.py               #   依赖注入
│   │   │   ├── health.py             #   GET /health
│   │   │   └── auth/resume/interview/question_bank/report.py
│   │   ├── services/                 # 业务服务（编排/AI 调用/事务边界）
│   │   │   ├── common/               #   email / storage / redis 共享服务
│   │   │   ├── auth/service.py
│   │   │   ├── resume/service.py
│   │   │   ├── interview/service.py + ai_service.py
│   │   │   ├── question_bank/service.py
│   │   │   └── report/service.py
│   │   ├── models/                   # ORM 模型（base + user/token/resume/interview/
│   │   │                             #   interview_message/question/report/waiting_list）
│   │   ├── schemas/                  # Pydantic（base/common + 各模块）
│   │   ├── tasks/                    # Celery（celery_app + resume/report/email/rag）
│   │   ├── prompts/                  # AI Prompt 模板（带 version 头）
│   │   ├── common/                   # exceptions / pagination / language
│   │   └── scripts/                  # seed 运维脚本
│   ├── migrations/                   # Alembic（versions/ + README）
│   ├── tests/                        # unit / integration / fixtures
│   ├── eval/                         # Ragas 离线评估（datasets/scripts/judge）
│   ├── resources/emails/             # 邮件模板（集中管理）
│   ├── .env.example                  # 环境变量样例（唯一允许入库的配置）
│   ├── requirements.txt / requirements-dev.txt
│   ├── Dockerfile / Dockerfile.dev / .dockerignore
│   ├── docker-compose.yml / .dev.yml / .prod.yml
│   ├── alembic.ini / celery_worker.py
├── frontend/                         # Vue3 用户端（src: api/router/stores/views/components/composables/types/utils）
├── docs/                             # 需求/设计/接口文档 + 两份规范原文
├── nginx/                            # Nginx 配置（静态资源 + 反向代理 + TLS）
├── .github/workflows/                # CI/CD
├── .gitignore                        # 含 .env/logs/uploads/*.local 红线
├── CLAUDE.md                         # 项目宪法（红线 1~10）
└── README.md
```

## 分层架构（依赖单向：api → services → models/core）

| 层 | 目录 | 职责 | 禁止事项 |
|---|---|---|---|
| API 层 | `app/api/v1/` | 路由、校验、鉴权依赖、序列化 | 禁止写 SQL / 直接调 LLM |
| 服务层 | `app/services/` | 业务编排、AI 调用、事务边界 | 禁止跨模块直操对方模型表、禁止自行 new session |
| 数据层 | `app/models/` | ORM 模型、仓库模式统一查询 | 用 JSONB 存需 WHERE/JOIN 的字段 |
| 基础设施 | `app/core/` | 配置、安全、Redis、日志、LLM 客户端 | 被上层反向 import |

## 关键红线（详见根目录 CLAUDE.md）

1. 禁止重复注册路由；2. 禁止 `.env`/`logs/`/`uploads/`/密钥入库；3. 上传文件名清洗 `{user_id}_{uuid}.{ext}`；
4. 简历解析/报告生成必须走 Celery 异步；5. 结构化输出协议 + Pydantic 校验（禁止正则抠 JSON）；
6. AI 调用统一走 `core/llm/`；7. SSE 五类事件 `meta/chunk/score/next/error`；8. 文件存对象存储（MinIO/COS）；
9. Prompt 集中管理带版本号；10. ragas 仅存在于 requirements-dev.txt。

## 端口规划（规范 §15）

FastAPI `8006` / PostgreSQL `5434` / Redis `6382` / Nginx `80`/`443`

## 本地启动（Docker Compose，M0-2）

在 `backend/` 目录下执行（Compose 文件与 Dockerfile 均位于此，`../nginx` 相对路径以此解析）：

```bash
cd backend
cp .env.example .env          # 首次：生成本地配置（真实密钥不入库；缺 .env 也能用默认值起）
docker compose up -d --build  # 一条命令起全栈
```

启动后冒烟：

- 后端健康检查（经 Nginx 反代）：`curl http://localhost/api/v1/health`
- Nginx 自身探活：`curl http://localhost/healthz`
- Swagger：`http://localhost/api/docs`

常用：

- 开发（源码热重载）：`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`
- 生产加固（TLS，证书放 `backend/certs/`）：`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
- Celery 监控：`docker compose --profile flower up -d`
- 定时备份：`docker compose --profile backup up -d`

> 注意：`docker compose down -v` 会清空数据卷，属危险命令（CLAUDE.md 红线），请勿执行。

## 下一步（对应计划书 M0/M1）

- ~~M0-2：实现 `docker-compose.yml` + Dockerfile（healthcheck/非 root/多阶段构建）~~ ✅
- ~~M0-3：`.github/workflows/` 建 CI（quick-check/test/lint-frontend/build，覆盖率 ≥60%）~~ ✅
- ~~M0-4：实现 `core/llm/client.py`（超时/重试/降级/token 计量）~~ ✅
- **M1：账户 + 简历（注册/登录/上传/异步解析/结构化展示）** ✅（完成报告已归档）

M1 已部署：Docker 全栈 running、迁移已执行 0002(head)；剩余 LLM 冒烟 + 人工评审。
