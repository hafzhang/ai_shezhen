# AI舌诊智能诊断系统 - 审计日志与ELK Stack配置指南

## 概述

本文档描述AI舌诊系统的审计日志和日志收集系统配置，包括：
- ELK Stack (Elasticsearch, Logstash, Kibana) 集成
- 180天日志留存策略
- WORM (Write Once Read Many) 防篡改存储
- 完整的审计追踪系统

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     日志数据流                              │
└─────────────────────────────────────────────────────────────────┘

API/Celery Worker          Filebeat              Logstash           Elasticsearch
     │                        │                     │                   │
     │  ┌──────────────────┐ │                     │                   │
     └─►│  application.log  ├─┤                     │                   │
        │  audit.log        │ │                     │                   │
        │  error.log        │ │                     │                   │
        └──────────────────┘ │                     │                   │
                             │                     │                   │
                             ▼                     ▼                   ▼
                    ┌─────────────┐    ┌─────────────┐   ┌─────────────┐
                    │  Logstash   │───►│ Elasticsearch│   │   Kibana    │
                    │  Pipeline   │    │   Storage   │◄──│Visualization│
                    └─────────────┘    │  (180 days) │   └─────────────┘
                                        └─────────────┘
```

## 快速开始

### 1. 启动ELK Stack服务

```bash
# 使用docker compose启动ELK服务
docker compose --profile logging up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f elasticsearch
docker compose logs -f logstash
docker compose logs -f kibana
```

### 2. 验证服务

```bash
# Elasticsearch健康检查
curl -u elastic:changeme http://localhost:9200/_cluster/health

# Kibana访问
open http://localhost:5601
```

### 3. 配置索引模板

索引模板会在首次启动时自动配置。如需手动配置：

```bash
# 运行索引设置脚本
docker compose run --rm elk-setup
```

## 审计日志系统

### 审计事件类型

系统记录以下类型的审计事件：

| 事件类型 | 描述 | 示例 |
|---------|------|------|
| `diagnosis_workflow` | 完整诊断流程 | 图像分割→分类→诊断的完整链路 |
| `data_access` | 数据访问 | 读取/写入/删除图像或诊断记录 |
| `configuration_change` | 配置变更 | 修改模型路径、API密钥等 |
| `api_request` | API请求 | 每次API调用的详细信息 |
| `api_response` | API响应 | 响应时间、状态码等 |

### 审计日志格式

审计日志以JSON格式存储，包含以下字段：

```json
{
  "event_id": "evt_20250212153045_abc123",
  "timestamp": "2026-02-12T15:30:45.123456",
  "event_type": "diagnosis_workflow",
  "user_id": null,
  "session_id": "sess_20250212_def456",
  "request_id": "req_abc123",
  "source_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "action": "execute",
  "resource_type": "diagnosis",
  "resource_id": "img_12345",
  "status": "success",
  "details": {
    "image_id": "img_12345",
    "diagnosis_type": "diagnosis",
    "workflow_steps": [
      {
        "step": "segmentation",
        "duration_ms": 45.2,
        "status": "success"
      },
      {
        "step": "classification",
        "duration_ms": 120.5,
        "status": "success"
      },
      {
        "step": "llm_diagnosis",
        "duration_ms": 1850.0,
        "status": "success"
      }
    ],
    "step_count": 3,
    "total_duration_ms": 2015.7
  }
}
```

### 使用审计追踪API

```python
from api_service.core.audit_trail import (
    log_diagnosis_workflow,
    log_data_access,
    log_configuration_change,
    get_audit_manager
)

# 记录诊断工作流
event_id = log_diagnosis_workflow(
    request_id="req_123",
    source_ip="192.168.1.100",
    image_id="img_456",
    diagnosis_type="diagnosis",
    workflow_steps=[
        {"step": "segmentation", "duration_ms": 45.2, "status": "success"},
        {"step": "classification", "duration_ms": 120.5, "status": "success"}
    ],
    final_result={"syndrome": "脾胃虚弱"}
)

# 记录数据访问
log_data_access(
    request_id="req_124",
    source_ip="192.168.1.100",
    resource_type="image",
    resource_id="img_456",
    access_type="read"
)

# 验证审计追踪完整性
manager = get_audit_manager()
report = manager.verify_audit_trail()
print(f"Total events: {report['total_events']}")
print(f"Verified: {report['verified']}")
print(f"Tampered events: {len(report['tampered_events'])}")
```

## WORM防篡改机制

### 校验和验证

每条审计记录包含SHA256校验和：

```python
class AuditEvent:
    def __post_init__(self):
        # 计算内容的SHA256哈希
        data_to_hash = self._get_hashable_data()
        self.checksum = hashlib.sha256(
            data_to_hash.encode('utf-8')
        ).hexdigest()
