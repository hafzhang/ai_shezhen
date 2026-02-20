# Redis缓存配置文档

**系统**: AI舌诊智能诊断系统
**版本**: v2.3
**配置日期**: 2026-02-21

---

## 1. 缓存架构概述

### 1.1 缓存层次

```
┌─────────────────────────────────────────────────────┐
│                  API层 (FastAPI)                     │
├─────────────────────────────────────────────────────┤
│               Redis缓存层 (6.x)                      │
│  - 诊断结果缓存 (24h TTL)                            │
│  - 特征向量缓存 (12h TTL)                            │
│  - 限流计数器 (滑动窗口)                             │
├─────────────────────────────────────────────────────┤
│           数据持久化层 (JSON文件/数据库)               │
└─────────────────────────────────────────────────────┘
```

### 1.2 缓存策略

| 策略 | 说明 | 应用场景 |
|------|------|----------|
| Cache-Aside | 代码控制缓存读写 | 诊断结果 |
| Write-Through | 写入时同步更新缓存 | 用户配置 |
| LRU淘汰 | 内存不足时淘汰最少使用项 | 所有缓存 |

---

## 2. Redis配置

### 2.1 基础配置

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    command: >
      redis-server
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
      --save 60 10000
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
```

### 2.2 内存策略

| 配置项 | 值 | 说明 |
|--------|-----|------|
| maxmemory | 512mb | 最大内存使用 |
| maxmemory-policy | allkeys-lru | LRU淘汰策略 |
| save | 900 1 / 300 10 / 60 10000 | RDB持久化规则 |

---

## 3. 缓存键设计

### 3.1 键命名规范

```
shezhen:<service>:<entity>:<identifier>:<attribute>
```

### 3.2 缓存键列表

| 缓存类型 | 键模式 | TTL | 说明 |
|----------|--------|-----|------|
| 诊断结果 | `shezhen:diagnosis:{image_hash}` | 24h | 完整诊断结果 |
| 分割结果 | `shezhen:segment:{image_hash}` | 24h | 舌体分割mask |
| 分类结果 | `shezhen:classify:{image_hash}` | 24h | 舌象分类结果 |
| 特征向量 | `shezhen:features:{image_hash}` | 12h | 提取的特征 |
| 限流计数 | `shezhen:ratelimit:{user_id}:{endpoint}` | 动态 | 请求计数 |
| 案例检索 | `shezhen:cases:{syndrome}` | 6h | 预加载案例 |

---

## 4. 缓存操作

### 4.1 读取缓存

```python
# 伪代码示例
def get_diagnosis_result(image_hash: str) -> Optional[Dict]:
    cache_key = f"shezhen:diagnosis:{image_hash}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None
```

### 4.2 写入缓存

```python
def set_diagnosis_result(image_hash: str, result: Dict, ttl: int = 86400):
    cache_key = f"shezhen:diagnosis:{image_hash}"
    redis_client.setex(
        cache_key,
        ttl,
        json.dumps(result, ensure_ascii=False)
    )
```

### 4.3 失效策略

```python
def invalidate_diagnosis_cache(image_hash: str):
    patterns = [
        f"shezhen:diagnosis:{image_hash}",
        f"shezhen:segment:{image_hash}",
        f"shezhen:classify:{image_hash}",
        f"shezhen:features:{image_hash}",
    ]
    for key in patterns:
        redis_client.delete(key)
```

---

## 5. 缓存预热

### 5.1 预加载策略

| 预加载内容 | 触发时机 | 预期效果 |
|------------|----------|----------|
| 热门案例 | 服务启动时 | 降低首次访问延迟 |
| 配置数据 | 定时刷新 | 配置更新及时生效 |

### 5.2 预热脚本

```python
async def warmup_cache():
    """预热缓存 - 加载热门案例"""
    syndromes = ["健康舌", "阴虚火旺证", "痰湿内阻证"]
    for syndrome in syndromes:
        cases = retrieve_cases_by_syndrome(syndrome, top_k=10)
        cache_key = f"shezhen:cases:{syndrome}"
        redis_client.setex(cache_key, 21600, json.dumps(cases))  # 6h
```

---

## 6. 缓存监控

### 6.1 Prometheus指标

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| cache_hits_total | Counter | 缓存命中次数 |
| cache_misses_total | Counter | 缓存未命中次数 |
| cache_size_items | Gauge | 当前缓存项数 |
| cache_memory_bytes | Gauge | 缓存内存使用 |

### 6.2 Grafana查询

```promql
# 缓存命中率
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# 缓存大小
cache_size_items{cache_type="diagnosis"}

# 缓存内存使用
cache_memory_bytes / 1024 / 1024  # MB
```

### 6.3 告警规则

```yaml
# prometheus/alert_rules.yml
- alert: LowCacheHitRate
  expr: |
    rate(cache_hits_total[15m]) /
    (rate(cache_hits_total[15m]) + rate(cache_misses_total[15m])) < 0.5
  for: 15m
  labels:
    severity: P3
  annotations:
    summary: "缓存命中率低于50%"
```

---

## 7. 性能优化

### 7.1 批量操作

```python
# 使用Pipeline减少RTT
pipe = redis_client.pipeline()
for image_hash in image_hashes:
    pipe.get(f"shezhen:diagnosis:{image_hash}")
results = pipe.execute()
```

### 7.2 压缩存储

```python
import gzip
import pickle

def set_compressed(key: str, value: Any, ttl: int):
    serialized = pickle.dumps(value)
    compressed = gzip.compress(serialized)
    redis_client.setex(key, ttl, compressed)
```

### 7.3 连接池配置

```python
redis_pool = redis.ConnectionPool(
    host='redis',
    port=6379,
    db=0,
    max_connections=50,
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)
```

---

## 8. 故障处理

### 8.1 Redis故障降级

```python
def get_with_fallback(key: str, fallback_func):
    try:
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)
    except RedisError:
        logger.warning("Redis unavailable, using fallback")
    return fallback_func()
```

### 8.2 缓存雪崩防护

```python
import random

def set_with_jitter(key: str, value: Any, base_ttl: int):
    """添加随机TTL避免同时过期"""
    jitter = random.randint(-300, 300)  # ±5分钟
    ttl = base_ttl + jitter
    redis_client.setex(key, ttl, value)
```

---

## 9. 维护操作

### 9.1 清理过期缓存

```bash
# 自动清理，Redis会自动删除过期键
# 手动清理特定模式
redis-cli --scan --pattern "shezhen:diagnosis:*" | xargs redis-cli DEL
```

### 9.2 缓存统计

```bash
# 获取缓存信息
redis-cli INFO stats

# 获取内存使用
redis-cli INFO memory

# 获取键空间统计
redis-cli --bigkeys
```

---

## 10. 附录

### 10.1 相关文件

- Redis配置: `docker-compose.yml` (redis service)
- 限流配置: `api_service/middleware/rate_limiter.py`
- 监控配置: `prometheus/prometheus.yml`

### 10.2 性能基准

| 操作 | 目标延迟 | 说明 |
|------|----------|------|
| GET | <1ms | 简单键查询 |
| SET | <1ms | 简单键写入 |
| MGET | <5ms | 批量查询(10键) |
| Pipeline | <10ms | 批量操作(100键) |
