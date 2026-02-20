# 压力测试与性能优化报告

**系统**: AI舌诊智能诊断系统
**版本**: v2.3
**测试日期**: 2026-02-21
**报告编号**: LT-2026-02-21-001

---

## 1. 测试概述

### 1.1 测试目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| QPS | ≥100 | 每秒查询数 |
| P95响应时间 | <2s | 95%请求响应时间 |
| API可用性 | >99% | 服务可用百分比 |
| 缓存命中率 | >50% | Redis缓存命中率 |

### 1.2 测试工具

- **主工具**: Locust (Python负载测试框架)
- **监控**: Prometheus + Grafana
- **测试脚本**: `tests/load/locust_load_test.py`

---

## 2. 测试环境

### 2.1 系统配置

| 组件 | 配置 |
|------|------|
| API服务 | FastAPI + Uvicorn |
| 缓存 | Redis 6.x, 512MB内存, LRU策略 |
| 模型 | BiSeNetV2 (分割), PP-HGNetV2-B4 (分类) |
| 推理引擎 | PaddlePaddle 2.6 CPU推理 |

### 2.2 缓存策略配置

```python
# Redis缓存TTL配置
CACHE_TTL_SECONDS = 86400  # 24小时

# 缓存键前缀
CACHE_PREFIX = "shezhen:diagnosis:"

# 缓存策略
REDIS_MAX_MEMORY = "512mb"
REDIS_MAX_MEMORY_POLICY = "allkeys-lru"
```

---

## 3. 压力测试脚本说明

### 3.1 测试场景

| 场景 | 权重 | 说明 |
|------|------|------|
| 健康检查 | 5% | GET /api/v1/health |
| 获取知情同意书 | 10% | GET /api/v1/consent/form |
| 舌体分割 | 20% | POST /api/v1/segment |
| 舌象分类 | 20% | POST /api/v1/classify |
| 完整诊断 | 45% | POST /api/v1/diagnosis |

### 3.2 用户行为模拟

- **并发用户数**: 100
- **生成速率**: 10 用户/秒
- **等待时间**: 1-3秒 (随机)
- **测试时长**: 5分钟

### 3.3 运行方式

```bash
# 标准测试（带Web UI）
locust -f tests/load/locust_load_test.py --host http://localhost:8000

# 无头模式（命令行）
locust -f tests/load/locust_load_test.py --headless \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m

# 生成HTML报告
locust -f tests/load/locust_load_test.py --headless \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --html load_test_report.html
```

---

## 4. 性能优化方案

### 4.1 已实施的优化措施

#### 4.1.1 缓存优化

| 优化项 | 实施方案 | 效果 |
|--------|----------|------|
| Redis缓存 | 24小时TTL, LRU淘汰 | 减少重复推理 |
| 缓存预热 | 启动时加载热门案例 | 降低首次延迟 |
| 缓存监控 | Prometheus metrics采集 | 实时命中率监控 |

#### 4.1.2 API优化

| 优化项 | 实施方案 | 效果 |
|--------|----------|------|
| 异步处理 | Celery任务队列 | 非阻塞请求处理 |
| 连接池 | HTTP连接复用 | 减少连接开销 |
| 响应压缩 | Gzip压缩 | 减少传输数据 |

#### 4.1.3 模型优化

| 优化项 | 实施方案 | 效果 |
|--------|----------|------|
| 模型量化 | FP16/INT8量化 | 减少推理时间 |
| 模型缓存 | 内存中加载 | 避免重复加载 |
| 批处理 | 支持batch推理 | 提高吞吐量 |

### 4.2 性能监控指标

#### Prometheus指标

```promql
# QPS
rate(http_requests_total{job="shezhen-api"}[1m])

# P95响应时间
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="shezhen-api"}[5m]))

# 缓存命中率
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# API可用性
rate(http_requests_total{job="shezhen-api",status!~"5.."}[5m]) / rate(http_requests_total{job="shezhen-api"}[5m])
```

### 4.3 告警规则

| 级别 | 触发条件 | 说明 |
|------|----------|------|
| P1 | P95响应时间 > 2s | 性能降级 |
| P1 | 错误率 > 5% | 服务异常 |
| P1 | 可用性 < 99% | SLA违反 |
| P3 | 缓存命中率 < 50% | 性能优化机会 |

---

## 5. 测试验证清单

### 5.1 自动化验证

- [ ] 100 QPS目标达成
- [ ] P95响应时间 < 2s
- [ ] API可用性 > 99%
- [ ] 缓存命中率 > 50%

### 5.2 手动验证

- [ ] Grafana监控面板检查
- [ ] Prometheus指标验证
- [ ] 日志无异常报错
- [ ] 资源使用正常（CPU/内存）

---

## 6. 结果分析

### 6.1 预期结果

运行 `tests/load/locust_load_test.py` 后，预期获得：

| 指标 | 预期值 | 实际值 | 状态 |
|------|--------|--------|------|
| QPS | ≥100 | 待测试 | - |
| P95延迟 | <2000ms | 待测试 | - |
| 可用性 | >99% | 待测试 | - |
| 缓存命中率 | >50% | 待测试 | - |

### 6.2 报告生成

测试完成后，系统将自动生成：

1. **JSON报告**: `tests/load/load_test_report.json`
2. **HTML报告**: `load_test_report.html` (使用 `--html` 参数)
3. **控制台摘要**: 实时打印测试结果

---

## 7. 建议与后续优化

### 7.1 短期优化

1. **增加节点**: 水平扩展API服务实例
2. **CDN加速**: 静态资源使用CDN
3. **数据库优化**: 如使用数据库，添加索引和连接池

### 7.2 长期优化

1. **GPU推理**: 使用GPU加速模型推理
2. **模型蒸馏**: 进一步压缩模型大小
3. **边缘部署**: 将推理部署到边缘节点

---

## 8. 附录

### 8.1 相关文档

- 缓存配置文档: `docs/cache_configuration.md`
- Prometheus配置: `prometheus/prometheus.yml`
- Grafana仪表板: `grafana/dashboards/shezhen-api-dashboard.json`

### 8.2 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| QPS无法达到100 | CPU瓶颈 | 增加实例/使用GPU |
| P95延迟过高 | 模型推理慢 | 启用缓存/模型量化 |
| 可用性低于99% | 错误率上升 | 检查日志/修复bug |
| 缓存命中率低 | TTL过短 | 增加TTL时间 |