```

### 完整性验证

```bash
# 运行完整性验证脚本
python -m api_service.core.audit_trail verify
```

### 防篡改特性

1. **仅追加写入**: 审计日志文件使用 `a` 模式打开，不允许修改现有内容
2. **校验和**: 每条记录独立校验和，检测任何修改
3. **分层存储**:
   - 热数据 (0-30天): 可写入，高性能存储
   - 温数据 (30-90天): 只读，压缩存储
   - 冷数据 (90-180天): 只读，归档存储
   - 删除: 180天后自动删除

## 日志留存策略

### ILM (Index Lifecycle Management) 策略

#### 审计日志 (shezhen-audit-*)

| 阶段 | 时间 | 操作 |
|------|------|------|
| Hot | 0-30天 | 可写入，单索引最大50GB |
| Warm | 30-90天 | 合并段，不可修改 |
| Cold | 90-180天 | 只读，低成本存储 |
| Delete | 180天后 | 自动删除 |

#### 应用日志 (shezhen-application-*)

| 阶段 | 时间 | 操作 |
|------|------|------|
| Hot | 0-30天 | 可写入 |
| Delete | 180天后 | 自动删除 |

### 查询历史日志

```bash
# Kibana Dev Tools
GET shezhen-audit-*/_search
{
  "query": {
    "range": {
      "@timestamp": {
        "gte": "now-180d",
        "lte": "now"
      }
    }
  },
  "size": 100
}
```

## Kibana仪表板

### 预配置的视图

1. **审计概览**: 所有审计事件的时间线
2. **诊断工作流**: 完整诊断流程的步骤分析
3. **API访问**: 请求量、响应时间、错误率
4. **数据访问**: 图像和诊断记录的访问历史
5. **合规报告**: 180天留存期验证

### 创建自定义视图

1. 访问 Kibana: http://localhost:5601
2. 导航到 Stack Management > Index Patterns
3. 选择索引模式: `shezhen-audit-*` 或 `shezhen-application-*`
4. 配置时间字段: `@timestamp`
5. 创建 Discover 视图

## 合规性要求

### 数据留存

- ✅ **180天留存**: 所有审计日志自动保留180天
- ✅ **WORM存储**: 审计日志仅追加写入，不可修改
- ✅ **校验和**: 每条记录独立SHA256校验和
- ✅ **完整性验证**: 支持批量验证审计追踪完整性

### 审计内容

每次诊断必须记录：
- ✅ 请求时间戳
- ✅ 客户端IP地址
- ✅ 诊断类型 (segment/classify/diagnosis)
- ✅ 工作流步骤 (含耗时和状态)
- ✅ 最终诊断结果
- ✅ 是否使用兜底方案

### 数据脱敏

审计日志中的敏感数据会被自动脱敏：
- `patient_id`: `[REDACTED]`
- `personal_info`: `[REDACTED]`
- `contact`: `[REDACTED]`

## 故障排除

### Elasticsearch无法启动

```bash
# 检查内存
docker compose logs elasticsearch | grep "heap"

# 增加JVM堆内存
# 在docker-compose.yml中设置:
# - ES_JAVA_OPTS=-Xms2g -Xmx2g
```

### Filebeat无法连接Logstash

```bash
# 检查Logstash端口
docker compose exec logstash netstat -tuln | grep 5044

# 检查Filebeat日志
docker compose logs filebeat
```

### Kibana无法发现索引

```bash
# 手动刷新索引
curl -u elastic:changeme -X POST \
  "http://localhost:9200/_refresh"

# 检查索引模板
curl -u elastic:changeme \
  "http://localhost:9200/_index_template/shezhen-audit-template"
```

## 配置文件位置

| 服务 | 配置文件 |
|------|---------|
| Elasticsearch | `elk/elasticsearch/config/elasticsearch.yml` |
| Logstash | `elk/logstash/config/logstash.conf` |
| Kibana | `elk/kibana/config/kibana.yml` |
| Filebeat | `elk/filebeat/config/filebeat.yml` |
| 索引设置 | `elk/setup/audit_indices.sh` |

## 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `ELASTICSEARCH_HOSTS` | `http://elasticsearch:9200` | Elasticsearch地址 |
| `ELASTICSEARCH_USER` | `elastic` | Elasticsearch用户名 |
| `ELASTICSEARCH_PASSWORD` | `changeme` | Elasticsearch密码 |
| `ELK_ENVIRONMENT` | `production` | 环境标识 |
| `KIBANA_ENCRYPTION_KEY` | - | Kibana加密密钥 (32字符) |

## 维护任务

### 每周

```bash
# 检查索引健康状态
curl -u elastic:changeme \
  "http://localhost:9200/_cat/indices/shezhen-*?v&health"

# 检查ILM策略状态
curl -u elastic:changeme \
  "http://localhost:9200/_ilm/policy/shezhen-audit-policy"
```

### 每月

```bash
# 验证审计追踪完整性
python -m api_service.core.audit_trail verify

# 备份重要索引
curl -u elastic:changeme -X POST \
  "http://localhost:9200/shezhen-audit-*/_snapshot/backup_repo/snapshot_$(date +%Y%m%d)"
```

## 参考链接

- [Elasticsearch文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Logstash文档](https://www.elastic.co/guide/en/logstash/current/index.html)
- [Kibana文档](https://www.elastic.co/guide/en/kibana/current/index.html)
- [ILM策略](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-lifecycle-management.html)
