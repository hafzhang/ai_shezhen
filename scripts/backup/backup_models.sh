#!/bin/bash
# 模型文件备份脚本
# Backup model files with compression and checksums
#
# Usage:
#   ./backup_models.sh [dry-run]
#
# Author: Ralph Agent
# Date: 2026-02-21

set -e

# 配置 / Configuration
MODELS_DIR="${MODELS_DIR:-/app/models}"
BACKUP_DIR="${BACKUP_DIR:-/data/backups/models}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"
REMOTE_SYNC="${REMOTE_SYNC:-false}"
S3_BUCKET="${S3_BUCKET:-s3://shezhen-backups/models}"

# 颜色输出 / Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

log_info "Starting model backup process at $TIMESTAMP"

# 检查模型目录
if [ ! -d "$MODELS_DIR" ]; then
    log_error "Models directory not found: $MODELS_DIR"
    exit 1
fi

# 创建备份目录
log_info "Creating backup directory: $BACKUP_DIR"
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$BACKUP_DIR"
fi

# 查找所有模型目录
MODEL_DIRS=$(find "$MODELS_DIR" -type d -mindepth 1 -maxdepth 2)

if [ -z "$MODEL_DIRS" ]; then
    log_warn "No model directories found in $MODELS_DIR"
    exit 0
fi

# 统计信息
TOTAL_MODELS=0
TOTAL_SIZE=0

# 备份每个模型目录
while IFS= read -r model_dir; do
    model_name=$(basename "$model_dir")
    log_info "Backing up model: $model_name"

    # 查找模型文件（.pdparams, .pdmodel, .onnx 等）
    MODEL_FILES=$(find "$model_dir" \( -name "*.pdparams" -o -name "*.pdmodel" -o -name "*.onnx" -o -name "*.pt" -o -name "*.pth" \) 2>/dev/null)

    if [ -z "$MODEL_FILES" ]; then
        log_warn "No model files found in $model_dir"
        continue
    fi

    # 创建临时目录
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT

    # 复制文件到临时目录
    while IFS= read -r model_file; do
        rel_path="${model_file#$MODELS_DIR/}"
        dest_dir="$TEMP_DIR/$(dirname "$rel_path")"
        mkdir -p "$dest_dir"
        cp "$model_file" "$dest_dir/"
    done <<< "$MODEL_FILES"

    # 创建压缩包
    BACKUP_FILE="$BACKUP_DIR/${model_name}_$TIMESTAMP.tar.gz"

    if [ "$DRY_RUN" = false ]; then
        tar -czf "$BACKUP_FILE" -C "$TEMP_DIR" .

        # 计算文件大小和校验和
        FILE_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null)
        CHECKSUM=$(sha256sum "$BACKUP_FILE" | cut -d' ' -f1)

        # 保存校验和
        echo "$CHECKSUM  $BACKUP_FILE" > "$BACKUP_FILE.sha256"

        log_info "  Created: $BACKUP_FILE"
        log_info "  Size: $FILE_SIZE bytes"
        log_info "  SHA-256: $CHECKSUM"

        TOTAL_MODELS=$((TOTAL_MODELS + 1))
        TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
    else
        ESTIMATED_SIZE=$(du -sb "$TEMP_DIR" | cut -f1)
        log_info "  [DRY-RUN] Would create: $BACKUP_FILE (~$ESTIMATED_SIZE bytes)"
        TOTAL_MODELS=$((TOTAL_MODELS + 1))
    fi

done <<< "$MODEL_DIRS"

# 清理旧备份
log_info "Cleaning up old backups (older than $RETENTION_WEEKS weeks)..."

if [ "$DRY_RUN" = false ]; then
    DELETED=$(find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$((RETENTION_WEEKS * 7)) -print -delete)
    DELETED_COUNT=$(echo "$DELETED" | grep -c "^" || echo "0")

    # 同时清理校验和文件
    find "$BACKUP_DIR" -name "*.sha256" -mtime +$((RETENTION_WEEKS * 7)) -delete

    if [ "$DELETED_COUNT" -gt 0 ]; then
        log_info "Deleted $DELETED_COUNT old backup(s)"
    else
        log_info "No old backups to delete"
    fi
else
    OLD_BACKUPS=$(find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$((RETENTION_WEEKS * 7)) 2>/dev/null | wc -l)
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
  "models_backuped": $TOTAL_MODELS,
  "total_size_bytes": $TOTAL_SIZE,
  "backup_dir": "$BACKUP_DIR",
  "models_dir": "$MODELS_DIR",
  "retention_weeks": $RETENTION_WEEKS,
  "status": "success"
}
EOF
    log_info "Backup report saved to: $REPORT_FILE"

    # 输出摘要
    log_info "=== Backup Summary ==="
    log_info "Models backed up: $TOTAL_MODELS"
    log_info "Total size: $TOTAL_SIZE bytes"
    log_info "Backup directory: $BACKUP_DIR"
fi

log_info "Model backup completed successfully!"
