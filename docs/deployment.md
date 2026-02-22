# AI舌诊智能诊断系统 - 部署指南

## 概述

本文档描述了如何部署AI舌诊智能诊断系统，包括后端API服务、PostgreSQL数据库、以及uni-app前端应用的完整部署流程。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI舌诊智能诊断系统架构                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │  PostgreSQL  │  │    Redis     │  │   API        │                      │
│  │  (Database)  │  │  (Cache)     │  │  Service     │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│         │                                  │                                │
│         └──────────────────────────────────┴──────────────────────────────┐ │
│                                                                            │ │
│  ┌─────────────────────────────────────────────────────────────────────┐  │ │
│  │                         Frontend Applications                        │  │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐                   │  │ │
│  │  │    H5    │  │ 微信小程序    │  │ 抖音小程序    │                   │  │ │
│  │  │ (Web)    │  │  (WeChat)    │  │  (Douyin)    │                   │  │ │
│  │  └──────────┘  └──────────────┘  └──────────────┘                   │  │ │
│  └─────────────────────────────────────────────────────────────────────┘  │ │
│                                                                            │ │
└────────────────────────────────────────────────────────────────────────────┘
```

## 前置要求

### 软件要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 2.0+ | 2.20+ |
| Node.js | 18.0+ | 20.x LTS |
| npm | 9.0+ | 10.x |
| Python | 3.10+ | 3.11 |
| PostgreSQL | 15+ | 15.x |

### 硬件要求

**最低配置:**
- CPU: 4核心
- 内存: 8GB
- 磁盘: 20GB

**推荐配置:**
- CPU: 8核心
- 内存: 16GB
- 磁盘: 50GB SSD

---

## 第一部分：后端部署

### 1. 环境准备

#### 1.1 克隆仓库

```bash
git clone <repository_url>
cd AI_shezhen
```

#### 1.2 配置环境变量

```bash
# 复制环境变量模板
cp api_service/.env.example api_service/.env

# 编辑配置文件
nano api_service/.env
```

**必须配置的变量:**

```bash
# 数据库配置 (US-119)
DATABASE_URL=postgresql://shezhen:your_password@localhost:5432/shezhen_db
ALEMBIC_DATABASE_URL=postgresql://shezhen:your_password@localhost:5432/shezhen_db

# JWT密钥 (生产环境必须更改)
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_REFRESH_SECRET_KEY=your-refresh-secret-key-change-in-production

# 百度文心一言API密钥
BAIDU_API_KEY=your_api_key_here
BAIDU_SECRET_KEY=your_secret_key_here

# 小程序配置 (可选)
WECHAT_APP_ID=your_wechat_app_id
WECHAT_APP_SECRET=your_wechat_app_secret
DOUYIN_APP_ID=your_douyin_app_id
DOUYIN_APP_SECRET=your_douyin_app_secret
```

### 2. PostgreSQL 部署

#### 2.1 使用 Docker Compose 部署 PostgreSQL

**推荐使用Docker Compose一键部署：**

```bash
# 启动PostgreSQL服务
docker compose up -d postgres

# 查看PostgreSQL日志
docker compose logs -f postgres

# 验证PostgreSQL运行状态
docker compose exec postgres pg_isready -U shezhen
```

#### 2.2 手动部署 PostgreSQL

**如果使用独立PostgreSQL实例：**

```bash
# 安装PostgreSQL (Ubuntu/Debian)
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# 启动PostgreSQL服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 创建数据库和用户
sudo -u postgres psql

-- 在psql中执行
CREATE DATABASE shezhen_db;
CREATE USER shezhen WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE shezhen_db TO shezhen;
ALTER DATABASE shezhen_db OWNER TO shezhen;
\q
```

#### 2.3 配置远程访问 (可选)

如果需要远程连接PostgreSQL：

```bash
# 编辑postgresql.conf
sudo nano /etc/postgresql/15/main/postgresql.conf

# 修改以下行
listen_addresses = '*'

# 编辑pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf

# 添加以下行
host    shezhen_db    shezhen    0.0.0.0/0    md5

# 重启PostgreSQL
sudo systemctl restart postgresql

# 配置防火墙
sudo ufw allow 5432/tcp
```

### 3. 数据库迁移

#### 3.1 使用 Alembic 进行数据库迁移

```bash
# 激活Python虚拟环境
cd api_service
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 初始化Alembic (首次运行)
alembic init alembic

