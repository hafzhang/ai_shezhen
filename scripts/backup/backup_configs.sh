#!/bin/bash
# 配置文件备份脚本
# Backup configuration files and push to Git
#
# Usage:
#   ./backup_configs.sh [dry-run]
#
# Author: Ralph Agent
# Date: 2026-02-21

set -e

# 配置 / Configuration
PROJECT_DIR="${PROJECT_DIR:-/opt/shezhen}"
BACKUP_DIR="${BACKUP_DIR:-/data/backups/configs}"
GIT_COMMIT="${GIT_COMMIT:-true}"
GIT_REMOTE="${GIT_REMOTE:-origin}"

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

log_info "Starting config backup process at $TIMESTAMP"

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    log_error "Project directory not found: $PROJECT_DIR"
    exit 1
fi

# 创建备份目录
log_info "Creating backup directory: $BACKUP_DIR"
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$BACKUP_DIR"
fi

# 备份计数
BACKUP_COUNT=0

# 1. 备份 Docker Compose 配置
log_info "Backing up Docker Compose configuration..."
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
    BACKUP_FILE="$BACKUP_DIR/docker-compose_$TIMESTAMP.yml"
    if [ "$DRY_RUN" = false ]; then
        cp "$COMPOSE_FILE" "$BACKUP_FILE"
        log_info "  Created: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    else
        log_info "  [DRY-RUN] Would create: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
fi

# 2. 备份环境变量文件
log_info "Backing up environment files..."
ENV_FILES=(
    "$PROJECT_DIR/api_service/.env"
    "$PROJECT_DIR/.env"
    "$PROJECT_DIR/api_service/.env.example"
)

for env_file in "${ENV_FILES[@]}"; do
    if [ -f "$env_file" ]; then
        filename=$(basename "$env_file")
        BACKUP_FILE="$BACKUP_DIR/${filename}_$TIMESTAMP"
        if [ "$DRY_RUN" = false ]; then
            # 过滤敏感信息（可选）
            cp "$env_file" "$BACKUP_FILE"
            log_info "  Created: $BACKUP_FILE"
            BACKUP_COUNT=$((BACKUP_COUNT + 1))
        else
            log_info "  [DRY-RUN] Would create: $BACKUP_FILE"
            BACKUP_COUNT=$((BACKUP_COUNT + 1))
        fi
    fi
done

# 3. 备份 Prometheus 配置
log_info "Backing up Prometheus configuration..."
PROM_DIR="$PROJECT_DIR/prometheus"
if [ -d "$PROM_DIR" ]; then
    BACKUP_FILE="$BACKUP_DIR/prometheus_config_$TIMESTAMP.tar.gz"
    if [ "$DRY_RUN" = false ]; then
        tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" prometheus/
        log_info "  Created: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    else
        log_info "  [DRY-RUN] Would create: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
fi

# 4. 备份 Grafana 配置
log_info "Backing up Grafana configuration..."
GRAFANA_DIR="$PROJECT_DIR/grafana"
if [ -d "$GRAFANA_DIR" ]; then
    BACKUP_FILE="$BACKUP_DIR/grafana_config_$TIMESTAMP.tar.gz"
    if [ "$DRY_RUN" = false ]; then
        tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" grafana/
        log_info "  Created: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    else
        log_info "  [DRY-RUN] Would create: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
fi

# 5. 备份 ELK 配置
log_info "Backing up ELK configuration..."
ELK_DIR="$PROJECT_DIR/elk"
if [ -d "$ELK_DIR" ]; then
    BACKUP_FILE="$BACKUP_DIR/elk_config_$TIMESTAMP.tar.gz"
    if [ "$DRY_RUN" = false ]; then
        tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" elk/
        log_info "  Created: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    else
        log_info "  [DRY-RUN] Would create: $BACKUP_FILE"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
fi

# Git 提交
if [ "$GIT_COMMIT" = "true" ]; then
    log_info "Committing to Git..."

    if [ "$DRY_RUN" = false ]; then
        cd "$PROJECT_DIR"

        # 检查是否为 Git 仓库
        if git rev-parse --git-dir > /dev/null 2>&1; then
            # 添加配置文件
            git add docker-compose.yml api_service/.env 2>/dev/null || true
            git add prometheus/ grafana/ elk/ 2>/dev/null || true

            # 提交
            git commit -m "Backup configs: $TIMESTAMP" > /dev/null 2>&1 || {
                log_warn "No changes to commit or commit failed"
            }

            # 推送（可选）
            if [ -n "$GIT_REMOTE" ]; then
                log_info "Pushing to remote: $GIT_REMOTE"
                git push "$GIT_REMOTE" main 2>/dev/null || \
                git push "$GIT_REMOTE" master 2>/dev/null || \
                log_warn "Git push failed or not configured"
            fi

            log_info "Git commit completed"
        else
            log_warn "Not a Git repository, skipping Git operations"
        fi
    else
        log_info "[DRY-RUN] Would commit to Git"
    fi
fi

# 生成备份报告
if [ "$DRY_RUN" = false ]; then
    REPORT_FILE="$BACKUP_DIR/backup_report_$TIMESTAMP.json"
    cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "files_backed_up": $BACKUP_COUNT,
  "project_dir": "$PROJECT_DIR",
  "backup_dir": "$BACKUP_DIR",
  "git_commit": $GIT_COMMIT,
  "status": "success"
}
EOF
    log_info "Backup report saved to: $REPORT_FILE"

    log_info "=== Backup Summary ==="
    log_info "Files backed up: $BACKUP_COUNT"
    log_info "Backup directory: $BACKUP_DIR"
fi

log_info "Config backup completed successfully!"
