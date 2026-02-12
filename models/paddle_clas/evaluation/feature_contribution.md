# 舌诊分类模型特征贡献度说明
# Tongue Classification Model Feature Contribution Analysis

## 概述 (Overview)

本文档说明多任务舌诊分类模型的预测依据和特征贡献度分析方法。
This document explains the prediction rationale and feature contribution analysis methods for the multi-task tongue classification model.

## 模型架构 (Model Architecture)

### 特征提取器 (Feature Extractor)
- **Backbone**: PP-HGNetV2-B4
- **Input**: RGB图像 (224x224x3)
- **Output**: 864维特征向量

### 分类头结构 (Classification Head Structure)

模型包含6个独立的分类头，每个头负责不同的舌诊维度：

| 头名称 (Head Name) | 类别数 (Classes) | 任务类型 (Task Type) | 描述 (Description) |
|-------------------|------------------|-------------------|-------------------|
| tongue_color | 4 | 单标签 | 舌色分类 (淡红舌/红舌/绛紫舌/淡白舌) |
| coating_color | 4 | 单标签 | 苔色分类 (白苔/黄苔/黑苔/花剥苔) |
| tongue_shape | 3 | 单标签 | 舌形分类 (正常/胖大舌/瘦薄舌) |
| coating_quality | 3 | 单标签 | 苔质分类 (薄苔/厚苔/腐苔) |
| features | 4 | 多标签 | 特殊特征 (无/红点/裂纹/齿痕) |
| health | 2 | 单标签 | 健康状态 (不健康/健康舌) |

## 特征贡献度分析方法 (Feature Contribution Analysis Methods)

### 1. Grad-CAM 热力图 (Grad-CAM Heatmaps)

**原理 (Principle)**:
Grad-CAM (Gradient-weighted Class Activation Mapping) 通过计算目标类别相对于最后一层卷积特征图的梯度，生成类激活映射，可视化显示模型关注的图像区域。

**实现步骤 (Implementation Steps)**:
1. 前向传播获取特征图 (Forward pass to get feature maps)
2. 计算目标类别分数的梯度 (Compute gradients for target class score)
3. 全局平均池化梯度权重 (Global average pooling of gradient weights)
4. 加权组合特征图 (Weighted combination of feature maps)
5. 应用ReLU保留正向贡献 (Apply ReLU to keep positive contributions)

**解读指南 (Interpretation Guide)**:
- **红色区域 (Red areas)**: 高贡献度，对分类决策影响大
- **蓝色区域 (Blue areas)**: 低贡献度，对分类决策影响小
- **重点关注 (Key focus)**:
  - 舌色分析：舌体中心区域颜色
  - 苔色分析：舌苔覆盖区域颜色
  - 舌形分析：舌头轮廓和边缘形态
  - 特征分析：特殊纹理位置（裂纹、齿痕等）

### 2. 注意力权重分析 (Attention Weight Analysis)

**多头注意力机制 (Multi-head Attention)**:
每个分类头对特征向量的不同维度有不同的敏感度：

```
Head Weight = softmax(Feature_Vector @ Head_Weights)
```

**贡献度计算 (Contribution Calculation)**:
```python
importance_scores = {}
for head_name in head_names:
    confidence = max(softmax(predictions[head_name]))
    importance_scores[head_name] = confidence

# 归一化
total = sum(importance_scores.values())
importance_scores = {k: v/total for k, v in importance_scores.items()}
```

### 3. 梯度归因 (Gradient Attribution)

**Integrated Gradients**:
通过累积从输入到输出的梯度路径，计算每个输入特征对预测的贡献。

```python
# 沿线性路径积分
integrated_grad = []
for alpha in np.linspace(0, 1, n_steps):
    interpolated_input = alpha * input_tensor
    grads = compute_gradients(interpolated_input, target_class)
    integrated_grad.append(grads)

# 平均梯度
avg_grad = np.mean(integrated_grad, axis=0)
contribution = input_tensor * avg_grad
```

## 预测结果解释 (Prediction Interpretation)

### 示例输出格式 (Example Output Format)

```
预测类别: 红舌 (置信度: 92.5%)

主要依据:
  - 舌色 (tongue_color): 48.2%
  - 苔色 (coating_color): 26.1%
  - 舌形 (tongue_shape): 15.3%
  - 特殊特征 (features): 8.4%
  - 苔质 (coating_quality): 2.0%
  - 健康状态 (health): 0.1%
```

### 置信度等级 (Confidence Levels)

| 置信度范围 | 等级 | 建议 (Recommendation) |
|------------|-------|---------------------|
| > 90% | 高可信 | 结果可靠，可直接使用 |
| 70-90% | 中等可信 | 结果可用，建议人工复核 |
| 50-70% | 低可信 | 建议结合其他信息综合判断 |
| < 50% | 不可信 | 建议重新拍摄或人工诊断 |

