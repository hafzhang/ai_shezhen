# Tech Lead Agent 快速入门指南

## 文件说明

| 文件名 | 说明 |
|--------|------|
| `tech_lead_agent.py` | 核心代理类，包含所有功能实现 |
| `tech_lead_config.yaml` | 配置文件，定义项目参数 |
| `tech_lead_demo.py` | 功能演示脚本，展示所有功能 |
| `test_tech_lead.py` | 测试套件，验证功能正确性 |
| `TECH_LEAD_README.md` | 详细文档 |
| `TECH_LEAD_QUICKSTART.md` | 本文件 |

## 快速开始

### 1. 初始化代理

```python
from tech_lead_agent import TechLeadAgent

# 创建代理实例
agent = TechLeadAgent()
```

### 2. 查看项目状态

```python
# 生成状态报告
report = agent.generate_status_report()
print(report)
```

### 3. 获取模型选型建议

```python
# 分割模型选型
seg_choice = agent.compare_models("segmentation")
print(f"推荐: {seg_choice.recommendation}")
print(f"理由: {seg_choice.rationale}")

# 分类模型选型
clas_choice = agent.compare_models("classification")
```

### 4. 部署策略建议

```python
# CPU部署
cpu_rec = agent.recommend_deployment({
    "budget": "medium",
    "hardware": "cpu",
    "concurrency": 50
})

# GPU部署
gpu_rec = agent.recommend_deployment({
    "budget": "high",
    "hardware": "gpu",
    "concurrency": 100
})
```

### 5. 风险管理

```python
# 添加风险
risk = agent.assess_risk(
    risk_name="模型过拟合",
    probability=0.6,
    impact="严重",
    description="小数据集可能导致过拟合",
    mitigation=["Early Stopping", "数据增强"],
    owner="算法负责人"
)

# 查看风险矩阵
matrix = agent.get_risk_matrix()
```

### 6. 架构决策

```python
# 创建新决策
decision = agent.create_decision(
    title="采用FastAPI作为Web框架",
    context="需要高性能异步API",
    decision="使用FastAPI + Uvicorn",
    consequences=[
        "正面：异步支持",
        "负面：生态较小"
    ],
    alternatives=[
        {"方案": "Flask", "优势": "成熟", "劣势": "同步"}
    ],
    rationale="异步特性适合AI服务"
)
```

### 7. 代码审查

```python
from tech_lead_agent import ModuleType

review = agent.review_code(
    pr_id="PR-123",
    module=ModuleType.API,
    code_summary="添加新的API端点",
    findings=[
        {
            "title": "缺少输入验证",
            "severity": "critical",
            "description": "未验证文件大小",
            "location": "api.py:45"
        }
    ]
)
print(review.verdict)
```

### 8. 知识查询

```python
# 查询各种问题
answer = agent.query_knowledge("模型推荐是什么？")
print(answer)

answer = agent.query_knowledge("损失函数如何配置？")
print(answer)
```

### 9. 获取推荐配置

```python
# 获取各模块推荐配置
configs = ["segmentation", "classification", "deployment", "monitoring"]

for module in configs:
    config = agent.get_recommended_config(module)
    print(f"{module}: {config}")
```

## 常见使用场景

### 场景1：项目启动时

```python
agent = TechLeadAgent()

# 查看已有架构决策
for d in agent.decisions:
    print(f"{d.id}: {d.title}")

# 获取技术栈推荐
seg = agent.compare_models("segmentation")
clas = agent.compare_models("classification")
deploy = agent.recommend_deployment({"hardware": "cpu"})
```

### 场景2：代码审查时

```python
# 审查PR
review = agent.review_code(
    pr_id="PR-456",
    module=ModuleType.CLASSIFICATION,
    code_summary="优化多标签分类损失函数",
    findings=[
        {
            "title": "Focal Loss参数未调优",
            "severity": "high",
            "description": "γ=2可能不适合当前数据",
            "location": "loss.py:23"
        }
    ]
)

# 生成审查评论
comment = agent.generate_review_comment(review)
```

### 场景3：风险评估会议

```python
agent = TechLeadAgent()

# 添加项目风险
risks_data = [
    {"name": "类别不平衡", "probability": 0.8, "impact": "严重", ...},
    {"name": "API不稳定", "probability": 0.3, "impact": "中等", ...},
    ...
]

for r in risks_data:
    agent.assess_risk(**r)

# 生成风险报告
matrix = agent.get_risk_matrix()
analysis = agent.analyze_project_risks()
```

### 场景4：部署决策

```python
# 根据约束条件获取部署方案
scenarios = {
    "开发环境": {"budget": "low", "hardware": "cpu", "concurrency": 10},
    "生产环境": {"budget": "high", "hardware": "gpu", "concurrency": 100},
}

for name, constraints in scenarios.items():
    rec = agent.recommend_deployment(**constraints)
    print(f"{name}: {rec['primary_strategy']}")
```

## 运行演示和测试

```bash
# 基础演示
python tech_lead_agent.py

# 完整功能演示
python tech_lead_demo.py

# 运行测试套件
python test_tech_lead.py
```

## 核心功能总结

| 功能 | 方法 | 用途 |
|------|------|------|
| 架构决策 | `create_decision()` | 记录技术决策 |
| 模型选型 | `compare_models()` | 获取模型推荐 |
| 部署建议 | `recommend_deployment()` | 获取部署方案 |
| 风险评估 | `assess_risk()` | 管理项目风险 |
| 代码审查 | `review_code()` | PR审查 |
| 接口协调 | `define_interface()` | 定义模块接口 |
| 知识查询 | `query_knowledge()` | 查询技术问题 |
| 配置推荐 | `get_recommended_config()` | 获取推荐配置 |
| 状态报告 | `generate_status_report()` | 生成项目报告 |

## 项目背景知识

代理内置了以下项目知识：

- 项目名称：AI舌诊智能诊断系统
- 数据集：shezhenv3-coco (5594训练/572验证/553测试)
- 核心挑战：类别严重不平衡（淡白舌占80.9%）
- 技术栈：PaddleSeg + PaddleClas + FastAPI + 文心4.5 API

## 下一步

1. 运行 `python tech_lead_demo.py` 查看完整功能演示
2. 运行 `python test_tech_lead.py` 验证所有功能正常
3. 阅读 `TECH_LEAD_README.md` 了解详细文档
4. 根据需要修改 `tech_lead_config.yaml` 配置
