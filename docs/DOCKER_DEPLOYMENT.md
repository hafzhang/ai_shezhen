# AI舌诊智能诊断系统 - Docker部署指南

## 概述

本文档描述了如何使用Docker和Docker Compose部署AI舌诊智能诊断系统。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Docker Compose Environment                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Redis   │──▶│  Celery Worker │  │  Celery Beat  │  │
│  │ (Broker) │  │  (Async Tasks) │  │  (Scheduler)   │  │
│  └─────────┘  └──────────────┘  └──────────────┘  │
│        │                                           │           │
│        ▼                                           ▼           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              API Service (FastAPI)                  │  │
│  │  - Segmentation Model (PaddlePaddle)            │  │
│  │  - Classification Model (PaddlePaddle)           │  │
│  │  - LLM Diagnosis (Wenxin API)                  │  │
│  │  - Rule-based Fallback                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│        │                              │                 │           │
│        ▼                              ▼                 ▼           │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Users    │  │    Flower     │  │   MLflow     │  │
│  │  :8000     │  │    :5555     │  │   :5000     │  │
│  └────────────┘  └──────────────┘  └──────────────┘  │
│                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

## 服务说明

| 服务名 | 容器名 | 端口 | 描述 | 可选 |
|--------|---------|--------|-------|-----|
| redis | shezhen-redis | 6379 | 消息代理和结果存储 | 否 |
| api | shezhen-api | 8000 | FastAPI主服务 | 否 |
| celery-worker | shezhen-celery-worker | - | 异步任务处理器 | 否 |
| celery-beat | shezhen-celery-beat | - | 定时任务调度器 | 否 |
| flower | shezhen-flower | 5555 | Celery监控面板 | 是 |
| mlflow | shezhen-mlflow | 5000 | ML实验追踪 | 是 |

## 前置要求

### 软件要求

- Docker Engine: 20.10+
- Docker Compose: 2.0+

### 硬件要求

**最低配置:**
- CPU: 4核心
- 内存: 8GB
- 磁盘: 20GB

**推荐配置:**
- CPU: 8核心
- 内存: 16GB
- 磁盘: 50GB SSD

### 网络要求

- 外部API访问: 文心一言API (需要互联网连接)
- 内部服务通信: Docker网络

## 快速开始

### 1. 克隆仓库

```bash
git clone <repository_url>
cd AI_shezhen
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp api_service/.env.example api_service/.env

# 编辑配置文件
nano api_service/.env
```

**必须配置的变量:**

```bash
# 百度文心一言API密钥 (必须)
BAIDU_API_KEY=your_api_key_here
BAIDU_SECRET_KEY=your_secret_key_here

# 推理设备
INFERENCE_DEVICE=cpu  # 或 gpu (如果有GPU支持)
```

### 3. 构建镜像

```bash
# 构建所有服务镜像
docker compose build

# 仅构建API服务
docker compose build api
```

### 4. 启动服务

```bash
# 启动所有核心服务
docker compose up -d

# 启动包含监控的所有服务
docker compose --profile monitoring up -d

# 查看日志
docker compose logs -f api
```

### 5. 验证部署

```bash
# 检查服务状态
docker compose ps

# 检查健康状态
curl http://localhost:8000/health

# 查看API文档
# 浏览器访问: http://localhost:8000/docs
```

## 服务管理

### 启动服务

```bash
# 启动所有服务
docker compose up -d

# 启动特定服务
docker compose up -d redis api

# 带监控启动
docker compose --profile monitoring up -d
```

### 停止服务

```bash
# 停止所有服务
docker compose down

# 停止并删除卷
docker compose down -v
```

### 查看日志

```bash
# 查看所有日志
docker compose logs

# 跟踪特定服务日志
docker compose logs -f api

# 查看最近100行日志
docker compose logs --tail=100 api
```

### 重启服务

```bash
# 重启特定服务
docker compose restart api

# 重启所有服务
docker compose restart
```

## 网络配置

### 外部访问

服务默认绑定到 `0.0.0.0`，可从外部访问：

| 服务 | 访问地址 |
|-----|---------|
| API | http://localhost:8000 |
| API文档 | http://localhost:8000/docs |
| Flower监控 | http://localhost:5555 |
| MLflow | http://localhost:5000 |

### 端口修改

如需修改端口，编辑 `docker-compose.yml`:

```yaml
services:
  api:
    ports:
      - "8080:8000"  # 将外部端口改为8080

  flower:
    ports:
      - "5556:5555"   # 将外部端口改为5556
```

## 数据持久化

### 卷挂载

| 卷 | 用途 |
|-----|------|
| redis_data | Redis持久化数据 |
| ./models | 模型文件 (只读) |
| ./api_service | 应用代码 (只读) |
| ./logs | 日志文件 |
| ./mlflow_data | MLflow实验数据 |

### 备份策略

