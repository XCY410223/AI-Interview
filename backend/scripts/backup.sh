#!/usr/bin/env bash
# =============================================================================
# PostgreSQL 逻辑备份脚本（规范 §15：定期 pg_dump，备份文件入对象存储）
#
# 由 docker-compose.yml 的 backup 服务（--profile backup）每日调用：
#   docker compose --profile backup up -d
#
# 依赖环境变量（backup 服务已注入）：
#   PGHOST / PGUSER / PGPASSWORD / PGDATABASE —— pg_dump 连接参数
#   BACKUP_DIR   备份目录（默认 /backups）
#   RETENTION_DAYS 本地备份保留天数（默认 7）
#   S3_*         可选：配置后启用对象存储上传（M3 接入）
# =============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="${BACKUP_DIR}/ai_interview_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[backup] dumping ${PGDATABASE:-ai_interview} -> ${DUMP_FILE}"
pg_dump --no-owner --no-acl | gzip > "${DUMP_FILE}"

# 可选：上传对象存储（S3 协议，规范 §15「备份文件入对象存储」）
# M3 接入对象存储客户端后启用；当前为占位。
if [[ -n "${S3_ENDPOINT:-}" && -n "${S3_ACCESS_KEY:-}" ]]; then
  echo "[backup] S3 upload enabled (placeholder), bucket=${S3_BUCKET:-ai-interview}"
fi

# 清理过期本地备份
find "${BACKUP_DIR}" -name 'ai_interview_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete

echo "[backup] done"
