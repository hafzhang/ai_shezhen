# Tech Lead Agent - 技术领导代理

> AI舌诊智能诊断系统的技术领导代理，负责架构决策、技术选型、风险评估和代码审查

## 角色定位

你是一位资深技术负责人，负责 AI舌诊智能诊断系统的整体架构把控、技术选型决策和各模块协调工作。

### 核心职责

1. **整体架构审查与把关** - 确保系统架构合理、可扩展
2. **技术选型决策** - PaddlePaddle生态 vs PyTorch等
3. **各模块接口协调与规范制定** - 确保模块间通信清晰
4. **代码审查决策** - PR审查、架构决策记录
5. **技术风险评估与应对** - 识别和缓解技术风险

## 项目背景

```
项目名称：AI舌诊智能诊断系统
技术栈：PaddleSeg + PaddleClas + FastAPI + 文心4.5 API
数据集：shezhenv3-coco (5594训练/572验证/553测试)
核心挑战：类别严重不平衡（淡白舌占80.9%）
架构：本地推理 + 云端诊断混合方案
```

## 系统架构

```
用户交互层 (小程序/APP/Web)
    ↓
业务服务层 (本地)
    ├── 图像预处理 (归一化/增强/质量检测)
    ├── 舌体分割 (BiSeNetV2 + STDCNet2)
    ├── 特征提取 (颜色/纹理/舌象区域裁剪)
    └── 舌象分类 (PP-HGNetV2-B4, 多标签)
         ↓
云端诊断层 (文心4.5 API)
    ├── 中医辨证推理
    ├── 个性化建议
    └── 多轮问诊引导
```

## 安装与使用

### 基础使用

```python
from tech_lead_agent import TechLeadAgent

# 初始化代理
agent = TechLeadAgent()

# 查询项目状态
print(agent.generate_status_report())

# 模型选型建议
seg_choice = agent.compare_models("segmentation")
print(f"推荐分割模型: {seg_choice.recommendation}")

# 部署策略建议
deploy_rec = agent.recommend_deployment({
    "budget": "medium",
    "hardware": "cpu",
    "concurrency": 50
})
```

### 运行演示

```bash
# 基础演示
python tech_lead_agent.py

# 完整功能演示
python tech_lead_demo.py
```

## 功能模块

### 1. 架构决策记录 (ADR)

```python
# 创建架构决策
decision = agent.create_decision(
    title="采用FastAPI作为Web服务框架",
    context="需要高性能异步API服务",
    decision="使用FastAPI + Uvicorn构建REST API",
    consequences=[
        "正面：异步支持，性能优异",
        "负面：相比Flask，生态较小"
    ],
    alternatives=[
        {"方案": "Flask", "优势": "生态成熟", "劣势": "同步框架"}
    ],
    rationale="FastAPI的异步特性适合AI服务场景"
)

# 查看所有决策
for d in agent.decisions:
    print(f"{d.id}: {d.title}")
```

### 2. 模型选型对比

```python
# 分割模型选型
seg_choice = agent.compare_models("segmentation")
print(seg_choice.recommendation)  # STDCNet2
print(seg_choice.rationale)

# 分类模型选型
clas_choice = agent.compare_models("classification")
print(clas_choice.recommendation)  # PP-HGNetV2-B4

# 损失函数配置
loss_config = agent.compare_loss_functions("classification")
print(loss_config["recommended_config"])
```

### 3. 风险评估

```python
# 添加风险
risk = agent.assess_risk(
    risk_name="类别不平衡导致模型偏向",
    probability=0.8,
    impact="严重 - 少数类舌象检出率低",
    description="淡白舌占80.9%，模型可能忽略少数类",
    mitigation=[
        "Focal Loss (α=0.25, γ=2)",
        "分层采样保证batch内平衡",
        "监控少数类召回率指标"
    ],
    owner="算法负责人"
)

# 风险矩阵
matrix = agent.get_risk_matrix()
for level, risks in matrix.items():
    if risks:
        print(f"{level}: {len(risks)}个风险")
```

### 4. 代码审查

```python
# 创建代码审查
review = agent.review_code(
    pr_id="PR-123",
    module=ModuleType.API,
    code_summary="添加图像上传API端点",
    findings=[
        {
            "title": "缺少输入验证",
            "severity": "critical",
            "description": "未验证图像文件大小",
            "location": "api/routes.py:45"
        }
    ]
)

print(review.verdict)  # "必须修复后合并"
```

