# 分类模型评估报告 (Classification Model Evaluation Report)

**生成时间 (Generated)**: {timestamp}
**模型版本 (Model Version)**: {model_version}
**数据集版本 (Dataset Version)**: {dataset_version}

---

## 执行摘要 (Executive Summary)

### 评估结论 (Evaluation Conclusion)

{conclusion_text}

### 关键指标概览 (Key Metrics Overview)

| 指标 (Metric) | 目标值 (Target) | 实际值 (Actual) | 状态 (Status) |
|----------------|----------------|-----------------|--------------|
| 多标签mAP | > 0.70 | {map_value:.4f} | {map_status} |
| 宏平均F1 | > 0.65 | {macro_f1:.4f} | {f1_status} |
| 多数类准确率 | > 85% | {majority_acc:.1%} | {majority_status} |
| 少数类召回率 | > 60% | {minority_recall:.1%} | {minority_status} |

---

## 1. 模型信息 (Model Information)

### 架构概览 (Architecture Overview)

```
Backbone: PP-HGNetV2-B4
Feature Dimension: 864
Number of Heads: 6
Total Parameters: {total_params:,}
Trainable Parameters: {trainable_params:,}
```

### 分类头配置 (Classification Head Configuration)

| 头名称 (Head) | 类别数 | 权重 | 多标签 | 损失类型 |
|---------------|---------|--------|--------|----------|
| tongue_color | 4 | 0.25 | 否 | Focal |
| coating_color | 4 | 0.20 | 否 | Focal |
| tongue_shape | 3 | 0.15 | 否 | Focal |
| coating_quality | 3 | 0.15 | 否 | Focal |
| features | 4 | 0.15 | 是 | Asymmetric |
| health | 2 | 0.10 | 否 | Focal |

---

## 2. 数据集统计 (Dataset Statistics)

### 测试集分布 (Test Set Distribution)

```
总样本数: {num_samples}
各维度样本数均衡度: {balance_score:.2f}
```

### 类别分布 (Class Distribution)

**tongue_color (舌色)**:
| 类别 | 样本数 | 占比 |
|-----|--------|-----|
| 淡红舌 | {tongue_pale_red:,} | {tongue_pale_red_pct:.1%} |
| 红舌 | {tongue_red:,} | {tongue_red_pct:.1%} |
| 绛紫舌 | {tongue_purple:,} | {tongue_purple_pct:.1%} |
| 淡白舌 | {tongue_pale_white:,} | {tongue_pale_white_pct:.1%} |

{other_class_distributions}

---

## 3. 性能分析 (Performance Analysis)

### 3.1 整体性能 (Overall Performance)

```
Macro F1: {macro_f1:.4f}
Macro mAP: {macro_map:.4f}
推理耗时: {inference_time_ms:.2f} ms
吞吐量: {fps:.2f} FPS
```

### 3.2 各维度性能 (Per-Dimension Performance)

#### 舌色分类 (Tongue Color)

| 指标 | 值 |
|-----|---|
| Accuracy | {tc_acc:.4f} |
| Precision | {tc_prec:.4f} |
| Recall | {tc_rec:.4f} |
| F1 | {tc_f1:.4f} |
| AP | {tc_ap:.4f} |

**各类别F1分数 (Per-class F1)**:
- 淡红舌: {tc_f1_pale_red:.3f}
- 红舌: {tc_f1_red:.3f}
- 绛紫舌: {tc_f1_purple:.3f}
- 淡白舌: {tc_f1_pale_white:.3f}

#### 苔色分类 (Coating Color)

| 指标 | 值 |
|-----|---|
| Accuracy | {cc_acc:.4f} |
| Precision | {cc_prec:.4f} |
| Recall | {cc_rec:.4f} |
| F1 | {cc_f1:.4f} |
| AP | {cc_ap:.4f} |

**各类别F1分数 (Per-class F1)**:
- 白苔: {cc_f1_white:.3f}
- 黄苔: {cc_f1_yellow:.3f}
- 黑苔: {cc_f1_black:.3f}
- 花剥苔: {cc_f1_patchy:.3f}

#### 舌形分类 (Tongue Shape)

| 指标 | 值 |
|-----|---|
| Accuracy | {ts_acc:.4f} |
| Precision | {ts_prec:.4f} |
| Recall | {ts_rec:.4f} |
| F1 | {ts_f1:.4f} |
| AP | {ts_ap:.4f} |

**各类别F1分数 (Per-class F1)**:
- 正常: {ts_f1_normal:.3f}
- 胖大舌: {ts_f1_fat:.3f}
- 瘦薄舌: {ts_f1_thin:.3f}

#### 苔质分类 (Coating Quality)

| 指标 | 值 |
|-----|---|
| Accuracy | {cq_acc:.4f} |
| Precision | {cq_prec:.4f} |
| Recall | {cq_rec:.4f} |
| F1 | {cq_f1:.4f} |
| AP | {cq_ap:.4f} |

**各类别F1分数 (Per-class F1)**:
- 薄苔: {cq_f1_thin:.3f}
- 厚苔: {cq_f1_thick:.3f}
- 腐苔: {cq_f1_rotten:.3f}

#### 特征检测 (Special Features)

| 指标 | 值 |
|-----|---|
| Accuracy | {feat_acc:.4f} |
| Precision | {feat_prec:.4f} |
| Recall | {feat_rec:.4f} |
| F1 | {feat_f1:.4f} |
| AP | {feat_ap:.4f} |

**各类别F1分数 (Per-class F1)**:
- 无: {feat_f1_none:.3f}
- 红点: {feat_f1_redspot:.3f}
- 裂纹: {feat_f1_crack:.3f}
- 齿痕: {feat_f1_toothmark:.3f}

