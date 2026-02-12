# 困难样本标注与模型迭代指南

**系统名称**: AI舌诊智能诊断系统
**版本**: v2.3
**日期**: 2026年___月___日

---

## 一、概述

本文档描述基于用户反馈的困难样本识别、专家标注和模型重训练流程，用于持续改进AI模型性能。

### 1.1 目的

- 识别困难样本类型和分布
- 建立专家标注工作流
- 实现模型迭代和重训练机制
- 追踪改进效果

### 1.2 适用范围

| 适用模块 | 舌体分割 | 舌象分类 |
|---------|---------|---------|
| 困难样本挖掘 | ✅ | ✅ |
| 专家标注管理 | ✅ | ✅ |
| 模型重训练 | ✅ | ✅ |

---

## 二、困难样本识别

### 2.1 数据来源

| 数据来源 | 描述 | 收集方式 |
|---------|------|---------|
| **用户反馈** | 诊断结果页反馈（有/无帮助） | feedback.py |
| **人工申诉** | 用户提交的误诊申诉 | feedback.py |
| **评估日志** | 模型评估的错误案例分析 | evaluation/*.py |
| **使用日志** | 诊断数量统计 | Prometheus |

### 2.2 困难样本类型

#### 2.2.1 分割困难样本

| 困难类型 | 特征描述 | 示例原因 |
|---------|---------|---------|
| **光照异常** | 过亮/过暗/强阴影 | 影响舌色判断 |
| **角度问题** | 极端拍摄角度（俯视/仰视） | 影响舌形识别 |
| **舌苔干扰** | 食物残留（染色） | 影响苔色/苔质判断 |
| **舌形异常** | 严重齿痕/裂纹/胖大舌 | 影响舌形判断 |
| **边界模糊** | 舌体边界不清晰 | 分割困难 |

#### 2.2.2 分类困难样本

| 困难类型 | 特征描述 | 示例原因 |
|---------|---------|---------|
| **少见类别** | 绛紫舌/黑苔/剥落苔 | 样本少导致欠拟合 |
| **特征组合** | 罕见特征组合（如红舌+厚苔） | 训练数据不足 |
| **置信度低** | 模型输出置信度<60% | 特征不明确 |
| **类别混淆** | 淡红舌与淡红舌混淆 | 特征区分度不够 |
| **多标签冲突** | 红舌+齿痕同时出现 | 标签一致性差 |

### 2.3 识别方法

**自动识别**（已实现）:

```python
# 1. 评估日志分析
python -m models.paddle_seg.evaluation.segmentation_evaluator

# 2. 困难样本挖掘
python -m models.paddle_seg.training.analyze_hard_examples \
    --mining-dir models/paddle_seg/output/hard_mining \
    --train-data datasets/processed/seg_v1/train \
    --compare-epochs 5,10,20,30,40,50
```

**人工审核**（需补充）:

- 人工复核自动识别结果
- 专家确认困难样本类型
- 标注需要改进的特征维度

### 2.4 困难样本库管理

| 阶段 | 样本数量 | 存储位置 |
|------|---------|---------|
| 初始识别 | 自动生成 | models/paddle_seg/output/hard_mining/ |
| 待标注 | 专家审核后 | datasets/processed/hard_samples/annotated/ |
| 已标注 | 完成标注 | datasets/processed/hard_samples/labeled/ |
| 待训练 | 加入训练集 | datasets/processed/hard_samples/training/ |

---

## 三、专家标注工作流

### 3.1 标注工具

**推荐工具**:
- **LabelImg**: 图像标注工具（免费）
- **CVAT (Computer Vision Annotation Tool)**: 开源标注平台
- **自研Web标注平台**: 基于Vue3 + FastAPI后端

### 3.2 标注规范

#### 3.2.1 分割标注

| 标签 | 值 | 说明 |
|------|------|------|
| tongue_area | 0/1 | 舌体区域（0=背景，1=舌体） |
| boundary_clear | 0/1 | 边界是否清晰 |
| lighting_condition | normal/overexposed/underexposed | 光照条件 |

#### 3.2.2 分类标注

| 标签 | 维度 | 值域 |
|------|------|------|
| tongue_color | 舌色 | 淡红/淡红/红/绛紫/青/淡白 |
| coating_color | 苔色 | 白/黄/灰/黑/剥落/无苔 |
| tongue_shape | 舌形 | 正常/胖大/瘦小/齿痕/裂纹 |
| special_features | 特殊特征 | 红点/齿痕/裂纹/瘀点/剥落 |

### 3.3 质量控制

**审核要求**:
- 双人复核：同一样本由两名专家独立标注
- 一致性阈值：IoU>0.85或Kappa>0.8
- 专家审核：高级中医师审核标注质量

**验收标准**:
- 困难样本标注完成率：>95%
- 标注一致性：Kappa系数>0.8
- 困难样本数量：扩展至>500样本

---

## 四、模型迭代流程

### 4.1 触发条件

| 触发条件 | 阈值 | 说明 |
|---------|------|---------|
| 困难样本数量 | ≥500 | 自动触发重训练 |
| 用户反馈准确率 | <85% | 模型性能不足 |
| 评估指标下降 | mAP下降>3% | 需要改进 |

### 4.2 重训练策略

**数据准备**:
```bash
# 1. 合并原始训练集和困难样本
python datasets/tools/merge_datasets.py \
    --original datasets/processed/seg_v1/train \
    --hard-samples datasets/processed/hard_samples/labeled \
    --output datasets/processed/seg_v2/train

# 2. 验证合并后的数据分布
python datasets/tools/analyze_distribution.py \
    --input datasets/processed/seg_v2/train \
    --output datasets/processed/seg_v2/distribution.json
```

**增量训练**:
```yaml
# 训练配置 (incremental_training.yml)
training:
  type: incremental
  base_checkpoint: "models/deploy/segment_fp16/model_fp16.pdparams"
  hard_mining_dir: "models/paddle_seg/output/hard_mining"
  additional_epochs: 10  # 额外训练轮次

data:
  train_images: "datasets/processed/seg_v2/train/images"
  train_masks: "datasets/processed/seg_v2/train/masks"
  val_images: "datasets/processed/seg_v1/val/images"
  val_masks: "datasets/processed/seg_v1/val/masks"

optimization:
  learning_rate: 0.0001
  hard_example_weight: 2.0  # 困难样本权重加倍
  early_stop:
    patience: 15
    min_delta: 0.001
```

**全量重训练**（如增量效果不明显）:
```bash
# 使用合并后的完整数据集重新训练
python train_segmentation.py \
    --config models/paddle_seg/configs/bisenetv2_incremental.yml \
    --epochs 80
```

### 4.3 迭代验证

| 指标 | 改进前 | 改进后 | 验证方法 |
|------|---------|---------|--------|
| 分割mIoU | 当前值 | 目标值>当前值+1% | 测试集评估 |
| 分类mAP | 当前值 | 目标值>当前值+3% | 测试集评估 |
| 困难样本召回率 | N/A | 目标值>70% | 困难样本集评估 |
| 端到端延迟 | 当前值 | 目标值<当前值-50ms | 压力测试 |

---

## 五、自动化流程

### 5.1 CI/CD集成

**持续集成流程**:
```yaml
# .github/workflows/difficult_samples.yml
name: Difficult Sample Mining

on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点运行
  workflow_dispatch:
    inputs: threshold

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Run hard example analysis
        run: |
          python -m models.paddle_seg.training.analyze_hard_examples \
            --mining-dir models/paddle_seg/output/hard_mining \
            --threshold 5
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: hard-samples-$(date +%Y%m%d)
```

### 5.2 自动重训练触发

**触发条件**（满足任一即触发）:
- 困难样本数量≥500
- 用户反馈准确率连续7天<85%
- 评估指标mIoU下降>2%

**自动化流程**:
```bash
# scripts/trigger_retraining.sh
#!/bin/bash

# 检查触发条件
HARD_SAMPLES=$(find datasets/processed/hard_samples/labeled -name "*.jpg" | wc -l)
FB_ACCURACY=$(python -c "from api_service.database import get_fb_accuracy; print(get_fb_accuracy(days=7))")

if [ $HARD_SAMPLES -ge 500 ] || [ $FB_ACCURACY -lt 85 ]; then
    echo "Triggering retraining..."
    bash scripts/start_retraining.sh
fi
```

---

## 六、效果评估

### 6.1 评估维度

| 维度 | 指标 | 基准值 |
|------|------|--------|
| 困难样本识别率 | ≥90% | 自动识别准确率 |
| 标注效率 | >50样本/天 | 人均标注速度 |
| 模型改进 | mIoU+1% | 评估指标提升 |
| 用户满意度 | ≥85% | 反馈准确率 |

### 6.2 A/B测试

```python
# 运行A/B测试对比新旧模型
python testing/ab_test_compare.py \
    --model-a models/deploy/segment_fp16/ \
    --model-b models/deploy/segment_v2/ \
    --test-data datasets/processed/seg_v1/val \
    --metrics miou,dice,f1
```

---

## 七、时间与成本

### 7.1 时间规划

| 阶段 | 周期 | 关键路径 |
|------|------|---------|
| 困难样本收集 | 持续进行 | 用户反馈持续收集 |
| 专家标注 | 2-4周 | 招募和培训专家 |
| 模型重训练 | 1-2周 | 包括评估和部署 |
| 评估验证 | 1周 | 测试集验证 |

### 7.2 成本估算

| 项目 | 成本（元） | 说明 |
|------|---------|--------|
| 标注工具 | 0-50,000 | 开源或自研 |
| 专家标注费 | 100,000-500,000 | 按样本数量和单价 |
| 重训练计算 | 2,000-10,000 | GPU云服务费用 |
| 评估测试 | 5,000-10,000 | 测试集和人工测试 |

---

## 八、工具和脚本

### 8.1 数据分析脚本

```python
# datasets/tools/analyze_difficult_samples.py
import json
from pathlib import Path

def analyze_feedback_patterns(feedback_file):
    """分析反馈模式识别困难样本"""
    with open(feedback_file, 'r') as f:
        feedback_data = json.load(f)

    # 统计误诊原因
    error_reasons = {}
    for fb in feedback_data:
        if fb.get('category') == 'inaccurate':
            reason = fb.get('comment', 'unknown')
            error_reasons[reason] = error_reasons.get(reason, 0) + 1

    # 找出高频错误
    top_errors = sorted(error_reasons.items(),
                      key=lambda x: x[1],
                      reverse=True)[:5]

    return {
        'total_feedback': len(feedback_data),
        'inaccurate_count': sum(1 for fb in feedback_data
                          if fb.get('category') == 'inaccurate'),
        'error_distribution': dict(error_reasons),
        'top_errors': top_errors
    }
```

### 8.2 标注质量检查

```python
# datasets/tools/check_annotation_quality.py
def calculate_iou(mask1_path, mask2_path):
    """计算两个标注之间的IoU"""
    import cv2
    import numpy as np

    mask1 = cv2.imread(mask1_path, cv2.IMREAD_GRAYSCALE)
    mask2 = cv2.imread(mask2_path, cv2.IMREAD_GRAYSCALE)

    intersection = np.logical_and(mask1, mask2)
    union = np.logical_or(mask1, mask2)
    iou = np.sum(intersection) / np.sum(union)

    return iou

# 使用示例
iou = calculate_iou('sample1_mask.png', 'sample2_mask.png')
if iou < 0.85:
    print(f'Warning: Low consistency (IoU={iou:.3f})')
```

---

## 九、检查清单

### 9.1 数据收集

- [ ] 困难样本自动识别脚本正常运行
- [ ] 用户反馈API正常收集数据
- [ ] 反馈数据自动分类和统计

### 9.2 标注流程

- [ ] 标注工具已安装和配置
- [ ] 标注规范文档完成
- [ ] 标注专家已培训和认证
- [ ] 质量控制流程建立

### 9.3 模型迭代

- [ ] 重训练脚本已验证
- [ ] CI/CD自动化流程已配置
- [ ] A/B测试框架已实现
- [ ] 效果评估指标已定义

---

**版本**: v1.0
**编制人**: Ralph Agent
**审核人**: [待填写]
**批准人**: [待填写]
**生效日期**: ______年___月___日
