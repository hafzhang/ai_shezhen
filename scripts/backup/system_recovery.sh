#!/bin/bash
# 系统恢复脚本
# System recovery script for disaster recovery
#
# Usage:
#   ./system_recovery.sh [--backup-dir DIR] [--full]
#
# Options:
#   --backup-dir DIR  Specify backup directory (default: /data/backups)
#   --full           Perform full system recovery (including configs)
#   --dry-run        Show what would be done without making changes
#
# Author: Ralph Agent
# Date: 2026-02-21

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}==>${NC} $1"
}

# 解析参数
BACKUP_DIR="/data/backups"
FULL_RECOVERY=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --full)
            FULL_RECOVERY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--backup-dir DIR] [--full] [--dry-run]"
            exit 1
            ;;
    esac
done

# 项目目录
PROJECT_DIR="${PROJECT_DIR:-/opt/shezhen}"

log_info "Starting system recovery process..."
log_info "Backup directory: $BACKUP_DIR"
log_info "Project directory: $PROJECT_DIR"
log_info "Full recovery: $FULL_RECOVERY"

if [ "$DRY_RUN" = true ]; then
    log_warn "Running in DRY-RUN mode, no changes will be made"
fi

# 确认
if [ "$DRY_RUN" = false ]; then
    echo ""
    read -p "This will perform system recovery. Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Recovery cancelled by user"
        exit 0
    fi
fi

echo ""

# ============================================================================
# Step 1: Stop all services
# ============================================================================
log_step "Step 1: Stopping all services..."

if [ "$DRY_RUN" = false ]; then
    cd "$PROJECT_DIR"
    docker compose down
    log_info "All services stopped"
else
    log_info "[DRY-RUN] Would stop all services"
fi

# ============================================================================
# Step 2: Restore configuration files (if full recovery)
# ============================================================================
if [ "$FULL_RECOVERY" = true ]; then
    log_step "Step 2: Restoring configuration files..."

    # 恢复环境变量
    LATEST_ENV=$(ls -t "$BACKUP_DIR/configs"/env_* 2>/dev/null | head -1)
    if [ -n "$LATEST_ENV" ]; then
        log_info "Restoring environment files from: $LATEST_ENV"
        if [ "$DRY_RUN" = false ]; then
            cp "$LATEST_ENV" "$PROJECT_DIR/api_service/.env"
        fi
    else
        log_warn "No environment backup found"
    fi

    # 恢复 Docker Compose 配置
    LATEST_COMPOSE=$(ls -t "$BACKUP_DIR/configs"/docker-compose_* 2>/dev/null | head -1)
    if [ -n "$LATEST_COMPOSE" ]; then
        log_info "Restoring docker-compose.yml from: $LATEST_COMPOSE"
        if [ "$DRY_RUN" = false ]; then
            cp "$LATEST_COMPOSE" "$PROJECT_DIR/docker-compose.yml"
        fi
    else
        log_warn "No docker-compose backup found"
    fi

    # 恢复 Prometheus 配置
    LATEST_PROM=$(ls -t "$BACKUP_DIR/configs"/prometheus_config_*.tar.gz 2>/dev/null | head -1)
    if [ -n "$LATEST_PROM" ]; then
        log_info "Restoring Prometheus configuration from: $LATEST_PROM"
        if [ "$DRY_RUN" = false ]; then
            tar -xzf "$LATEST_PROM" -C "$PROJECT_DIR"
        fi
    else
        log_warn "No Prometheus backup found"
    fi

    # 恢复 Grafana 配置
    LATEST_GRAFANA=$(ls -t "$BACKUP_DIR/configs"/grafana_config_*.tar.gz 2>/dev/null | head -1)
    if [ -n "$LATEST_GRAFANA" ]; then
        log_info "Restoring Grafana configuration from: $LATEST_GRAFANA"
        if [ "$DRY_RUN" = false ]; then
            tar -xzf "$LATEST_GRAFANA" -C "$PROJECT_DIR"
        fi
    else
        log_warn "No Grafana backup found"
    fi
fi

# ============================================================================
# Step 3: Restore model files
# ============================================================================
log_step "Step 3: Restoring model files..."