#### 健康状态 (Health Status)

| 指标 | 值 |
|-----|---|
| Accuracy | {health_acc:.4f} |
| Precision | {health_prec:.4f} |
| Recall | {health_rec:.4f} |
| F1 | {health_f1:.4f} |
| AP | {health_ap:.4f} |

**各类别F1分数 (Per-class F1)**:
- 不健康: {health_f1_unhealthy:.3f}
- 健康舌: {health_f1_healthy:.3f}

---

## 4. 错误分析 (Error Analysis)

### 4.1 混淆矩阵分析 (Confusion Matrix Analysis)

每个分类头的混淆矩阵已保存在 `confusion_matrices/` 目录。

主要混淆模式 (Major Confusion Patterns):

**tongue_color (舌色)**:
{tongue_color_confusion}

**coating_color (苔色)**:
{coating_color_confusion}

**tongue_shape (舌形)**:
{tongue_shape_confusion}

### 4.2 典型错误案例 (Typical Error Cases)

| 图像 | 预测 | 真实 | 置信度 | 错误类型 |
|-----|-------|-------|--------|---------|
{error_cases_table}

### 4.3 错误原因分析 (Error Cause Analysis)

**数据质量问题 (Data Quality Issues)**:
- {data_quality_issues}

**模型局限性 (Model Limitations)**:
- {model_limitations}

**标注不一致 (Annotation Inconsistencies)**:
- {annotation_inconsistencies}

---

## 5. 可解释性分析 (Interpretability Analysis)

### 5.1 Grad-CAM可视化 (Grad-CAM Visualization)

Grad-CAM热力图已保存在 `gradcam/` 目录。

**解读说明 (Interpretation Guide)**:
- 红色区域表示对分类决策贡献高的特征
- 蓝色区域表示对分类决策贡献低的特征

### 5.2 特征贡献度分析 (Feature Contribution Analysis)

各分类头的平均特征重要性：

| 头名称 | 平均贡献度 |
|--------|-----------|
| tongue_color | {contrib_tc:.1%} |
| coating_color | {contrib_cc:.1%} |
| tongue_shape | {contrib_ts:.1%} |
| coating_quality | {contrib_cq:.1%} |
| features | {contrib_feat:.1%} |
| health | {contrib_health:.1%} |

### 5.3 预测依据说明 (Prediction Rationale)

**高置信度预测示例 (High Confidence Example)**:
```
图像: sample_001.jpg
预测: 红舌 (92.3%)

主要依据:
  - 舌色特征: 舌体整体呈现红色调
  - 区域定位: 舌中心区域高激活
  - 辅助特征: 苔色偏黄，符合内热表现
```

**低置信度预测示例 (Low Confidence Example)**:
```
图像: sample_002.jpg
预测: 花剥苔 (58.7%)

不确定原因:
  - 苔色分布不均匀
  - 光照影响颜色判断
  - 边界区域特征模糊
  建议: 重新拍摄或人工复核
```

---

## 6. 与基线对比 (Baseline Comparison)

| 指标 | 基线模型 | 当前模型 | 提升 |
|-----|---------|---------|-----|
| Macro mAP | {baseline_map:.4f} | {current_map:.4f} | {map_improvement:+.1%} |
| Macro F1 | {baseline_f1:.4f} | {current_f1:.4f} | {f1_improvement:+.1%} |

---

## 7. 建议与改进方向 (Recommendations)

### 7.1 模型改进建议 (Model Improvement Suggestions)

1. **少数类优化 (Minority Class Optimization)**:
   - 针对绛紫舌、黑苔等少数类增加专项数据增强
   - 调整Focal Loss的α参数，提高少数类权重
   - 收集更多少数类样本

2. **边界样本优化 (Boundary Sample Optimization)**:
   - 增加淡红舌与红舌之间的过渡样本
   - 淡白舌与白苔的联合标注
   - 花剥苔边界区域的精细标注

3. **鲁棒性增强 (Robustness Enhancement)**:
   - 光照不变特征提取（Lab颜色空间）
   - 颜色校正预处理
   - 多角度/光照条件的数据增强

### 7.2 部署建议 (Deployment Recommendations)

1. **置信度阈值设置**:
   - 自动诊断: 置信度 > 90%
   - 辅助诊断: 置信度 70-90%
   - 人工复核: 置信度 < 70%

2. **质量控制**:
   - 图像质量自动检测
   - 不合格图像自动重拍提示
   - 定期模型性能监控

---

## 附录 (Appendix)

### A. 评估指标定义 (Metric Definitions)

- **mAP (mean Average Precision)**: 所有类别的平均精度
- **F1-score**: 精确率和召回率的调和平均
- **Macro F1**: 各类别F1的算术平均
- **Micro F1**: 所有样本的总体F1

### B. 文件清单 (File List)

```
evaluation/
├── evaluation_report.json        # 完整评估结果（JSON格式）
├── evaluation_summary.txt        # 评估摘要（文本格式）
├── confusion_matrices/          # 混淆矩阵可视化
│   ├── tongue_color_confusion_matrix.png
│   ├── coating_color_confusion_matrix.png
│   └── ...
├── gradcam/                    # Grad-CAM可视化
│   ├── sample_001_tongue_color.png
│   ├── sample_001_coating_color.png
│   └── ...
└── worst_cases/               # 最差错误案例
    ├── fp_cases.png
    ├── fn_cases.png
    └── ...
```

---

**报告生成器 (Generator)**: Ralph Agent v2.3
**评估模块版本 (Module Version)**: 1.0
**日期 (Date)**: {timestamp}