# 升级数据库到最新版本
alembic upgrade head

# 验证迁移状态
alembic current

# 查看迁移历史
alembic history
```

#### 3.2 使用 Docker 执行迁移

```bash
# 构建API服务镜像
docker compose build api

# 执行数据库迁移
docker compose run --rm api alembic upgrade head

# 验证表结构
docker compose exec postgres psql -U shezhen -d shezhen_db -c "\dt"
```

#### 3.3 数据库迁移步骤详解

**完整的迁移流程：**

1. **创建迁移文件** (开发新功能时)

```bash
# 生成新的迁移文件
alembic revision --autogenerate -m "描述迁移内容"

# 手动创建迁移文件
alembic revision -m "手动创建迁移"
```

2. **审查迁移文件**

```bash
# 查看最新迁移文件
cat alembic/versions/xxxxx_description.py
```

3. **测试迁移** (开发环境)

```bash
# 回滚到上一个版本
alembic downgrade -1

# 升级到最新版本
alembic upgrade head
```

4. **生产环境迁移**

```bash
# 备份数据库
pg_dump -U shezhen shezhen_db > backup_before_migration_$(date +%Y%m%d).sql

# 执行迁移
alembic upgrade head

# 验证迁移成功
alembic current
```

5. **回滚迁移** (如需要)

```bash
# 回滚到指定版本
alembic downgrade <revision_id>

# 回滚到初始状态
alembic downgrade base
```

#### 3.4 现有迁移列表

当前系统包含以下数据库迁移：

| 迁移ID | 描述 | 版本日期 |
|--------|------|---------|
| us102 | 创建用户表 | 2026-02-21 |
| us103 | 创建刷新令牌表 | 2026-02-21 |
| us104 | 创建舌象图片表 | 2026-02-21 |
| us105 | 创建诊断历史表 | 2026-02-21 |
| us106 | 创建健康档案表 | 2026-02-21 |

### 4. API服务部署

#### 4.1 使用 Docker Compose 部署

```bash
# 构建并启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看API日志
docker compose logs -f api

# 验证API健康状态
curl http://localhost:8000/api/v2/health
```

#### 4.2 手动部署 API 服务

```bash
# 进入API服务目录
cd api_service

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 执行数据库迁移
alembic upgrade head

# 启动API服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4.3 使用 Gunicorn 生产部署

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动API服务
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

#### 4.4 使用 Systemd 管理服务

创建服务文件 `/etc/systemd/system/shezhen-api.service`：

```ini
[Unit]
Description=AI舌诊智能诊断系统 API服务
After=network.target postgresql.service

[Service]
Type=notify
User=shezhen
Group=shezhen
WorkingDirectory=/opt/shezhen/api_service
Environment="PATH=/opt/shezhen/api_service/venv/bin"
ExecStart=/opt/shezhen/api_service/venv/bin/gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
PrivateTmp=true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start shezhen-api

# 设置开机自启
sudo systemctl enable shezhen-api

# 查看服务状态
sudo systemctl status shezhen-api

# 查看日志
sudo journalctl -u shezhen-api -f
```

---

## 第二部分：前端部署

### 5. uni-app 前端构建

#### 5.1 环境准备

```bash
# 进入前端目录
cd uni-app_frontend

# 安装依赖
npm install

# 或使用 pnpm
pnpm install
```

#### 5.2 H5 网页版构建

```bash
# 开发环境运行
npm run dev:h5

# 生产环境构建
npm run build:h5

# 构建产物位置
# dist/build/h5/
```

**H5 部署到 Nginx：**

```bash
# 安装 Nginx
sudo apt install nginx

# 复制构建产物到 Nginx 目录
sudo cp -r dist/build/h5/* /var/www/html/shezhen/

# 配置 Nginx
sudo nano /etc/nginx/sites-available/shezhen-h5
```

Nginx配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/html/shezhen;
    index index.html;

    # SPA路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API代理
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

启用站点：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/shezhen-h5 /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载Nginx
sudo systemctl reload nginx
```

#### 5.3 微信小程序构建

**使用 HBuilderX 构建：**

1. 打开 HBuilderX
2. 导入项目：文件 -> 导入 -> 从本地目录导入
3. 配置 manifest.json：
   - 微信小程序 AppID
   - 应用名称
   - 应用版本
4. 发行：发行 -> 小程序-微信
5. 使用微信开发者工具打开生成的目录

**使用命令行构建：**

```bash
# 开发环境预览
npm run dev:mp-weixin

