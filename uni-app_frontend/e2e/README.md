# E2E测试文档

## 概述

这是AI舌诊智能诊断系统H5前端的端到端测试套件，使用Playwright进行自动化测试。

## 测试范围

### US-174: End-to-end test - H5

本测试套件覆盖以下场景：

1. **用户注册流程测试**
   - 导航到注册页面
   - 填写注册表单（手机号、密码、昵称）
   - 验证密码确认匹配
   - 成功注册并登录

2. **用户登录流程测试**
   - 导航到登录页面
   - 输入有效凭证登录
   - 验证无效手机号错误处理
   - 验证无效密码错误处理
   - 成功登录后显示用户信息

3. **完整诊断流程测试**
   - 从首页开始诊断
   - 上传舌象图片（拍照/相册）
   - 填写用户信息（年龄、性别、主诉）
   - 提交诊断请求
   - 查看诊断结果

4. **历史记录查看测试**
   - 导航到历史记录页面
   - 查看诊断历史列表
   - 查看单个诊断详情

5. **健康档案管理测试**
   - 导航到健康档案页面
   - 添加健康记录
   - 编辑健康记录
   - 删除健康记录

6. **用户登出测试**
   - 从个人中心登出
   - 验证登出后状态
   - 验证受保护路由重定向

7. **响应式设计测试**
   - 移动端 viewport (375x667)
   - 平板 viewport (768x1024)
   - 桌面 viewport (1920x1080)

## 前置条件

### 1. 启动API服务

```bash
cd api_service
python -m app.main
```

确保API服务运行在 `http://localhost:8000`

### 2. 安装依赖

```bash
cd uni-app_frontend
npm install
```

### 3. 安装Playwright浏览器

```bash
npx playwright install
```

## 运行测试

### 运行所有测试

```bash
npm run test:e2e
```

### 以UI模式运行测试

```bash
npm run test:e2e:ui
```

### 调试模式运行

```bash
npm run test:e2e:debug
```

### 运行特定测试文件

```bash
npx playwright test h5-complete-flow.spec.ts
```

### 查看测试报告

```bash
npm run test:e2e:report
```

## 环境变量

可以设置以下环境变量：

- `BASE_URL`: H5前端URL（默认: `http://localhost:5173`）
- `API_BASE_URL`: API服务URL（默认: `http://localhost:8000`）

示例：

```bash
BASE_URL=http://localhost:3000 API_BASE_URL=http://api.example.com npm run test:e2e
```

## 测试文件结构

```
e2e/
├── README.md                    # 本文档
├── playwright.config.ts         # Playwright配置
├── global-setup.ts              # 全局测试设置
├── global-teardown.ts           # 全局测试清理
├── helpers.ts                   # 测试辅助函数
├── h5-complete-flow.spec.ts     # 完整流程测试套件
├── screenshots/                 # 测试截图目录（自动创建）
└── playwright-report/           # 测试报告目录（自动创建）
```

## 测试辅助函数

`helpers.ts` 提供以下辅助函数：

- `generateTestPhone()`: 生成测试手机号
- `generateTestPassword()`: 生成测试密码
- `generateTestNickname()`: 生成测试昵称
- `registerTestUser()`: 通过API注册测试用户
- `loginTestUser()`: 通过API登录测试用户
- `cleanupTestUser()`: 清理测试用户
- `waitForPageStable()`: 等待页面稳定
- `fillFormField()`: 填写表单字段
- `clickAndWait()`: 点击并等待
- `isElementVisible()`: 检查元素是否可见
- `getElementText()`: 获取元素文本
- `takeScreenshot()`: 截图
- `TestUserStorage`: 测试用户数据存储类

## 测试数据

测试使用以下模式生成随机数据：

- **手机号**: `139` + 时间戳后8位
- **密码**: `Test` + 时间戳 + `!`
- **昵称**: `TestUser` + 时间戳

测试完成后会自动清理创建的测试用户。

## 截图

测试失败时会自动保存截图到 `e2e/screenshots/` 目录。

每个测试步骤也会保存截图用于文档和调试。

## CI/CD集成

在CI环境中，测试配置会自动：

- 仅重试失败的测试（2次）
- 使用单worker运行测试
- 生成HTML测试报告

## 已知限制

1. **文件上传**: 实际的图片上传功能需要文件系统访问，当前测试主要验证UI流程
2. **API响应**: 某些测试假设API响应正常，实际使用中可能需要mock API
3. **异步操作**: 某些异步操作使用了固定等待时间，可能需要优化

## 未来改进

- [ ] 添加API mock支持
- [ ] 添加更多诊断场景测试
- [ ] 添加性能测试
- [ ] 添加可访问性测试
- [ ] 添加视觉回归测试
- [ ] 优化异步操作等待策略

## 故障排除

### 测试失败：API服务不可用

确保API服务正在运行：

```bash
curl http://localhost:8000/api/v2/health
```

### 测试失败：端口已被占用

修改 `playwright.config.ts` 中的端口配置。

### 测试超时

在 `playwright.config.ts` 中增加超时时间。

### 浏览器未安装

运行：

```bash
npx playwright install
```
