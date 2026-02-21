# 灾备方案与高可用配置指南
# Disaster Recovery and High Availability Configuration Guide

## 目录 / Table of Contents

1. [概述](#概述)
2. [系统架构](#系统架构)
3. [灾备策略](#灾备策略)
4. [备份策略](#备份策略)
5. [故障转移机制](#故障转移机制)
6. [恢复流程](#恢复流程)
7. [监控告警](#监控告警)
8. [演练计划](#演练计划)
9. [附录](#附录)

---

## 概述 / Overview

本文档描述了AI舌诊智能诊断系统的灾备方案与高可用配置，确保系统在发生故障时能够快速恢复，保证服务连续性。

### 目标 / Goals

| 指标 | 目标值 | 说明 |
|------|--------|------|
| RPO (恢复点目标) | ≤ 1小时 | 数据丢失容忍时间 |
| RTO (恢复时间目标) | ≤ 5分钟 | 服务恢复时间 |
| 可用性 | ≥ 99.9% | 年度停机时间 < 8.76小时 |
| 数据持久性 | ≥ 99.999999% | 11个9的可靠性 |

### 覆盖范围 / Coverage

- **应用服务**: FastAPI、Celery Worker、Celery Beat
- **数据存储**: Redis、Elasticsearch、MLflow
- **配置文件**: 环境变量、配置文件
- **模型文件**: 训练好的模型权重
- **日志数据**: 审计日志、应用日志

---

## 系统架构 / System Architecture

### 主备架构 / Primary-Standby Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Load Balancer (Nginx)        │
                    │         (Production / DR)            │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────┴───────────────────┐
                    │                                       │
         ┌──────────▼──────────┐              ┌───────────▼──────────┐
         │   Primary Region    │              │    DR Region         │
         │   (Production)      │              │    (Standby)         │
         │                     │              │                      │
         │  ┌───────────────┐  │              │  ┌───────────────┐   │
         │  │ API Service   │  │              │  │ API Service   │   │
         │  │ (Active)      │  │              │  │ (Standby)      │   │
         │  └───────────────┘  │              │  └───────────────┘   │
         │  ┌───────────────┐  │              │  ┌───────────────┐   │
         │  │ Celery Worker │  │              │  │ Celery Worker │   │
         │  │ (Active)      │  │              │  │ (Standby)      │   │
         │  └───────────────┘  │              │  └───────────────┘   │
         │  ┌───────────────┐  │              │  ┌───────────────┐   │
         │  │ Redis         │  │              │  │ Redis         │   │
         │  │ (Master)      │  │              │  │ (Slave)       │   │
         │  └───────┬───────┘  │              │  └───────┬───────┘   │
         │          │          │              │          │           │
         └──────────┼──────────┘              └──────────┼───────────┘
                    │                                       │
                    └──────────────────┬────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │  Shared Storage │
                              │  (NFS / S3)     │
                              │  - Backups      │
                              │  - Models       │
                              │  - Configs      │
                              └─────────────────┘
```

### 单节点高可用方案 / Single Node HA (当前实现)

对于小型部署，使用以下单节点高可用方案：

```
┌─────────────────────────────────────────────────────────┐
│                  Single Host HA                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │   API    │  │  Celery  │  │  Redis   │             │
│  │ (Active) │  │ (Active) │  │ (Active) │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │            │             │                    │
│       └────────────┴─────────────┘                    │
│                    │                                  │
│       ┌────────────▼────────────┐                     │
│       │  Health Check (Cron)    │                     │
│       │  - Monitor Services     │                     │
│       │  - Auto Restart         │                     │
│       │  - Alert on Failure     │                     │
│       └─────────────────────────┘                     │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │  Backup Strategy                         │          │
│  │  - Daily DB Snapshot (00:00)            │          │
│  │  - Weekly Model Backup (Sunday)          │          │
│  │  - Config Version Control (Git)          │          │
│  │  - Log Archival (S3/NFS)                 │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

---

## 灾备策略 / Disaster Recovery Strategy

### 备份级别 / Backup Levels

| 级别 | 类型 | 频率 | 保留期 | 存储位置 |
|------|------|------|--------|----------|
| L1 | 数据库快照 | 每日 | 7天 | 本地 + 远程 |
| L2 | 完整备份 | 每周 | 4周 | 远程存储 |
| L3 | 归档备份 | 每月 | 12个月 | 对象存储 |

### 服务健康检查 / Health Check

```python
# 健康检查配置
HEALTH_CHECK_CONFIG = {
    "endpoints": {
        "api": "http://localhost:8000/health",
        "redis": "http://localhost:6379",
        "elasticsearch": "http://localhost:9200/_cluster/health",
    },
    "interval_seconds": 30,
    "timeout_seconds": 5,
    "failure_threshold": 3,  # 连续失败3次触发告警
    "recovery_threshold": 2,  # 连续成功2次解除告警
}
```

### 自动重启策略 / Auto-Restart Policy

```yaml
# docker-compose.yml
services:
  api:
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## 备份策略 / Backup Strategy

### 1. Redis 数据备份 / Redis Backup

#### 自动备份脚本 / Automated Backup Script

```bash
#!/bin/bash
# backup_redis.sh - Redis 数据备份脚本

set -e

BACKUP_DIR="/data/backups/redis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 触发 Redis BGSAVE
echo "[$TIMESTAMP] Starting Redis backup..."
redis-cli BGSAVE

# 等待备份完成
while [ $(redis-cli LASTSAVE) -lt $(date +%s -d '1 minute ago') ]; do
    echo "Waiting for BGSAVE to complete..."
    sleep 5
done

# 复制 RDB 文件
cp /var/lib/redis/dump.rdb "$BACKUP_DIR/dump_$TIMESTAMP.rdb"

# 压缩备份
gzip "$BACKUP_DIR/dump_$TIMESTAMP.rdb"

# 清理旧备份
find "$BACKUP_DIR" -name "*.rdb.gz" -mtime +$RETENTION_DAYS -delete

# 上传到远程存储（可选）
# aws s3 cp "$BACKUP_DIR/dump_$TIMESTAMP.rdb.gz" s3://backups/redis/

echo "[$TIMESTAMP] Redis backup completed: dump_$TIMESTAMP.rdb.gz"
```

#### Cron 配置 / Cron Configuration

```bash
# /etc/cron.d/shezhen-backups
# 每天凌晨 2:00 执行 Redis 备份
0 2 * * * root /opt/scripts/backup_redis.sh >> /var/log/redis_backup.log 2>&1
```

### 2. 模型文件备份 / Model Backup

```bash
#!/bin/bash
# backup_models.sh - 模型文件备份脚本

set -e

MODELS_DIR="/app/models"
BACKUP_DIR="/data/backups/models"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_WEEKS=4

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份模型文件
echo "[$TIMESTAMP] Starting model backup..."

for model_dir in "$MODELS_DIR"/*; do
    model_name=$(basename "$model_dir")
    echo "Backing up $model_name..."

    # 创建压缩包
    tar -czf "$BACKUP_DIR/${model_name}_$TIMESTAMP.tar.gz" -C "$MODELS_DIR" "$model_name"

    # 计算校验和
    sha256sum "$BACKUP_DIR/${model_name}_$TIMESTAMP.tar.gz" > "$BACKUP_DIR/${model_name}_$TIMESTAMP.sha256"
done

# 清理旧备份
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$((RETENTION_WEEKS * 7)) -delete
find "$BACKUP_DIR" -name "*.sha256" -mtime +$((RETENTION_WEEKS * 7)) -delete

echo "[$TIMESTAMP] Model backup completed"
```

### 3. 配置文件备份 / Configuration Backup

```bash
#!/bin/bash
# backup_configs.sh - 配置文件备份脚本

set -e

CONFIG_DIR="/app/config"
BACKUP_DIR="/data/backups/configs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份配置文件
echo "[$TIMESTAMP] Starting config backup..."

# 1. Docker Compose 配置
cp /opt/shezhen/docker-compose.yml "$BACKUP_DIR/docker-compose_$TIMESTAMP.yml"

# 2. 环境变量
cp /opt/shezhen/api_service/.env "$BACKUP_DIR/env_$TIMESTAMP"

# 3. Prometheus 配置
tar -czf "$BACKUP_DIR/prometheus_config_$TIMESTAMP.tar.gz" -C /opt/shezhen/prometheus .

# 4. Grafana 配置
tar -czf "$BACKUP_DIR/grafana_config_$TIMESTAMP.tar.gz" -C /opt/shezhen/grafana .

# 5. 提交到 Git（可选）
cd /opt/shezhen
git add docker-compose.yml api_service/.env
git commit -m "Backup configs: $TIMESTAMP"
git push origin main

echo "[$TIMESTAMP] Config backup completed"
```

### 4. Elasticsearch 日志备份 / Log Backup

```bash
#!/bin/bash
# backup_elasticsearch.sh - Elasticsearch 日志备份脚本

set -e

ES_HOST="localhost:9200"
ES_USER="elastic"
ES_PASSWORD="${ELASTICSEARCH_PASSWORD}"
BACKUP_DIR="/data/backups/elasticsearch"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 注册快照仓库（如果不存在）
echo "[$TIMESTAMP] Registering snapshot repository..."
curl -u "$ES_USER:$ES_PASSWORD" -X PUT "$ES_HOST/_snapshot/backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "'"$BACKUP_DIR"'"
  }
}'

# 创建快照
echo "[$TIMESTAMP] Creating Elasticsearch snapshot..."
curl -u "$ES_USER:$ES_PASSWORD" -X PUT "$ES_HOST/_snapshot/backup/snapshot_$TIMESTAMP?wait_for_completion=true"

# 清理旧快照（保留7天）
OLD_SNAPSHOTS=$(curl -s -u "$ES_USER:$ES_PASSWORD" "$ES_HOST/_snapshot/backup/_all" | jq -r '.snapshots[] | select(.start_time_in_millis < (now - 604800000)) | .snapshot')
for snapshot in $OLD_SNAPSHOTS; do
    echo "Deleting old snapshot: $snapshot"
    curl -u "$ES_USER:$ES_PASSWORD" -X DELETE "$ES_HOST/_snapshot/backup/$snapshot"
done

echo "[$TIMESTAMP] Elasticsearch backup completed"
```

### 5. 综合备份脚本 / Unified Backup Script

```python
#!/usr/bin/env python3
# unified_backup.py - 统一备份管理脚本

import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/shezhen_backup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BackupManager:
    """备份管理器"""

    def __init__(self, config_path="/opt/shezhen/backup_config.json"):
        self.config = self._load_config(config_path)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _load_config(self, config_path):
        """加载备份配置"""
        default_config = {
            "backup_dir": "/data/backups",
            "redis": {
                "enabled": True,
                "host": "localhost",
                "port": 6379,
                "retention_days": 7
            },
            "models": {
                "enabled": True,
                "source_dir": "/app/models",
                "retention_weeks": 4
            },
            "configs": {
                "enabled": True,
                "source_dir": "/opt/shezhen",
                "git_commit": True
            },
            "elasticsearch": {
                "enabled": True,
                "host": "localhost",
                "port": 9200,
                "username": "elastic",
                "password_file": "/etc/elasticsearch_password"
            },
            "remote": {
                "enabled": False,
                "s3_bucket": "s3://shezhen-backups",
                "nfs_mount": "/mnt/backups"
            }
        }

        if os.path.exists(config_path):
            with open(config_path) as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config

    def backup_redis(self):
        """备份 Redis 数据"""
        if not self.config["redis"]["enabled"]:
            logger.info("Redis backup is disabled")
            return

        logger.info("Starting Redis backup...")

        backup_dir = Path(self.config["backup_dir"]) / "redis"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 触发 BGSAVE
        subprocess.run(
            ["redis-cli", "-h", self.config["redis"]["host"],
             "-p", str(self.config["redis"]["port"]), "BGSAVE"],
            check=True
        )

        # 等待备份完成并复制文件
        # ... (完整实现)

        logger.info(f"Redis backup completed: redis_backup_{self.timestamp}.rdb.gz")

    def backup_models(self):
        """备份模型文件"""
        if not self.config["models"]["enabled"]:
            logger.info("Model backup is disabled")
            return

        logger.info("Starting model backup...")

        source_dir = Path(self.config["models"]["source_dir"])
        backup_dir = Path(self.config["backup_dir"]) / "models"
        backup_dir.mkdir(parents=True, exist_ok=True)

        for model_path in source_dir.glob("**/*.pdparams"):
            relative_path = model_path.relative_to(source_dir)
            backup_path = backup_dir / f"{relative_path.stem}_{self.timestamp}.tar.gz"

            # 创建压缩包
            subprocess.run([
                "tar", "-czf", str(backup_path),
                "-C", str(source_dir), str(relative_path.parent)
            ], check=True)

        logger.info(f"Model backup completed")

    def backup_configs(self):
        """备份配置文件"""
        if not self.config["configs"]["enabled"]:
            logger.info("Config backup is disabled")
            return

        logger.info("Starting config backup...")

        # 复制配置文件
        # 如果启用，提交到 Git
        if self.config["configs"]["git_commit"]:
            subprocess.run([
                "git", "-C", self.config["configs"]["source_dir"],
                "add", "docker-compose.yml", "api_service/.env"
            ], check=True)
            subprocess.run([
                "git", "-C", self.config["configs"]["source_dir"],
                "commit", "-m", f"Backup configs: {self.timestamp}"
            ], check=True)

        logger.info("Config backup completed")

    def backup_elasticsearch(self):
        """备份 Elasticsearch 日志"""
        if not self.config["elasticsearch"]["enabled"]:
            logger.info("Elasticsearch backup is disabled")
            return

        logger.info("Starting Elasticsearch backup...")

        # 创建快照
        # ... (完整实现)

        logger.info("Elasticsearch backup completed")

    def upload_to_remote(self):
        """上传备份到远程存储"""
        if not self.config["remote"]["enabled"]:
            logger.info("Remote upload is disabled")
            return

        logger.info("Uploading backups to remote storage...")

        if "s3_bucket" in self.config["remote"]:
            # 上传到 S3
            subprocess.run([
                "aws", "s3", "sync",
                self.config["backup_dir"],
                self.config["remote"]["s3_bucket"]
            ], check=True)

        logger.info("Remote upload completed")

    def run_all_backups(self):
        """执行所有备份任务"""
        logger.info(f"Starting unified backup: {self.timestamp}")

        try:
            self.backup_redis()
            self.backup_models()
            self.backup_configs()
            self.backup_elasticsearch()
            self.upload_to_remote()

            # 生成备份报告
            self._generate_backup_report()

            logger.info("All backups completed successfully")
            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def _generate_backup_report(self):
        """生成备份报告"""
        report = {
            "timestamp": self.timestamp,
            "backups": {
                "redis": self.config["redis"]["enabled"],
                "models": self.config["models"]["enabled"],
                "configs": self.config["configs"]["enabled"],
                "elasticsearch": self.config["elasticsearch"]["enabled"]
            },
            "status": "success"
        }

        report_path = Path(self.config["backup_dir"]) / f"backup_report_{self.timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    manager = BackupManager()
    success = manager.run_all_backups()
    exit(0 if success else 1)
```

---

## 故障转移机制 / Failover Mechanism

### 服务健康监控 / Service Health Monitoring

```python
# health_monitor.py - 服务健康监控

import time
import requests
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict
import subprocess
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    service: str
    status: ServiceStatus
    response_time_ms: float
    message: str
    timestamp: float


class HealthMonitor:
    """健康监控器"""

    def __init__(self, config_path="/opt/shezhen/health_config.json"):
        self.services = self._load_config(config_path)
        self.failure_counts: Dict[str, int] = {}
        self.recovery_counts: Dict[str, int] = {}

    def _load_config(self, config_path):
        """加载监控配置"""
        default_config = {
            "api": {
                "url": "http://localhost:8000/health",
                "timeout": 5,
                "failure_threshold": 3,
                "recovery_threshold": 2
            },
            "redis": {
                "url": "http://localhost:6379",
                "timeout": 3,
                "failure_threshold": 3,
                "recovery_threshold": 2
            },
            "elasticsearch": {
                "url": "http://localhost:9200/_cluster/health",
                "timeout": 5,
                "failure_threshold": 5,
                "recovery_threshold": 3
            }
        }
        return default_config

    def check_service(self, service_name: str) -> HealthCheckResult:
        """检查单个服务健康状态"""
        config = self.services.get(service_name)
        if not config:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNKNOWN,
                response_time_ms=0,
                message="Service not configured",
                timestamp=time.time()
            )

        try:
            start_time = time.time()
            response = requests.get(
                config["url"],
                timeout=config["timeout"]
            )
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return HealthCheckResult(
                    service=service_name,
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    message="OK",
                    timestamp=time.time()
                )
            else:
                return HealthCheckResult(
                    service=service_name,
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=response_time,
                    message=f"HTTP {response.status_code}",
                    timestamp=time.time()
                )

        except requests.exceptions.Timeout:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=0,
                message="Timeout",
                timestamp=time.time()
            )
        except Exception as e:
            return HealthCheckResult(
                service=service_name,
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=0,
                message=str(e),
                timestamp=time.time()
            )

    def check_all_services(self) -> List[HealthCheckResult]:
        """检查所有服务"""
        results = []
        for service_name in self.services.keys():
            result = self.check_service(service_name)
            results.append(result)

            # 更新失败计数
            if result.status == ServiceStatus.UNHEALTHY:
                self.failure_counts[service_name] = \
                    self.failure_counts.get(service_name, 0) + 1
                self.recovery_counts[service_name] = 0
            else:
                self.recovery_counts[service_name] = \
                    self.recovery_counts.get(service_name, 0) + 1
                if self.recovery_counts[service_name] >= \
                        self.services[service_name]["recovery_threshold"]:
                    self.failure_counts[service_name] = 0

        return results

    def should_trigger_failover(self, service_name: str) -> bool:
        """判断是否应该触发故障转移"""
        threshold = self.services[service_name]["failure_threshold"]
        return self.failure_counts.get(service_name, 0) >= threshold

    def execute_failover(self, service_name: str):
        """执行故障转移"""
        logger.warning(f"Triggering failover for {service_name}...")

        if service_name == "api":
            self._restart_api_service()
        elif service_name == "redis":
            self._restart_redis_service()
        elif service_name == "elasticsearch":
            self._restart_elasticsearch_service()

    def _restart_api_service(self):
        """重启 API 服务"""
        logger.info("Restarting API service...")
        subprocess.run([
            "docker", "restart", "shezhen-api"
        ], check=True)

    def _restart_redis_service(self):
        """重启 Redis 服务"""
        logger.info("Restarting Redis service...")
        subprocess.run([
            "docker", "restart", "shezhen-redis"
        ], check=True)

    def _restart_elasticsearch_service(self):
        """重启 Elasticsearch 服务"""
        logger.info("Restarting Elasticsearch service...")
        subprocess.run([
            "docker", "restart", "shezhen-elasticsearch"
        ], check=True)

    def run_monitoring_loop(self, interval_seconds: int = 30):
        """运行监控循环"""
        logger.info("Starting health monitoring loop...")

        while True:
            results = self.check_all_services()

            # 记录状态
            for result in results:
                if result.status != ServiceStatus.HEALTHY:
                    logger.warning(
                        f"{result.service}: {result.status.value} - "
                        f"{result.message} "
                        f"(failures: {self.failure_counts.get(result.service, 0)})"
                    )

                # 检查是否需要故障转移
                if self.should_trigger_failover(result.service):
                    logger.error(
                        f"Service {result.service} has failed "
                        f"{self.failure_counts[result.service]} times, "
                        f"triggering failover..."
                    )
                    self.execute_failover(result.service)

            # 等待下次检查
            time.sleep(interval_seconds)


if __name__ == "__main__":
    monitor = HealthMonitor()
    monitor.run_monitoring_loop(interval_seconds=30)
```

### 自动故障转移脚本 / Auto-Failover Script

```bash
#!/bin/bash
# auto_failover.sh - 自动故障转移脚本

set -e

LOG_FILE="/var/log/shezhen_failover.log"
MAX_FAILURES=3
CHECK_INTERVAL=30

# 服务检查函数
check_service() {
    local service_name=$1
    local health_url=$2

    if curl -sf "$health_url" > /dev/null 2>&1; then
        echo "[$(date)] $service_name: HEALTHY" >> "$LOG_FILE"
        return 0
    else
        echo "[$(date)] $service_name: UNHEALTHY" >> "$LOG_FILE"
        return 1
    fi
}

# 故障计数器
declare -A failure_counts

# 主循环
while true; do
    # 检查 API 服务
    if ! check_service "API" "http://localhost:8000/health"; then
        failure_counts[api]=$((${failure_counts[api]:-0} + 1))

        if [ ${failure_counts[api]} -ge $MAX_FAILURES ]; then
            echo "[$(date)] API service failed ${failure_counts[api]} times, restarting..." >> "$LOG_FILE"
            docker restart shezhen-api
            failure_counts[api]=0
        fi
    else
        failure_counts[api]=0
    fi

    # 检查 Redis
    if ! check_service "Redis" "http://localhost:6379"; then
        failure_counts[redis]=$((${failure_counts[redis]:-0} + 1))

        if [ ${failure_counts[redis]} -ge $MAX_FAILURES ]; then
            echo "[$(date)] Redis failed ${failure_counts[redis]} times, restarting..." >> "$LOG_FILE"
            docker restart shezhen-redis
            failure_counts[redis]=0
        fi
    else
        failure_counts[redis]=0
    fi

    # 等待下次检查
    sleep $CHECK_INTERVAL
done
```

---

## 恢复流程 / Recovery Procedures

### 场景 1: API 服务故障 / API Service Failure

**症状**: API 服务无响应或返回错误

**恢复步骤**:

```bash
# 1. 检查服务状态
docker ps -a | grep shezhen-api

# 2. 查看日志
docker logs shezhen-api --tail 100

# 3. 尝试重启
docker restart shezhen-api

# 4. 如果重启失败，重新构建
cd /opt/shezhen
docker compose up -d --build api

# 5. 验证恢复
curl http://localhost:8000/health
```

### 场景 2: Redis 数据丢失 / Redis Data Loss

**症状**: Redis 启动但数据丢失

**恢复步骤**:

```bash
# 1. 停止 Redis
docker stop shezhen-redis

# 2. 备份当前数据（如果有）
cp /var/lib/docker/volumes/shezhen_redis_data/_data/dump.rdb \
   /tmp/dump.rdb.corrupted

# 3. 恢复最近的备份
LATEST_BACKUP=$(ls -t /data/backups/redis/*.rdb.gz | head -1)
gunzip -c "$LATEST_BACKUP" > \
  /var/lib/docker/volumes/shezhen_redis_data/_data/dump.rdb

# 4. 重启 Redis
docker start shezhen-redis

# 5. 验证数据
redis-cli DBSIZE
redis-cli GET "some:key"
```

### 场景 3: 模型文件损坏 / Model File Corruption

**症状**: 模型加载失败

**恢复步骤**:

```bash
# 1. 识别损坏的模型
docker logs shezhen-api | grep -i "error.*model"

# 2. 从备份恢复
LATEST_MODEL_BACKUP=$(ls -t /data/backups/models/*segment*.tar.gz | head -1)
tar -xzf "$LATEST_MODEL_BACKUP" -C /app/models/

# 3. 验证校验和
sha256sum -c /data/backups/models/*.sha256

# 4. 重启 API 服务
docker restart shezhen-api

# 5. 验证模型加载
curl http://localhost:8000/api/v1/health
```

### 场景 4: 完全系统恢复 / Full System Recovery

**恢复步骤**:

```bash
#!/bin/bash
# system_recovery.sh - 完整系统恢复脚本

set -e

echo "Starting full system recovery..."

# 1. 停止所有服务
echo "Stopping all services..."
cd /opt/shezhen
docker compose down

# 2. 恢复配置文件
echo "Restoring configurations..."
LATEST_CONFIG_BACKUP=$(ls -t /data/backups/configs/env_* | head -1)
cp "$LATEST_CONFIG_BACKUP" /opt/shezhen/api_service/.env

# 3. 恢复模型文件
echo "Restoring model files..."
LATEST_MODEL_BACKUP=$(ls -t /data/backups/models/*.tar.gz | head -1)
tar -xzf "$LATEST_MODEL_BACKUP" -C /app/models/

# 4. 恢复 Redis 数据
echo "Restoring Redis data..."
LATEST_REDIS_BACKUP=$(ls -t /data/backups/redis/*.rdb.gz | head -1)
gunzip -c "$LATEST_REDIS_BACKUP" > \
  /var/lib/docker/volumes/shezhen_redis_data/_data/dump.rdb

# 5. 启动所有服务
echo "Starting all services..."
docker compose up -d

# 6. 等待服务就绪
echo "Waiting for services to be ready..."
sleep 30

# 7. 验证服务状态
echo "Verifying service health..."
curl -sf http://localhost:8000/health || {
    echo "ERROR: API service health check failed"
    exit 1
}

redis-cli ping || {
    echo "ERROR: Redis health check failed"
    exit 1
}

echo "System recovery completed successfully!"
```

---

## 监控告警 / Monitoring and Alerting

### Prometheus 告警规则 / Prometheus Alert Rules

```yaml
# prometheus/dr_alerts.yml

groups:
  - name: disaster_recovery
    interval: 30s
    rules:
      # 服务完全不可用
      - alert: ServiceDown
        expr: up{job=~"api|celery-worker|redis"} == 0
        for: 2m
        labels:
          severity: critical
          priority: P0
        annotations:
          summary: "Service {{ $labels.job }} is down"
          description: "Service {{ $labels.job }} has been down for more than 2 minutes"
          runbook_url: "https://docs.shezhen.ai/runbooks/service-down"

      # 数据备份失败
      - alert: BackupFailed
        expr: shezhen_backup_success == 0
        for: 5m
        labels:
          severity: warning
          priority: P2
        annotations:
          summary: "Backup job failed"
          description: "The last backup job failed for {{ $labels.backup_type }}"

      # 磁盘空间不足
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes{mountpoint="/data"} / node_filesystem_size_bytes{mountpoint="/data"}) < 0.1
        for: 10m
        labels:
          severity: warning
          priority: P1
        annotations:
          summary: "Disk space low on /data"
          description: "Available disk space is below 10% on {{ $labels.instance }}"

      # Redis 内存使用过高
      - alert: RedisMemoryHigh
        expr: (redis_memory_used_bytes / redis_memory_max_bytes) > 0.9
        for: 5m
        labels:
          severity: warning
          priority: P2
        annotations:
          summary: "Redis memory usage high"
          description: "Redis is using more than 90% of max memory"

      # 恢复点过旧
      - alert: RecoveryPointTooOld
        expr: time() - shezhen_last_backup_timestamp > 7200
        for: 0s
        labels:
          severity: critical
          priority: P0
        annotations:
          summary: "Recovery point is too old"
          description: "Last successful backup was more than 2 hours ago"
```

### 告警通知配置 / Alert Notification Configuration

```yaml
# alertmanager/config.yml

receivers:
  # 邮件通知
  - name: 'email-alerts'
    email_configs:
      - to: 'alerts@shezhen.ai'
        from: 'alertmanager@shezhen.ai'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alertmanager@shezhen.ai'
        auth_password: '${SMTP_PASSWORD}'
        headers:
          Subject: '[ALERT] {{ .GroupLabels.alertname }}'

  # Webhook 通知
  - name: 'webhook-alerts'
    webhook_configs:
      - url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        send_resolved: true

# 路由配置
route:
  receiver: 'email-alerts'
  group_by: ['alertname', 'priority']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 12h
  routes:
    # P0 级别告警立即发送
    - match:
        priority: P0
      receiver: 'webhook-alerts'
      group_wait: 0s
      repeat_interval: 5m
```

---

## 演练计划 / Drill Plan

### 季度灾备演练 / Quarterly DR Drill

**目标**: 验证灾备方案的有效性

**频率**: 每季度一次

**演练场景**:

1. **第一季度 - API 服务故障恢复**
   - 模拟 API 服务崩溃
   - 验证自动重启机制
   - 测试手动恢复流程
   - 目标: RTO < 5分钟

2. **第二季度 - Redis 数据恢复**
   - 模拟 Redis 数据丢失
   - 从备份恢复数据
   - 验证数据完整性
   - 目标: RPO < 1小时

3. **第三季度 - 完整系统恢复**
   - 模拟完全系统故障
   - 执行完整恢复流程
   - 验证所有服务正常
   - 目标: RTO < 15分钟

4. **第四季度 - 灾难场景演练**
   - 模拟主数据中心不可用
   - 切换到备用环境
   - 验证业务连续性
   - 目标: RTO < 30分钟

### 演练记录表 / Drill Record Template

```markdown
# 灾备演练记录表

**日期**: YYYY-MM-DD
**演练场景**: [场景名称]
**负责人**: [姓名]
**参与人员**: [列表]

## 演练目标
- [ ] 目标1
- [ ] 目标2

## 演练步骤
| 时间 | 步骤 | 负责人 | 状态 | 备注 |
|------|------|--------|------|------|
| 00:00 | 开始演练 | | | |
| 00:05 | 触发故障 | | | |
| 00:10 | 检测告警 | | | |
| 00:15 | 开始恢复 | | | |

## 演练结果
- RTO (恢复时间): XX 分钟
- RPO (数据丢失): XX 分钟
- 成功/失败: [ ]

## 发现问题
1. 问题描述
2. 改进措施

## 经验教训
1. 经验1
2. 经验2

## 签字确认
负责人: ________  日期: ________
观察员: ________  日期: ________
```

---

## 附录 / Appendix

### A. 备份文件命名规范 / Backup File Naming Convention

```
<service>_<type>_<timestamp>.<extension>

示例:
- redis_dump_20260221_020000.rdb.gz
- models_segment_20260221_030000.tar.gz
- configs_env_20260221_production.env
- elasticsearch_snapshot_20260221_040000
```

### B. 紧急联系信息 / Emergency Contacts

| 角色 | 姓名 | 电话 | 邮箱 |
|------|------|------|------|
| 系统管理员 | | | |
| DBA | | | |
| 开发负责人 | | | |
| 业务负责人 | | | |

### C. 相关文档链接 / Related Documents

- [部署文档](./DOCKER_DEPLOYMENT.md)
- [监控配置](./MONITORING_SETUP.md)
- [审计日志](./AUDIT_LOG_SETUP.md)
- [医疗器械备案](./MEDICAL_DEVICE_REGISTRATION.md)

---

**文档版本**: v1.0
**最后更新**: 2026-02-21
**维护者**: AI舌诊智能诊断系统团队
**审核者**: 医疗合规团队