# 生产环境构建
npm run build:mp-weixin

# 构建产物位置
# dist/build/mp-weixin/
```

**上传到微信平台：**

1. 下载微信开发者工具
2. 导入项目：选择 `dist/build/mp-weixin/` 目录
3. 填写 AppID
4. 预览测试
5. 上传代码：工具 -> 上传
6. 登录微信公众平台提交审核

#### 5.4 抖音小程序构建

```bash
# 开发环境预览
npm run dev:mp-toutiao

# 生产环境构建
npm run build:mp-toutiao

# 构建产物位置
# dist/build/mp-toutiao/
```

**上传到抖音平台：**

1. 下载抖音开发者工具
2. 导入项目：选择 `dist/build/mp-toutiao/` 目录
3. 填写 AppID
4. 预览测试
5. 上传代码
6. 登录抖音开放平台提交审核

### 6. 环境变量配置

#### 6.1 H5 环境变量

创建 `.env.production` 文件：

```bash
# API地址
VITE_API_BASE_URL=https://api.your-domain.com

# 应用配置
VITE_APP_TITLE=AI舌诊智能诊断系统
VITE_APP_VERSION=3.0.0
```

#### 6.2 小程序环境变量

在小程序管理后台配置服务器域名：

- **微信小程序**: 开发 -> 开发设置 -> 服务器域名
- **抖音小程序**: 开发 -> 开发设置 -> 服务器域名

**request合法域名:**
```
https://api.your-domain.com
```

**uploadFile合法域名:**
```
https://api.your-domain.com
```

---

## 第三部分：监控与运维

### 7. 健康检查

#### 7.1 API健康检查

```bash
# 检查API服务状态
curl http://localhost:8000/api/v2/health

# 预期响应
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "models_loaded": true
  }
}
```

#### 7.2 数据库健康检查

```bash
# PostgreSQL健康检查
docker compose exec postgres pg_isready -U shezhen

# 连接数据库
docker compose exec postgres psql -U shezhen -d shezhen_db

# 查看连接数
SELECT count(*) FROM pg_stat_activity;
```

#### 7.3 Redis健康检查

```bash
# Redis健康检查
docker compose exec redis redis-cli ping

# 查看Redis信息
docker compose exec redis redis-cli INFO
```

### 8. 日志管理

#### 8.1 API日志

```bash
# 查看API日志
docker compose logs -f api

# 查看最近100行
docker compose logs --tail=100 api

# 导出日志
docker compose logs api > api_logs_$(date +%Y%m%d).log
```

#### 8.2 数据库日志

```bash
# 查看PostgreSQL日志
docker compose exec postgres tail -f /var/log/postgresql/postgresql-15-main.log
```

#### 8.3 日志聚合 (可选)

使用 ELK Stack 进行日志聚合：

```bash
# 启动日志服务
docker compose --profile logging up -d

# 访问Kibana
http://localhost:5601
```

### 9. 性能监控

启动Prometheus和Grafana监控：

```bash
# 启动监控服务
docker compose --profile monitoring up -d

# 访问Grafana
http://localhost:3000

# 默认账号
admin/admin
```

---

## 第四部分：生产部署

### 10. 安全配置

#### 10.1 修改默认密码

```bash
# 生成随机JWT密钥
openssl rand -hex 32

# 生成数据库密码
openssl rand -base64 24

# 更新.env文件
JWT_SECRET_KEY=<生成的密钥>
JWT_REFRESH_SECRET_KEY=<生成的密钥>
DATABASE_URL=postgresql://shezhen:<生成的密码>@postgres:5432/shezhen_db
```

#### 10.2 HTTPS配置

**使用 Let's Encrypt:**

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取SSL证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

#### 10.3 防火墙配置

```bash
# 配置UFW防火墙
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# 查看状态
sudo ufw status
```

### 11. 备份策略

#### 11.1 数据库备份

```bash
# 创建备份脚本
cat > /opt/backups/backup_db.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker compose exec -T postgres pg_dump -U shezhen shezhen_db | gzip > $BACKUP_DIR/shezhen_db_$DATE.sql.gz