```bash
# 备份模型文件
tar -czf models_backup_$(date +%Y%m%d).tar.gz models/

# 备份日志
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/

# 备份MLflow数据
docker compose exec mlflow tar -czf /tmp/mlflow_backup.tar.gz /mlflow
docker compose cp mlflow:/tmp/mlflow_backup.tar.gz ./
```

## 监控和调试

### 健康检查

```bash
# API健康检查
curl http://localhost:8000/health

# 预期响应
{
  "status": "healthy",
  "models_loaded": true,
  "redis_connected": true
}
```

### Flower监控 (Celery)

访问 http://localhost:5555 查看：
- 任务队列状态
- Worker状态
- 任务执行统计
- 失败任务重试

### MLflow追踪

访问 http://localhost:5000 查看：
- 训练实验历史
- 模型性能指标
- 参数对比

## 故障排除

### 常见问题

**1. API服务无法启动**

```bash
# 检查日志
docker compose logs api

# 常见原因:
# - 模型文件不存在 (检查./models路径)
# - API密钥未配置 (检查.env文件)
# - 端口被占用 (修改docker-compose.yml端口)
```

**2. Redis连接失败**

```bash
# 检查Redis状态
docker compose exec redis redis-cli ping

# 应返回: PONG
```

**3. Celery Worker无响应**

```bash
# 检查Worker日志
docker compose logs celery-worker

# 检查Redis连接
docker compose exec celery-worker celery -A api_service.worker.celery_app inspect active
```

**4. 内存不足**

```bash
# 检查容器资源使用
docker stats

# 解决方案:
# 1. 减少Worker并发数 (CELERY_WORKER_CONCURRENCY)
# 2. 减少推理批次大小 (INFERENCE_BATCH_SIZE)
# 3. 使用模型量化 (USE_FP16=true)
```

### 日志级别

修改 `.env` 文件中的日志级别:

```bash
# 开发环境
LOG_LEVEL=DEBUG

# 生产环境
LOG_LEVEL=INFO

# 故障排查
LOG_LEVEL=DEBUG
```

## 生产部署建议

### 安全配置

```bash
# 1. 使用.env文件 (不要将密钥提交到代码仓库)
echo ".env" >> .gitignore

# 2. 使用非root用户运行容器 (Dockerfile已配置)

# 3. 限制容器资源 (在docker-compose.yml中添加)
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

# 4. 启用HTTPS (使用反向代理)
```

### 性能优化

```bash
# 1. 使用多Worker实例
docker compose up -d --scale celery-worker=4

# 2. 启用模型量化 (FP16)
USE_FP16=true

# 3. 调整批处理大小
INFERENCE_BATCH_SIZE=4

# 4. 配置Redis内存限制
# 在docker-compose.yml中已配置: --maxmemory 512mb
```

### 高可用配置

```bash
# 使用外部Redis (不使用容器化Redis)
CELERY_BROKER_URL=redis://external-redis:6379/1

# 使用外部MLflow数据库
MLFLOW_BACKEND_STORE_URI=postgresql://user:pass@external-db:5432/mlflow
```

## 更新和回滚

### 更新服务

```bash
# 1. 拉取最新代码
git pull origin feature/shezhen-ai-system

# 2. 重新构建镜像
docker compose build

# 3. 滚动更新 (无停机)
docker compose up -d --build

# 4. 验证新版本
curl http://localhost:8000/health
```

### 回滚

```bash
# 1. 回退代码
git checkout <previous_commit>

# 2. 重新构建旧版本
docker compose build

# 3. 启动旧版本
docker compose up -d
```

## 验收检查清单

部署完成后，验证以下项目：

- [ ] 所有容器状态为 `running`
- [ ] API健康检查返回200
- [ ] API文档可访问 (`/docs`)
- [ ] Celery Worker连接到Redis
- [ ] Flower监控显示活跃Workers
- [ ] 日志文件写入到 `./logs`
- [ ] 模型文件成功挂载
- [ ] 环境变量正确配置
- [ ] 服务间网络通信正常

## 附录

### Docker Compose命令参考

```bash
# 构建和启动
docker compose up -d --build

# 仅构建
docker compose build

# 停止
docker compose down

# 强制重建
docker compose up -d --force-recreate

# 查看资源使用
docker compose top

# 执行命令
docker compose exec api <command>

# 复制文件
docker compose cp api_service/.env api:/app/api_service/.env
```

### 文件结构

```
AI_shezhen/
├── docker-compose.yml          # Docker Compose配置
├── api_service/
│   ├── Dockerfile             # API服务镜像
│   ├── .env.example           # 环境变量模板
│   ├── app/
│   │   └── main.py          # FastAPI应用入口
│   ├── worker/
│   │   └── celery_app.py     # Celery应用配置
│   └── requirements.txt       # Python依赖
├── models/
│   ├── deploy/               # 导出的推理模型
│   └── paddle_seg/          # 分割模型源码
└── docs/
    └── DOCKER_DEPLOYMENT.md  # 本文档
```

---

**文档版本:** v1.0
**最后更新:** 2026-02-12
**维护者:** Ralph Agent
