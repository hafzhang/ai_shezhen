#!/bin/bash
# Redis 数据备份脚本
# Backup Redis data with automatic compression and cleanup
#
# Usage:
#   ./backup_redis.sh [dry-run]
#
# Author: Ralph Agent
# Date: 2026-02-21

set -e

# 配置 / Configuration
BACKUP_DIR="${BACKUP_DIR:-/data/backups/redis}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
REMOTE_SYNC="${REMOTE_SYNC:-false}"
S3_BUCKET="${S3_BUCKET:-s3://shezhen-backups/redis}"

# 颜色输出 / Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为 dry-run 模式
DRY_RUN=false
if [ "$1" = "dry-run" ]; then
    DRY_RUN=true
    log_warn "Running in DRY-RUN mode, no changes will be made"
fi

# 时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

log_info "Starting Redis backup process at $TIMESTAMP"

# 创建备份目录
log_info "Creating backup directory: $BACKUP_DIR"
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$BACKUP_DIR"
fi

# 检查 Redis 连接
log_info "Checking Redis connection: $REDIS_HOST:$REDIS_PORT"
if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
    log_error "Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
    exit 1
fi

# 获取当前 BGSAVE 状态
log_info "Checking current BGSAVE status"
LASTSAVE=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE)

# 触发 BGSAVE
log_info "Triggering BGSAVE..."
if [ "$DRY_RUN" = false ]; then
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE > /dev/null
fi

# 等待 BGSAVE 完成
log_info "Waiting for BGSAVE to complete..."
WAIT_TIME=0
MAX_WAIT=300  # 最大等待5分钟
while true; do
    CURRENT_LASTSAVE=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE)
    if [ "$CURRENT_LASTSAVE" -gt "$LASTSAVE" ]; then
        log_info "BGSAVE completed successfully"
        break
    fi

    if [ $WAIT_TIME -ge $MAX_WAIT ]; then
        log_error "BGSAVE timeout after ${MAX_WAIT}s"
        exit 1
    fi

    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))
    echo -n "."
done
echo ""

# 查找 RDB 文件位置
log_info "Locating RDB file..."
RDB_PATH=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" CONFIG GET dir | tail -1)
RDB_FILENAME=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" CONFIG GET dbfilename | tail -1)
RDB_FILE="$RDB_PATH/$RDB_FILENAME"

if [ ! -f "$RDB_FILE" ]; then
    log_error "RDB file not found at $RDB_FILE"
    # 尝试 Docker 容器内的路径
    CONTAINER_NAME=$(docker ps --filter "ancestor=redis:7-alpine" --format "{{.Names}}" | head -1)
    if [ -n "$CONTAINER_NAME" ]; then
        log_info "Trying to copy from Docker container: $CONTAINER_NAME"
        RDB_FILE="/data/dump.rdb"
    else
        exit 1
    fi
fi

# 复制并压缩备份文件
BACKUP_FILE="$BACKUP_DIR/dump_$TIMESTAMP.rdb"
COMPRESSED_FILE="$BACKUP_FILE.gz"

log_info "Creating backup: $COMPRESSED_FILE"

if [ "$DRY_RUN" = false ]; then
    if [ -n "$CONTAINER_NAME" ]; then
        # 从 Docker 容器复制
        docker cp "$CONTAINER_NAME:/data/dump.rdb" "$BACKUP_FILE"
    else
        # 直接复制
        cp "$RDB_FILE" "$BACKUP_FILE"
    fi

    # 压缩
    gzip -f "$BACKUP_FILE"

    # 计算文件大小和校验和
    FILE_SIZE=$(stat -f%z "$COMPRESSED_FILE" 2>/dev/null || stat -c%s "$COMPRESSED_FILE" 2>/dev/null)
    CHECKSUM=$(sha256sum "$COMPRESSED_FILE" | cut -d' ' -f1)

    log_info "Backup created: $COMPRESSED_FILE"
    log_info "File size: $FILE_SIZE bytes"
    log_info "SHA-256: $CHECKSUM"

    # 保存校验和
    echo "$CHECKSUM  $COMPRESSED_FILE" > "$COMPRESSED_FILE.sha256"
else
    log_info "[DRY-RUN] Would create: $COMPRESSED_FILE"
fi

# 清理旧备份
log_info "Cleaning up old backups (older than $RETENTION_DAYS days)..."

if [ "$DRY_RUN" = false ]; then
    DELETED=$(find "$BACKUP_DIR" -name "dump_*.rdb.gz" -mtime +$RETENTION_DAYS -print -delete)
    DELETED_COUNT=$(echo "$DELETED" | wc -l)
    if [ $DELETED_COUNT -gt 0 ]; then
        log_info "Deleted $DELETED_COUNT old backup(s)"
    else
        log_info "No old backups to delete"
    fi
else
    OLD_BACKUPS=$(find "$BACKUP_DIR" -name "dump_*.rdb.gz" -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)
    log_info "[DRY-RUN] Would delete $OLD_BACKUPS old backup(s)"
fi

# 上传到远程存储
if [ "$REMOTE_SYNC" = "true" ]; then
    log_info "Syncing to remote storage: $S3_BUCKET"

    if [ "$DRY_RUN" = false ]; then
        if command -v aws > /dev/null 2>&1; then
            aws s3 sync "$BACKUP_DIR" "$S3_BUCKET" --delete
            log_info "Remote sync completed"
        else
            log_warn "AWS CLI not found, skipping remote sync"
        fi
    else
        log_info "[DRY-RUN] Would sync to: $S3_BUCKET"
    fi
fi

# 生成备份报告
if [ "$DRY_RUN" = false ]; then
    REPORT_FILE="$BACKUP_DIR/backup_report_$TIMESTAMP.json"
    cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "backup_file": "$COMPRESSED_FILE",
  "file_size_bytes": $FILE_SIZE,
  "sha256_checksum": "$CHECKSUM",
  "redis_host": "$REDIS_HOST",
  "redis_port": $REDIS_PORT,
  "retention_days": $RETENTION_DAYS,
  "status": "success"
}
EOF
    log_info "Backup report saved to: $REPORT_FILE"
fi

log_info "Redis backup completed successfully!"