## 特征相关性分析 (Feature Correlation Analysis)

### 舌色与苔色的关联 (Tongue Color vs Coating Color)

| 舌色 | 常见苔色组合 | 医学解释 |
|-------|--------------|----------|
| 淡红舌 | 白苔(薄) | 正常舌象，健康状态良好 |
| 红舌 | 黄苔(厚) | 内热较盛，可能有炎症 |
| 绛紫舌 | 少苔或无苔 | 瘀血内阻，循环不良 |
| 淡白舌 | 白苔(厚) | 阳虚寒湿，脾肾阳虚 |

### 舌形与健康的关联 (Tongue Shape vs Health Status)

| 舌形 | 健康倾向 | 特征关联 |
|-------|----------|----------|
| 正常舌 | 健康 | 各维度指标平衡 |
| 胖大舌 | 不健康 | 常伴齿痕、淡白舌、白苔厚 |
| 瘦薄舌 | 不健康 | 常伴红舌、裂纹、少苔 |

## 错误分析与模型局限性 (Error Analysis and Model Limitations)

### 常见错误类型 (Common Error Types)

#### 1. 类间混淆 (Inter-class Confusion)

**易混淆对 (Confused Pairs)**:
- 淡红舌 vs 红舌: 色谱接近，光照影响
- 白苔 vs 花剥苔: 苔色分布不均
- 正常 vs 胖大舌: 舌体大小阈值判断

**改进策略 (Improvement Strategies)**:
- 增加边界样本训练
- 使用Focal Loss调整难例权重
- 数据增强模拟不同光照条件

#### 2. 光照敏感度 (Lighting Sensitivity)

**问题表现 (Symptoms)**:
- 同一舌象在不同光照下预测不同
- 强光下偏向红舌、黄苔
- 弱光下偏向淡白舌、白苔

**缓解方法 (Mitigation)**:
- 输入标准化 (颜色校正)
- 数据增强包含光照变换
- Lab颜色空间特征提取

#### 3. 少数类识别困难 (Minority Class Difficulty)

**低召回率类别 (Low Recall Classes)**:
- 绛紫舌 (样本数<100)
- 黑苔 (样本数<50)
- 裂纹特征 (标注不一致)

**优化方案 (Optimization)**:
- 专项数据增强
- 过采样少数类
- 调整类别权重

## 可解释性验证方法 (Interpretability Validation)

### 医学专家一致性检验 (Medical Expert Consistency)

**验证指标 (Validation Metrics)**:
1. **特征定位一致性**: Grad-CAM高亮区域与专家标注区域重叠度
2. **预测依据合理性**: 模型关注特征与中医理论一致性
3. **错误案例分析**: 专家对模型错误的合理性评估

**验证流程 (Validation Process)**:
```
1. 随机抽取100个测试样本
2. 生成Grad-CAM可视化
3. 医学专家标注关键特征区域
4. 计算IoU (Intersection over Union)
5. 目标: 平均IoU > 0.6
```

### Ablation Study (消融实验)

**实验设计 (Experiment Design)**:

| 实验组 | 输入修改 | 预期变化 |
|--------|---------|----------|
| 完整图像 | 原始图像 | 基线性能 |
| 遮蔽舌体 | 舌体区域置0 | 舌色准确率大幅下降 |
| 遮蔽舌苔 | 苔层区域置0 | 苔色准确率大幅下降 |
| 颜色扰动 | RGB通道随机化 | 各头性能均下降 |

## 使用建议 (Usage Recommendations)

### 临床应用建议 (Clinical Recommendations)

1. **辅助诊断，非替代诊断**: 模型输出应作为辅助参考，最终诊断需由专业医师确认

2. **置信度阈值设置**:
   - 高置信度(>90%): 可直接用于初筛
   - 中置信度(70-90%): 需人工复核
   - 低置信度(<70%): 建议重新拍摄

3. **质量控制**:
   - 图像质量检查：清晰度、光照、角度
   - 设备标准化：固定拍摄环境参数
   - 定期校准：使用标准色卡校正颜色

### 模型更新建议 (Model Update Recommendations)

1. **持续学习**: 定期使用新标注数据微调模型
2. **错误反馈**: 收集临床误判案例用于模型改进
3. **版本控制**: 记录每次更新的性能变化

## 技术参考 (Technical References)

1. Grad-CAM: Selvaraju et al. "Grad-CAM: Visual Explanations from Deep Networks" (ICCV 2017)
2. Integrated Gradients: Sundararajan et al. "Axiomatic Attribution for Deep Networks" (ICML 2017)
3. Multi-task Learning: Caruana (1997) "Multitask Learning"
4. Focal Loss: Lin et al. "Focal Loss for Dense Object Detection" (ICCV 2017)

---

**文档版本 (Version)**: 1.0
**最后更新 (Last Updated)**: 2026-02-12
**维护者 (Maintainer)**: Ralph Agent
