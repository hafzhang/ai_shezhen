# 多标签编码映射说明文档

## 概述

本文档描述了从原始21类舌诊标签到6维度19类one-hot编码的映射规则。

## 映射结构

### 维度定义

| 维度 | 类别数 | 类别详情 | 说明 |
|------|--------|----------|------|
| 舌色 (tongue_color) | 4 | 淡白、淡红、红、绛紫 | 舌体颜色特征 |
| 苔色 (coating_color) | 4 | 白苔、黄苔、黑苔、花剥苔 | 舌苔颜色特征 |
| 舌形 (tongue_shape) | 3 | 正常、胖大、瘦薄 | 舌体形态特征 |
| 苔质 (coating_quality) | 3 | 薄苔、厚苔、腻苔 | 舌苔质量特征 |
| 特征标记 (features) | 3 | 红点、裂纹、齿痕 | 特殊特征标记 |
| 健康标记 (health) | 2 | 非健康舌、健康舌 | 健康状态标记 |

**总计**: 18个特征类别 + 1个健康标记 = 19维输出

### One-hot向量结构

```
索引 0-3:   舌色 [淡白, 淡红, 红, 绛紫]
索引 4-7:   苔色 [白苔, 黄苔, 黑苔, 花剥苔]
索引 8-10:  舌形 [正常, 胖大, 瘦薄]
索引 11-13: 苔质 [薄苔, 厚苔, 腻苔]
索引 14-16: 特征 [红点, 裂纹, 齿痕]
索引 17:    保留位 (未使用)
索引 18:    健康标记 (0=非健康, 1=健康)
```

## 原始类别映射表

| 原始ID | 类别名 | 舌色 | 苔色 | 舌形 | 苔质 | 特征 | 健康 | 说明 |
|:------:|:------:|:----:|:----:|:----:|:----:|:----:|:----:|:-----|
| 0 | jiankangshe | - | - | - | - | - | 1 | - |
| 1 | botaishe | - | - | - | 薄苔 | - | 0 | - |
| 2 | hongshe | 红 | - | - | - | - | 0 | - |
| 3 | zishe | 绛紫 | - | - | - | - | 0 | - |
| 4 | pangdashe | - | - | 胖大 | - | - | 0 | - |
| 5 | shoushe | - | - | 瘦薄 | - | - | 0 | - |
| 6 | hongdianshe | - | - | - | - | 红点 | 0 | - |
| 7 | liewenshe | - | - | - | - | 裂纹 | 0 | - |
| 8 | chihenshe | - | - | - | - | 齿痕 | 0 | - |
| 9 | baitaishe | - | 白苔 | - | - | - | 0 | - |
| 10 | huangtaishe | - | 黄苔 | - | - | - | 0 | - |
| 11 | heitaishe | - | 黑苔 | - | - | - | 0 | - |
| 12 | huataishe | - | 花剥苔 | - | - | - | 0 | - |
| 13 | shenquao | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 14 | shenqutu | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 15 | gandanao | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 16 | gandantu | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 17 | piweiao | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 18 | piweitu | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 19 | xinfeiao | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |
| 20 | xinfeitu | - | - | - | - | - | 0 | 证型标注（不参与分类训练） |


## 统计信息

- 总处理图像数: 6719
- 空标签图像数: 194
- 多标签图像数: 4784
- 健康舌数量: 206
- 平均每图标签数: 1.99

## 使用示例

### 读取标签文件

```python
import numpy as np

# 读取标签文件
with open('datasets/processed/clas_v1/train/labels.txt', 'r') as f:
    lines = f.readlines()

# 解析单行
filename, labels_str = lines[0].strip().split('\t')
label_vector = np.array([int(x) for x in labels_str.split(',')])

# label_vector 是19维向量
# label_vector[0:4]   -> 舌色
# label_vector[4:8]   -> 苔色
# label_vector[8:11]  -> 舌形
# label_vector[11:14] -> 苔质
# label_vector[14:17] -> 特征
# label_vector[18]    -> 健康标记
```

### 转换为可读格式

```python
from datasets.tools.class_mapping import DIMENSION_CATEGORIES, DIMENSION_INDICES

def vector_to_readable(vector):
    result = {}
    for dim_name, (start, end) in DIMENSION_INDICES.items():
        if dim_name == "health":
            result['is_healthy'] = bool(vector[18])
        else:
            active = np.where(vector[start:end] == 1)[0]
            categories = [DIMENSION_CATEGORIES[dim_name][i] for i in active]
            result[dim_name] = categories
    return result

# 使用
readable = vector_to_readable(label_vector)
print(readable)
# {'tongue_color': ['红'], 'coating_color': ['黄苔'], ...}
```

## 注意事项

1. **证型类别不参与分类训练**: 类别ID 13-20（证型标签）仅用于云端LLM诊断的few-shot示例，不包含在分类模型的输出中。

2. **多标签处理**: 单张图像可能包含多个标签，使用one-hot编码时需要注意多个类别可以同时为1。

3. **健康舌特殊处理**: 当图像仅标注为"jiankangshe"（健康舌）时，所有特征维度为0，健康标记为1。

4. **类别权重**: 由于原始数据集存在严重的类别不平衡，建议使用计算得到的类别权重进行训练。

## 生成信息

- 生成时间: 2026-02-11 19:42:22
- 数据集版本: shezhenv3-coco
- 脚本版本: v1.0
