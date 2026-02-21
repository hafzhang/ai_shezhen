# AI舌诊智能诊断系统 - uni-app前端

基于 uni-app (Vue 3 + TypeScript) 的跨平台前端应用，支持 H5、微信小程序和抖音小程序。

## 技术栈

- **框架**: uni-app 3.x (Vue 3 Composition API)
- **语言**: TypeScript 5.x
- **状态管理**: Pinia + pinia-plugin-persistedstate
- **UI组件**: uview-plus 2.x
- **构建工具**: Vite 5.x
- **样式**: SCSS

## 项目结构

```
uni-app_frontend/
├── src/
│   ├── api/              # API接口定义
│   ├── components/       # 公共组件
│   ├── pages/            # 页面
│   │   ├── index/        # 首页
│   │   ├── login/        # 登录页
│   │   └── register/     # 注册页
│   ├── store/            # Pinia状态管理
│   │   └── user.ts       # 用户状态
│   ├── utils/            # 工具函数
│   │   └── request.ts    # 网络请求封装
│   ├── static/           # 静态资源
│   ├── uni_modules/      # uni-app插件模块
│   ├── App.vue           # 应用入口组件
│   ├── main.ts           # 应用入口文件
│   ├── manifest.json     # 应用配置文件
│   └── pages.json        # 页面路由配置
├── public/               # 公共静态资源
├── package.json          # 项目依赖
├── tsconfig.json         # TypeScript配置
├── vite.config.ts        # Vite配置
└── index.html            # HTML入口文件
```

## 开发指南

### 安装依赖

```bash
cd uni-app_frontend
npm install
```

### 开发模式

```bash
# H5开发
npm run dev:h5

# 微信小程序开发
npm run dev:mp-weixin

# 抖音小程序开发
npm run dev:mp-toutiao
```

### 生产构建

```bash
# H5构建
npm run build:h5

# 微信小程序构建
npm run build:mp-weixin

# 抖音小程序构建
npm run build:mp-toutiao
```

### 类型检查

```bash
npm run type-check
```

## API集成

所有API请求通过 `@/utils/request` 发送到后端服务（`http://localhost:8000/api/v2`）。

开发环境下，Vite会自动代理 `/api` 请求到后端服务。

## 环境变量

创建 `.env` 文件配置环境变量（可选）：

```
VITE_API_BASE_URL=http://localhost:8000/api/v2
VITE_APP_TITLE=AI舌诊智能诊断系统
```

## 浏览器访问

H5开发模式启动后，访问：`http://localhost:3000`

## 注意事项

1. **uview-plus**: 本项目使用uview-plus UI组件库，首次运行需要通过HBuilderX导入插件或使用npm安装
2. **跨平台编译**: 不同平台可能需要特定的配置调整，详见uni-app官方文档
3. **API代理**: 开发模式下Vite配置了API代理，生产环境需配置正确的API地址

## 相关文档

- [uni-app官方文档](https://uniapp.dcloud.net.cn/)
- [Vue 3文档](https://cn.vuejs.org/)
- [Pinia文档](https://pinia.vuejs.org/zh/)
- [uview-plus文档](https://uview-plus.jiangruyi.com/)
