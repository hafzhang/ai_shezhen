# Prometheus + Grafana监控配置指南

AI舌诊智能诊断系统的Prometheus + Grafana监控配置文档。

## 目录

- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [Prometheus配置](#prometheus配置)
- [Grafana配置](#grafana配置)
- [告警规则](#告警规则)
- [监控指标](#监控指标)
- [服务管理](#服务管理)
- [故障排除](#故障排除)

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     监控系统架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │   API服务     │─────▶│  Prometheus  │                   │
│  │  (FastAPI)   │/metrics│  (采集器)    │                   │
│  │  :8000       │      │  :9090       │                   │
│  └──────────────┘      └──────┬───────┘                   │
│         │                      │                              │
│         │                      │                              │
│         │                      ▼                              │
│         │              ┌──────────────┐                       │
│         │              │   Grafana    │                       │
│         │              │  (可视化)     │                       │
│         │              │  :3000       │                       │
│         │              └──────────────┘                       │
│         │                                                      │
│  ┌──────────────┐                                              │
│  │  Redis       │                                              │
│  │  :6379      │                                              │
│  └──────────────┘                                              │
│         │                                                      │
│  ┌──────────────┐                                              │
│  │ Celery      │                                              │
│  │ Worker      │                                              │
│  └──────────────┘                                              │
│                                                              │
└───────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 配置环境变量

确保`.env`文件已配置：

```bash
cp api_service/.env.example api_service/.env
```

编辑`api_service/.env`，确认以下配置：

```bash
# 启用Prometheus指标
ENABLE_PROMETHEUS=true

# API服务配置
API_HOST=0.0.0.0
API_PORT=8000
```

### 2. 启动监控服务

```bash
# 启动所有服务（包含监控）
docker compose --profile monitoring up -d

# 仅启动监控服务（如果API已在运行）
docker compose --profile monitoring up -d prometheus grafana redis-exporter node-exporter cadvisor
```

### 3. 访问监控界面

- **Grafana**: http://localhost:3000
  - 默认用户名: `admin`
  - 默认密码: `admin`

- **Prometheus**: http://localhost:9090
  - 查看 Targets: http://localhost:9090/targets
  - 查询指标: http://localhost:9090/graph

## Prometheus配置

### 配置文件位置

- 主配置: `prometheus/prometheus.yml`
- 告警规则: `prometheus/alert_rules.yml`

### 关键配置项

```yaml
global:
  scrape_interval: 15s      # 采集间隔
  evaluation_interval: 15s   # 规则评估间隔

scrape_configs:
  - job_name: 'shezhen-api'
    scrape_interval: 10s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['api:8000']
```

### 数据保留

- 时间序列数据保留: 15天
- 默认存储位置: Docker volume `prometheus_data`

## Grafana配置

### 仪表板配置

仪表板位置: `grafana/dashboards/shezhen-api-dashboard.json`

### 数据源配置

自动配置数据源（通过provisioning）:
- 位置: `grafana/provisioning/datasources/prometheus.yml`
- URL: `http://prometheus:9090`

### 主要面板

1. **API请求量 (QPS)**: 总请求/2xx/4xx/5xx请求速率
2. **API可用性**: 可用性百分比（目标>99%）
3. **API响应时间**: P50/P95/P99延迟（目标P95<2s）
4. **Celery任务队列长度**: 各队列积压情况
5. **模型推理延迟**: 分割/分类/LLM诊断延迟
6. **缓存命中率**: 缓存效果监控
7. **Redis内存使用率**: 内存使用情况
8. **熔断器状态**: 熔断器当前状态
9. **文心API今日成本**: API调用成本统计
10. **模型加载状态**: 各模型加载情况

## 告警规则

### 告警级别

- **P0 (Critical)**: 立即处理，服务完全不可用
- **P1 (High)**: 重要告警，用户受到影响
- **P2 (Medium)**: 次要告警，需要关注
- **P3 (Low)**: 信息提示，趋势分析

### 主要告警规则

#### API服务告警

| 规则 | 级别 | 触发条件 | 说明 |
|------|------|----------|------|
| APIServiceDown | P0 | 服务停机>1分钟 | API服务不可用 |
| APIHighResponseTime | P1 | P95响应时间>2s，持续5分钟 | API响应过慢 |
| APIHighErrorRate | P1 | 5xx错误率>5%，持续3分钟 | API错误率过高 |
| APIAvailabilityBelowSLA | P1 | 可用性<99%，持续5分钟 | 低于SLA要求 |

#### Celery告警

| 规则 | 级别 | 触发条件 | 说明 |
|------|------|----------|------|
| CeleryWorkerDown | P0 | Worker停机>2分钟 | 异步任务处理不可用 |
| CeleryQueueBacklog | P1 | 队列长度>100 | 任务积压严重 |
| CeleryHighFailureRate | P2 | 失败率>10% | 任务失败率过高 |

#### 系统资源告警

| 规则 | 级别 | 触发条件 | 说明 |
|------|------|----------|------|
| DiskSpaceLow | P0 | 磁盘剩余<10% | 磁盘空间不足 |
| HighCPUUsage | P1 | CPU使用率>85% | CPU负载过高 |
| HighMemoryUsage | P1 | 内存使用率>90% | 内存使用率过高 |
| RedisDown | P0 | Redis停机>1分钟 | 缓存服务不可用 |
| RedisHighMemoryUsage | P1 | 内存使用率>90% | Redis内存不足 |

## 监控指标

### HTTP请求指标

- `http_requests_total`: HTTP请求总数（按method、endpoint、status）
- `http_request_duration_seconds`: HTTP请求延迟直方图
- `http_requests_in_progress`: 当前进行中的请求数
- `http_response_size_bytes`: 响应大小直方图

### 模型推理指标

- `segmentation_requests_total`: 分割请求总数
- `segmentation_inference_duration_seconds`: 分割延迟
- `classification_requests_total`: 分类请求总数
- `classification_inference_duration_seconds`: 分类延迟
- `diagnosis_requests_total`: 诊断请求总数
- `diagnosis_duration_seconds`: 诊断延迟

### LLM API指标

- `wenxin_api_requests_total`: 文心API调用总数
- `wenxin_api_duration_seconds`: API调用延迟
- `wenxin_api_cost_total`: API成本累计
- `wenxin_api_tokens_total`: Token使用量

### 缓存指标

- `cache_hits_total`: 缓存命中总数
- `cache_misses_total`: 缓存未命中总数
- `cache_size_items`: 当前缓存大小

### Celery指标

- `celery_task_received_total`: 任务接收总数
- `celery_task_started_total`: 任务开始总数
- `celery_task_succeeded_total`: 任务成功总数
- `celery_task_failed_total`: 任务失败总数
- `celery_task_duration_seconds`: 任务执行延迟
- `celery_queue_length`: 队列长度
- `celery_active_tasks_count`: 活跃任务数

### 系统指标

- `model_loaded`: 模型加载状态
- `redis_connection_status`: Redis连接状态
- `circuit_breaker_state`: 熔断器状态
- `circuit_breaker_failure_count`: 熔断器失败计数

## 服务管理

### 查看服务状态

```bash
# 查看所有服务状态
docker compose ps

# 查看特定服务日志
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f api
```

### 重启服务

```bash
# 重启Prometheus
docker compose restart prometheus

# 重启Grafana
docker compose restart grafana

# 重新加载Prometheus配置（无需重启）
curl -X POST http://localhost:9090/-/reload
```

### 停止监控服务

```bash
# 停止所有服务
docker compose --profile monitoring down

# 停止监控服务但保留数据
docker compose --profile monitoring down --volumes  # 删除数据卷
```

## 故障排除

### Prometheus无法采集指标

1. 检查API服务是否启动:
```bash
curl http://localhost:8000/metrics
```

2. 检查Prometheus targets状态:
访问 http://localhost:9090/targets

3. 检查docker网络:
```bash
docker network ls
docker network inspect shezhen-network
```

### Grafana无法连接Prometheus

1. 检查Prometheus是否可访问:
```bash
curl http://localhost:9090/api/v1/status/config
```

2. 在Grafana中检查数据源配置:
Configuration > Data Sources > Prometheus

3. 检查Grafana日志:
```bash
docker compose logs grafana
```

### 指标数据缺失

1. 检查Prometheus是否正常抓取:
```bash
# 查询最近数据
curl 'http://localhost:9090/api/v1/query?query=up&time='
```

2. 检查告警规则是否加载:
访问 http://localhost:9090/alerts

3. 检查Prometheus存储:
```bash
docker exec -it shezhen-prometheus du -sh /prometheus
```

### 告警未触发

1. 检查告警规则状态:
访问 http://localhost:9090/rules

2. 检查规则评估间隔是否合适

3. 手动验证PromQL表达式:
在 http://localhost:9090/graph 中输入表达式

### 高磁盘使用

清理旧数据或调整保留时间:

```yaml
# prometheus/prometheus.yml
command:
  - '--storage.tsdb.retention.time=7d'  # 改为7天
```

然后重启Prometheus。

## 生产环境建议

### 安全配置

1. 修改Grafana默认密码
2. 配置HTTPS访问
3. 限制Prometheus仅内网访问
4. 使用API密钥保护敏感端点

### 高可用配置

1. 部署多个Prometheus实例
2. 配置AlertManager集群
3. 使用持久化存储
4. 配置数据备份

### 性能优化

1. 调整采集间隔（15s -> 30s）
2. 配置数据保留策略
3. 使用recording rules预计算
4. 优化高基数指标

## 监控最佳实践

1. **设置合理的告警阈值**: 避免告警疲劳
2. **定期审查告警规则**: 删除无效规则，调整阈值
3. **添加业务指标**: 跟踪诊断成功率、用户满意度等
4. **配置告警通知**: 集成钉钉、企业微信等
5. **定期检查仪表板**: 确保可视化满足需求
6. **文档化告警处理**: 建立runbook记录处理流程

## 相关文档

- [Docker部署指南](DOCKER_DEPLOYMENT.md)
- [性能优化指南](PERFORMANCE_OPTIMIZATION.md)
- [日志收集指南](LOGGING_SETUP.md) - 待完善