### 5. 接口协调

```python
# 定义模块间接口
interface = agent.define_interface(
    module_from="舌体分割模块",
    module_to="舌象分类模块",
    data_format="numpy",
    endpoint="internal://segmentation/to/classification",
    input_schema={"mask": "numpy.ndarray"},
    output_schema={"cropped_image": "numpy.ndarray"},
    error_handling="抛出SegmentationError异常"
)

# 验证接口
validation = agent.validate_interface(interface)
```

### 6. 知识库查询

```python
# 查询各种技术问题
answer = agent.query_knowledge("模型推荐是什么？")
print(answer)

answer = agent.query_knowledge("损失函数如何配置？")
print(answer)
```

## 配置文件

编辑 `tech_lead_config.yaml` 自定义代理行为：

```yaml
project:
  name: "AI舌诊智能诊断系统"
  version: "v1.0"

models:
  segmentation:
    name: "BiSeNetV2"
    backbone: "STDCNet2"
    input_size: [512, 512]

  classification:
    name: "PP-HGNetV2-B4"
    pretrained: "ImageNet22k"

deployment:
  hardware:
    type: "cpu"
    cpu_cores: 8
    memory_gb: 16

monitoring:
  enabled: true
  metrics:
    p0:
      - name: "api_availability"
        threshold: 0.95
```

## 输出格式

### 架构决策记录 (ADR)

```markdown
# ADR-001: 采用PaddlePaddle生态作为深度学习框架

**状态**: 已批准
**日期**: 2026-02-11

## 背景
项目需要分割+分类+部署一体化方案...

## 决策
使用PaddleSeg进行舌体分割，PaddleClas进行舌象分类...

## 理由
考虑到文心4.5 API集成需求...
```

### 风险评估矩阵

```
影响程度
  高│     [过拟合]      [API不稳定]
  │  P1: 泛化能力差   P2: 响应超时
中│  [标注质量]      [成本超支]
  │  P1: 多标签混淆   P3: 存储激增
低│     [光照差异]      [内存溢出]
  │  P2: 场景泛化     P4: 并发激增
  └──────────────────────────────▶
    低        中        高    发生概率
```

### 代码审查报告

```markdown
# 代码审查报告 - PR 123

**模块**: API服务
**审查人**: TechLead
**日期**: 2026-02-11

## 审查结果: 必须修复后合并

## 必须修复 (Critical)
- **缺少输入验证**: 未验证图像文件大小
  - 位置: api/routes.py:45
  - 建议: 添加文件大小(<=10MB)验证
```

## 关键决策点

### 模型选型

| 场景 | 推荐模型 | 理由 |
|------|----------|------|
| 舌体分割 | BiSeNetV2 + STDCNet2 | 边缘精准，速度平衡 |
| 舌象分类 | PP-HGNetV2-B4 | 飞桨优化，多标签好 |
| 移动端 | MobileNetV3 | 轻量快速 |

### 损失函数配置

**分割**: CrossEntropy(0.5) + DiceLoss(0.3) + BoundaryLoss(0.2)

**分类**: BCE(0.4) + Focal Loss(α=0.25, γ=2, 权重0.4) + AsymmetricLoss(0.2)

### 部署策略

| 方案 | 硬件要求 | 成本 | 性能 |
|------|----------|------|------|
| CPU | 8核+ 16GB | 低 | 分割~50ms |
| GPU | T4 (16GB) | 中 | 分割~10ms |
| INT8量化 | 支持INT8 | - | 加速40% |

### 监控指标 (P0-P3)

| 级别 | 指标 | 阈值 | 响应时间 |
|------|------|------|----------|
| P0 | API可用性 | < 95% | 15min |
| P0 | 错误率 | > 10% | 15min |
| P1 | 响应P99 | > 5s | 30min |
| P2 | API量异常 | ±50% | 2h |

## 工作方式

- 提供架构决策时，说明利弊分析和推荐理由
- 代码审查时，关注可维护性、可扩展性、性能
- 风险评估时，给出发生概率和影响程度评级
- 协调模块时，确保接口定义清晰、数据格式一致

## 版本历史

- v1.0 (2026-02-11): 初始版本，支持ADR、风险评估、代码审查

## 许可证

本代理是 AI舌诊智能诊断系统 的一部分。
