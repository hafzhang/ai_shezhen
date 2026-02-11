# AI舌诊智能诊断系统 - ML Engineer Agent

机器学习工程师代理，负责医学图像AI模型的训练、优化和部署。

## 代理角色定位

**角色**: ML Engineer (机器学习工程师)
**专长**: 医学图像AI、PaddlePaddle、类别不平衡处理
**职责**: 数据分析、模型训练、性能优化、部署准备

## 项目数据集

```
数据集: shezhenv3-coco
├── 训练集: 5,594张
├── 验证集: 572张
└── 测试集: 553张

类别分布（严重不平衡）:
├── Top 1: 淡白舌 (jiankangshe) 4,379张 (80.9%)
├── Top 2: 薄苔舌 (botaishe) 2,578张 (47.7%)
├── Top 3: 红点舌 (hongdianshe) 1,493张 (27.6%)
├── 少数类: 绛紫舌 (zishe) 209张 (3.9%)
└── 极少类: 黑苔、花剥苔 <100张

多标签特征: 单图平均2.3个标签
```

## 项目结构

```
AI_shezhen/
├── agents/
│   └── ml_engineer.py          # ML Engineer Agent主类
├── src/
│   ├── data/
│   │   └── dataset.py           # 数据集类和采样器
│   ├── models/
│   │   ├── segmentation.py      # 分割模型 (BiSeNetV2)
│   │   └── classification.py    # 分类模型 (PP-HGNetV2)
│   ├── training/
│   │   └── trainer.py           # 训练器
│   └── evaluation/
│       └── metrics.py           # 评估指标
├── configs/
│   └── experiment_config.yaml   # 实验配置
├── train_segmentation.py        # 分割训练脚本
├── train_classification.py      # 分类训练脚本
├── evaluate.py                  # 评估脚本
├── analyze_dataset.py           # 数据分析脚本
└── README.md                    # 本文件
```

## 核心功能

### 1. 数据分析

快速分析数据集统计信息：

```bash
python analyze_dataset.py --split train --visualize --report
```

输出：
- 类别分布统计
- 多标签分布
- 不平衡分析
- 可视化图表
- 分析报告

### 2. 分割模型训练

舌体分割模型（BiSeNetV2 + STDCNet2）：

```bash
python train_segmentation.py --config configs/experiment_config.yaml
```

**配置要点：**
- 模型: BiSeNetV2 (轻量级双路径网络)
- 损失: CrossEntropy(0.5) + Dice(0.3) + Boundary(0.2)
- 优化器: SGD (momentum=0.9)
- 学习率: Warmup + PolyLR
- 目标: mIoU > 0.92, Dice > 0.95

### 3. 分类模型训练

多标签分类模型（PP-HGNetV2-B4）：

```bash
python train_classification.py --config configs/experiment_config.yaml
```

**类别不平衡处理：**
- Focal Loss (α=0.25, γ=2)
- Asymmetric Loss
- 分层采样
- 类别加权 (weight = 1/√count)
- 难例挖掘

**类别重构：**
```
21类 → 6维度18类
├── 舌色(4): 淡白/淡红/红/绛紫
├── 苔色(4): 白苔/黄苔/黑苔/花剥苔
├── 舌形(3): 正常/胖大/瘦薄
├── 苔质(3): 薄苔/厚苔/腻苔
├── 特征(3): 红点/裂纹/齿痕
└── 综合(1): 健康舌
```

### 4. 模型评估

```bash
# 评估分割模型
python evaluate.py --task segmentation --checkpoint checkpoints/segmentation/best.pdparams

# 评估分类模型
python evaluate.py --task classification --checkpoint checkpoints/classification/best.pdparams
```

### 5. 恢复训练

```bash
python train_segmentation.py --resume checkpoints/segmentation/latest.pdparams
python train_classification.py --resume checkpoints/classification/latest.pdparams
```

## 评估指标

### 分割指标
- mIoU: > 0.92
- Dice系数: > 0.95
- 像素准确率: > 0.98
- 边界IoU: > 0.85
- 推理时延: < 33ms (CPU)

### 分类指标
- 宏平均F1: > 0.65
- mAP: > 0.70
- 少数类召回率: > 0.60
- 多数类召回率: > 0.85

### 不平衡指标
- 召回率平衡比: > 0.7
- 召回率方差: < 0.05
- Gini系数: < 0.3

## 类别不平衡专项方案

### 第一层：数据层面
- 过采样：少数类复制+轻微变换
- 欠采样：多数类随机丢弃（保持80%）
- 目标比例：< 10:1

### 第二层：算法层面
- Focal Loss：α=0.25, γ=2
- 类别加权：weight = 1/√count
- 分层采样：每batch均衡
- 难例挖掘：loss Top 10%重采样

### 第三层：评估层面
- 宏平均F1（重点关注）
- 少数类单独评估
- 混淆矩阵分析

## 依赖环境

```bash
# PaddlePaddle
pip install paddlepaddle-gpu==2.6.0  # GPU版本
# 或
pip install paddlepaddle==2.6.0      # CPU版本

# 其他依赖
pip install pycocotools
pip install albumentations
pip install scikit-learn
pip install matplotlib seaborn
pip install pyyaml
pip install tqdm
pip install mlflow
```

## 实验跟踪

使用MLflow跟踪实验：

```bash
# 启动MLflow UI
mlflow ui
```

访问：http://localhost:5000

## 工作风格

1. **数据驱动决策**：用实验数据说话
2. **记录实验结果**：使用MLflow记录所有实验
3. **对比baseline**：说明改进点和效果
4. **关注训练曲线**：监控loss变化，检测过拟合
5. **问题诊断**：{现象, 原因, 解决方案}

## 输出格式

- **实验报告**: {配置, 结果, 对比, 结论}
- **代码注释**: 关键参数说明
- **问题诊断**: {现象, 原因, 解决方案}

## 联系方式

- ML Engineer Agent
- 项目: AI舌诊智能诊断系统
- 日期: 2026-02-11

## 快速开始

```bash
# 1. 分析数据集
python analyze_dataset.py --split train --visualize --report

# 2. 训练分割模型
python train_segmentation.py

# 3. 训练分类模型
python train_classification.py

# 4. 评估模型
python evaluate.py --task segmentation --checkpoint checkpoints/segmentation/best.pdparams
python evaluate.py --task classification --checkpoint checkpoints/classification/best.pdparams
```
