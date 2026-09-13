# syntax=docker/dockerfile:1

# =============================================================================
# 生产镜像：多阶段构建（builder -> runtime）+ 非 root 运行（规范 §15）
#
#   Stage 1 builder：创建 venv 并安装运行时依赖（requirements.txt）
#   Stage 2 runtime：仅拷贝 venv + 应用代码，不携带 pip 构建缓存/编译器
#   运行用户：app（uid/gid 10001），健康检查：GET /api/v1/health
#
#   说明：requirements.txt 全部依赖均有 cp312 manylinux wheel，
#         无需在 builder 安装 gcc；如未来新增无 wheel 依赖再补编译工具链。
# =============================================================================

########## Stage 1: builder —— 安装依赖 ##########
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# 国内 PyPI 镜像（可用 --build-arg PIP_INDEX_URL=https://pypi.org/simple 覆盖）
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 依赖分层缓存：仅拷贝 requirements，依赖未变则复用该层
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip -i ${PIP_INDEX_URL} \
    && /opt/venv/bin/pip install -r requirements.txt -i ${PIP_INDEX_URL}

########## Stage 2: runtime —— 精简运行镜像 ##########
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    TZ=Asia/Shanghai

# 国内 Debian 镜像（可用 --build-arg APT_MIRROR=deb.debian.org 覆盖）
ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn

# 运行时系统依赖：ca-certificates(HTTPS 调 LLM) curl(healthcheck) procps(pgrep) tzdata(时区)
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl procps tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app \
    && mkdir -p /home/app/celerybeat \
    && chown -R app:app /home/app

# 从 builder 拷贝已装好的 venv（精简：不带 pip 构建缓存/源码）
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# 非 root 运行（规范 §15）
USER app

EXPOSE 8006

# 健康检查：GET /api/v1/health（生产 gunicorn 多 worker）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["curl", "-fsS", "http://127.0.0.1:8006/api/v1/health"]

# 生产：gunicorn 管理 uvicorn worker，4 worker（规范 §15）
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8006", "--timeout", "120", "--graceful-timeout", "30", "--access-logfile", "-"]