# 保留最近30天的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/backups/backup_db.sh

# 添加到crontab (每天凌晨2点备份)
crontab -e
# 添加: 0 2 * * * /opt/backups/backup_db.sh
```

#### 11.2 恢复数据库

```bash
# 解压并恢复
gunzip < backup_file.sql.gz | docker compose exec -T postgres psql -U shezhen shezhen_db
```

### 12. 高可用配置

#### 12.1 数据库主从复制

```bash
# 配置PostgreSQL主从复制
# (需要修改postgresql.conf和pg_hba.conf)
```

#### 12.2 负载均衡

使用Nginx作为API负载均衡器：

```nginx
upstream api_backend {
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://api_backend;
    }
}
```

---

## 第五部分：故障排除

### 13. 常见问题

#### 13.1 API服务无法启动

```bash
# 检查日志
docker compose logs api

# 常见原因：
# - 数据库未启动
# - 环境变量配置错误
# - 端口被占用
```

#### 13.2 数据库连接失败

```bash
# 检查PostgreSQL状态
docker compose ps postgres

# 测试连接
docker compose exec postgres psql -U shezhen -d shezhen_db

# 检查网络
docker network ls
docker network inspect shezhen-network
```

#### 13.3 迁移失败

```bash
# 查看当前迁移版本
alembic current

# 查看迁移历史
alembic history

# 强制回滚
alembic downgrade base

# 重新迁移
alembic upgrade head
```

---

## 第六部分：验收检查清单

部署完成后，验证以下项目：

### 后端检查

- [ ] PostgreSQL数据库运行正常
- [ ] 所有数据库表已创建
- [ ] 数据库迁移已执行到最新版本
- [ ] API服务正常启动
- [ ] API健康检查返回200
- [ ] JWT令牌生成验证正常
- [ ] 诊断历史可存储、可查询
- [ ] 健康档案CRUD正常

### 前端检查

- [ ] H5应用可正常构建
- [ ] H5应用可通过浏览器访问
- [ ] 微信小程序可正常构建
- [ ] 抖音小程序可正常构建
- [ ] 用户注册/登录功能正常
- [ ] 端到端诊断流程完整

### 运维检查

- [ ] 日志正常输出
- [ ] 健康检查正常
- [ ] 监控指标正常
- [ ] 备份任务正常运行
- [ ] SSL证书有效
- [ ] 防火墙配置正确

---

## 附录

### A. 端口映射

| 服务 | 内部端口 | 外部端口 | 说明 |
|------|---------|---------|------|
| API | 8000 | 8000 | FastAPI服务 |
| PostgreSQL | 5432 | 5432 | 数据库 |
| Redis | 6379 | 6379 | 缓存 |
| Grafana | 3000 | 3000 | 监控面板 |
| Prometheus | 9090 | 9090 | 指标采集 |
| Kibana | 5601 | 5601 | 日志查看 |

### B. 目录结构

```
AI_shezhen/
├── alembic/                    # 数据库迁移文件
│   └── versions/               # 迁移版本
├── api_service/                # API服务
│   ├── app/                    # 应用代码
│   ├── Dockerfile              # Docker镜像
│   └── requirements.txt        # Python依赖
├── uni-app_frontend/           # 前端应用
│   ├── src/                    # 源代码
│   ├── package.json            # Node依赖
│   └── dist/                   # 构建产物
├── docker-compose.yml          # Docker Compose配置
├── alembic.ini                 # Alembic配置
└── docs/                       # 文档
    └── deployment.md           # 本文档
```

### C. 命令参考

```bash
# Docker Compose
docker compose up -d              # 启动服务
docker compose down               # 停止服务
docker compose logs -f api        # 查看日志
docker compose ps                 # 查看状态
docker compose exec api bash      # 进入容器

# Alembic
alembic upgrade head             # 升级数据库
alembic downgrade -1             # 回滚一步
alembic current                  # 查看当前版本
alembic history                  # 查看历史
alembic revision -m "msg"        # 创建迁移

# uni-app
npm run dev:h5                   # H5开发
npm run build:h5                 # H5构建
npm run dev:mp-weixin            # 微信开发
npm run build:mp-weixin          # 微信构建
```

---

**文档版本:** v2.0
**最后更新:** 2026-02-22
**维护者:** Ralph Agent
**适用版本:** v3.0 (Phase 2: Refactoring)