# 查找最新的模型备份
LATEST_MODEL_BACKUP=$(ls -t "$BACKUP_DIR/models"/segment*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_MODEL_BACKUP" ]; then
    log_info "Restoring segment model from: $LATEST_MODEL_BACKUP"

    # 验证校验和
    CHECKSUM_FILE="${LATEST_MODEL_BACKUP}.sha256"
    if [ -f "$CHECKSUM_FILE" ]; then
        log_info "Verifying checksum..."
        if [ "$DRY_RUN" = false ]; then
            if sha256sum -c "$CHECKSUM_FILE" > /dev/null 2>&1; then
                log_info "Checksum verification passed"
            else
                log_error "Checksum verification failed!"
                read -p "Continue anyway? (yes/no): " continue
                if [ "$continue" != "yes" ]; then
                    exit 1
                fi
            fi
        fi
    fi

    if [ "$DRY_RUN" = false ]; then
        # 提取到临时目录
        TEMP_DIR=$(mktemp -d)
        tar -xzf "$LATEST_MODEL_BACKUP" -C "$TEMP_DIR"

        # 复制到模型目录
        mkdir -p "$PROJECT_DIR/models/deploy"
        cp -r "$TEMP_DIR"/* "$PROJECT_DIR/models/deploy/"

        # 清理
        rm -rf "$TEMP_DIR"

        log_info "Model files restored"
    fi
else
    log_warn "No segment model backup found"
fi

# 查找分类模型备份
LATEST_CLAS_MODEL_BACKUP=$(ls -t "$BACKUP_DIR/models"/classify*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_CLAS_MODEL_BACKUP" ]; then
    log_info "Restoring classify model from: $LATEST_CLAS_MODEL_BACKUP"
    if [ "$DRY_RUN" = false ]; then
        TEMP_DIR=$(mktemp -d)
        tar -xzf "$LATEST_CLAS_MODEL_BACKUP" -C "$TEMP_DIR"
        cp -r "$TEMP_DIR"/* "$PROJECT_DIR/models/deploy/"
        rm -rf "$TEMP_DIR"
        log_info "Classification model restored"
    fi
fi

# ============================================================================
# Step 4: Restore Redis data
# ============================================================================
log_step "Step 4: Restoring Redis data..."

LATEST_REDIS_BACKUP=$(ls -t "$BACKUP_DIR/redis"/dump_*.rdb.gz 2>/dev/null | head -1)
if [ -n "$LATEST_REDIS_BACKUP" ]; then
    log_info "Restoring Redis data from: $LATEST_REDIS_BACKUP"

    # 验证校验和
    CHECKSUM_FILE="${LATEST_REDIS_BACKUP}.sha256"
    if [ -f "$CHECKSUM_FILE" ]; then
        log_info "Verifying checksum..."
        if [ "$DRY_RUN" = false ]; then
            if sha256sum -c "$CHECKSUM_FILE" > /dev/null 2>&1; then
                log_info "Checksum verification passed"
            else
                log_error "Checksum verification failed!"
                read -p "Continue anyway? (yes/no): " continue
                if [ "$continue" != "yes" ]; then
                    exit 1
                fi
            fi
        fi
    fi

    if [ "$DRY_RUN" = false ]; then
        # 解压到 Redis 数据目录
        REDIS_DATA_DIR="/var/lib/docker/volumes/shezhen_redis_data/_data"

        # 备份当前数据（如果有）
        if [ -f "$REDIS_DATA_DIR/dump.rdb" ]; then
            cp "$REDIS_DATA_DIR/dump.rdb" "$REDIS_DATA_DIR/dump.rdb.corrupted"
            log_info "Current Redis data backed up to dump.rdb.corrupted"
        fi

        # 解压新数据
        gunzip -c "$LATEST_REDIS_BACKUP" > "$REDIS_DATA_DIR/dump.rdb"

        log_info "Redis data restored"
    fi
else
    log_warn "No Redis backup found"
fi

# ============================================================================
# Step 5: Start all services
# ============================================================================
log_step "Step 5: Starting all services..."

if [ "$DRY_RUN" = false ]; then
    cd "$PROJECT_DIR"
    docker compose up -d

    log_info "Waiting for services to start..."
    sleep 30
else
    log_info "[DRY-RUN] Would start all services"
fi

# ============================================================================
# Step 6: Verify services
# ============================================================================
log_step "Step 6: Verifying service health..."

VERIFY_FAILED=0

# 检查 API 服务
log_info "Checking API service..."
if [ "$DRY_RUN" = false ]; then
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log_info "✓ API service is healthy"
    else
        log_error "✗ API service health check failed"
        VERIFY_FAILED=1
    fi
fi

# 检查 Redis
log_info "Checking Redis..."
if [ "$DRY_RUN" = false ]; then
    if docker exec shezhen-redis redis-cli ping > /dev/null 2>&1; then
        log_info "✓ Redis is healthy"
    else
        log_error "✗ Redis health check failed"
        VERIFY_FAILED=1
    fi
fi

# 检查 Elasticsearch (如果启用)
if docker ps | grep -q shezhen-elasticsearch; then
    log_info "Checking Elasticsearch..."
    if [ "$DRY_RUN" = false ]; then
        if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then
            log_info "✓ Elasticsearch is healthy"
        else
            log_error "✗ Elasticsearch health check failed"
            VERIFY_FAILED=1
        fi
    fi
fi

# ============================================================================
# Step 7: Generate recovery report
# ============================================================================
log_step "Step 7: Generating recovery report..."

RECOVERY_REPORT="$BACKUP_DIR/recovery_report_$(date +%Y%m%d_%H%M%S).json"

if [ "$DRY_RUN" = false ]; then
    cat > "$RECOVERY_REPORT" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "backup_dir": "$BACKUP_DIR",
  "project_dir": "$PROJECT_DIR",
  "full_recovery": $FULL_RECOVERY,
  "restored_components": {
    "configs": $FULL_RECOVERY,
    "models": $( [ -n "$LATEST_MODEL_BACKUP" ] && echo "true" || echo "false" ),
    "redis": $( [ -n "$LATEST_REDIS_BACKUP" ] && echo "true" || echo "false" )
  },
  "verification": {
    "all_passed": $( [ $VERIFY_FAILED -eq 0 ] && echo "true" || echo "false" )
  },
  "status": "$( [ $VERIFY_FAILED -eq 0 ] && echo "success" || echo "partial" )"
}
EOF

    log_info "Recovery report saved to: $RECOVERY_REPORT"
fi

# ============================================================================
# Complete
# ============================================================================
echo ""
if [ $VERIFY_FAILED -eq 0 ]; then
    log_info "=== System Recovery Completed Successfully ==="
else
    log_warn "=== System Recovery Completed with Errors ==="
    log_warn "Some services may not be functioning correctly"
    log_warn "Please check the logs above and manually resolve any issues"
fi

exit $VERIFY_FAILED
