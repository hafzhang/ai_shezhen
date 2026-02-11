#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多标签编码映射脚本（21类→6维度18类）

实现原始21类到6维度18类的one-hot编码映射，生成分类任务标签文件。
支持多标签共存、证型标签分离、类别权重计算等功能。

Mapping Structure:
- 舌色(4): 淡白/淡红/红/绛紫
- 苔色(4): 白苔/黄苔/黑苔/花剥苔
- 舌形(3): 正常/胖大/瘦薄
- 苔质(3): 薄苔/厚苔/腻苔
- 特征标记(3): 红点/裂纹/齿痕
- 健康(1): 健康舌标记

Usage:
    python datasets/tools/class_mapping.py --data_root path/to/shezhenv3-coco --split train
    python datasets/tools/class_mapping.py --all
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict, Counter
from itertools import combinations

import numpy as np
from tqdm import tqdm
from pycocotools.coco import COCO

# Set Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Class Mapping Definition ====================

# Original 21 classes (ID 0-20)
ORIGINAL_CLASSES = [
    "jiankangshe",   # 0: 健康舌
    "botaishe",      # 1: 薄苔舌
    "hongshe",       # 2: 红舌
    "zishe",         # 3: 绛紫舌
    "pangdashe",     # 4: 胖大舌
    "shoushe",       # 5: 瘦薄舌
    "hongdianshe",   # 6: 红点舌
    "liewenshe",     # 7: 裂纹舌
    "chihenshe",     # 8: 齿痕舌
    "baitaishe",     # 9: 白苔舌
    "huangtaishe",   # 10: 黄苔舌
    "heitaishe",     # 11: 黑苔舌
    "huataishe",     # 12: 花剥苔舌
    "shenquao",      # 13: 肾气虚证型
    "shenqutu",      # 14: 肾气虚+其他证型
    "gandanao",      # 15: 肝胆偏颇证型
    "gandantu",      # 16: 肝胆偏颇+其他证型
    "piweiao",       # 17: 脾胃虚弱证型
    "piweitu",       # 18: 脾胃虚弱+其他证型
    "xinfeiao",      # 19: 心肺气虚证型
    "xinfeitu",      # 20: 心肺气虚+其他证型
]

# 6 Dimension names with their categories
DIMENSION_NAMES = {
    "tongue_color": "舌色",
    "coating_color": "苔色",
    "tongue_shape": "舌形",
    "coating_quality": "苔质",
    "features": "特征标记",
    "health": "健康标记"
}

# Category names for each dimension
DIMENSION_CATEGORIES = {
    "tongue_color": ["淡白", "淡红", "红", "绛紫"],
    "coating_color": ["白苔", "黄苔", "黑苔", "花剥苔"],
    "tongue_shape": ["正常", "胖大", "瘦薄"],
    "coating_quality": ["薄苔", "厚苔", "腻苔"],
    "features": ["红点", "裂纹", "齿痕"],
    "health": ["非健康舌", "健康舌"]
}

# Complete mapping: original_class_id -> (dimension_idx, category_idx) list
# Format: {class_id: [(dim_idx, cat_idx), ...]}
CLASS_MAPPING = {
    0: [("health", 1)],  # jiankangshe -> 健康舌
    1: [("coating_quality", 0)],  # botaishe -> 薄苔
    2: [("tongue_color", 2)],  # hongshe -> 红舌
    3: [("tongue_color", 3)],  # zishe -> 绛紫舌
    4: [("tongue_shape", 1)],  # pangdashe -> 胖大舌
    5: [("tongue_shape", 2)],  # shoushe -> 瘦薄舌
    6: [("features", 0)],  # hongdianshe -> 红点
    7: [("features", 1)],  # liewenshe -> 裂纹
    8: [("features", 2)],  # chihenshe -> 齿痕
    9: [("coating_color", 0)],  # baitaishe -> 白苔
    10: [("coating_color", 1)],  # huangtaishe -> 黄苔
    11: [("coating_color", 2)],  # heitaishe -> 黑苔
    12: [("coating_color", 3)],  # huataishe -> 花剥苔
    # Syndrome classes (13-20) are NOT used for classification training
    # They will be used for few-shot prompts in LLM diagnosis
    13: [],  # shenquao
    14: [],  # shenqutu
    15: [],  # gandanao
    16: [],  # gandantu
    17: [],  # piweiao
    18: [],  # piweitu
    19: [],  # xinfeiao
    20: [],  # xinfeitu
}

# Dimension sizes for building one-hot vector
DIMENSION_SIZES = {
    "tongue_color": 4,
    "coating_color": 4,
    "tongue_shape": 3,
    "coating_quality": 3,
    "features": 3,
    "health": 2
}

# Total dimensions and categories
TOTAL_DIMENSIONS = 6
TOTAL_CATEGORIES = sum(DIMENSION_SIZES.values())  # 18 + health=2

# Dimension indices in flattened vector
DIMENSION_INDICES = {
    "tongue_color": (0, 4),
    "coating_color": (4, 8),
    "tongue_shape": (8, 11),
    "coating_quality": (11, 14),
    "features": (14, 17),
    "health": (17, 19)
}


# ==================== Class Mapping Converter ====================

class ClassMappingConverter:
    """多标签编码映射转换器"""

    def __init__(self, data_root: str, output_base: str = None):
        """
        初始化转换器

        Args:
            data_root: COCO数据集根目录
            output_base: 输出基础目录 (默认: datasets/processed/clas_v1)
        """
        self.data_root = Path(data_root)
        if output_base is None:
            output_base = Path(__file__).parent.parent.parent / "processed" / "clas_v1"
        else:
            output_base = Path(output_base)

        self.output_base = output_base
        self.stats = {
            "total_images": 0,
            "processed_images": 0,
            "empty_labels": [],
            "multi_label_count": 0,
            "syndrome_only_count": 0,
            "healthy_tongue_count": 0,
            "category_distribution": defaultdict(int),
            "dimension_distribution": defaultdict(int),
            "multi_label_cooccurrence": defaultdict(int),
            "label_vectors": []
        }

    def original_to_multihot(self, category_ids: List[int]) -> np.ndarray:
        """
        将原始类别ID列表转换为多标签one-hot向量

        Args:
            category_ids: 原始类别ID列表 (e.g., [1, 2, 9])

        Returns:
            19维one-hot向量 (18个特征类别 + 1个健康标记)
        """
        # Initialize zero vector: 18 feature categories + 1 health flag = 19
        # Note: health is binary (0=non-healthy, 1=healthy)
        vector = np.zeros(19, dtype=np.int8)

        has_healthy = False
        has_features = False

        for cat_id in category_ids:
            if cat_id not in CLASS_MAPPING:
                continue

            mappings = CLASS_MAPPING[cat_id]
            if not mappings:
                # Syndrome class, skip for classification
                continue

            for dim_name, cat_idx in mappings:
                has_features = True

                if dim_name == "health":
                    has_healthy = True
                else:
                    # Calculate position in the 18-dimension feature vector
                    dim_start, _ = DIMENSION_INDICES[dim_name]
                    vector[dim_start + cat_idx] = 1

        # Set health flag (index 18)
        if has_healthy:
            vector[18] = 1
        elif not has_features:
            # No features marked, could be healthy tongue or missing data
            # Set to healthy as default
            vector[18] = 1

        return vector

    def multihot_to_readable(self, vector: np.ndarray) -> Dict[str, Any]:
        """
        将one-hot向量转换为可读格式

        Args:
            vector: 19维one-hot向量

        Returns:
            可读的标签字典
        """
        result = {}

        for dim_name, (start, end) in DIMENSION_INDICES.items():
            if dim_name == "health":
                # Health flag
                result["is_healthy"] = bool(vector[18])
                result["health_label"] = "健康舌" if vector[18] == 1 else "非健康舌"
            else:
                # Feature dimensions
                dim_vector = vector[start:end]
                active_indices = np.where(dim_vector == 1)[0]

                categories = DIMENSION_CATEGORIES[dim_name]
                active_categories = [categories[i] for i in active_indices]

                result[DIMENSION_NAMES[dim_name]] = active_categories

        return result

    def process_split(self, split: str = "train") -> Dict[str, Any]:
        """
        处理单个数据集划分

        Args:
            split: 数据集划分名称 (train/val/test)

        Returns:
            处理结果统计
        """
        logger.info(f"Processing {split} split...")

        # Paths
        split_dir = self.data_root / split
        annotation_file = split_dir / "annotations" / f"{split}.json"
        image_dir = split_dir / "images"

        if not annotation_file.exists():
            logger.error(f"Annotation file not found: {annotation_file}")
            return {}

        # Load COCO annotations
        coco = COCO(str(annotation_file))

        # Create output directories
        output_split_dir = self.output_base / split
        output_split_dir.mkdir(parents=True, exist_ok=True)
        labels_file = output_split_dir / "labels.txt"

        # Process each image
        image_ids = coco.getImgIds()
        self.stats["total_images"] += len(image_ids)

        label_lines = []
        multi_label_cooccurrence_local = defaultdict(int)

        for img_id in tqdm(image_ids, desc=f"Processing {split}"):
            img_info = coco.loadImgs(img_id)[0]
            ann_ids = coco.getAnnIds(imgIds=img_id)
            annotations = coco.loadAnns(ann_ids)

            # Extract category IDs
            category_ids = list(set([ann["category_id"] for ann in annotations]))

            # Filter out syndrome categories (13-20) for classification
            feature_categories = [c for c in category_ids if c <= 12]
            syndrome_categories = [c for c in category_ids if c >= 13]

            # Convert to multi-hot vector
            label_vector = self.original_to_multihot(feature_categories)

            # Store statistics
            if len(feature_categories) == 0:
                self.stats["empty_labels"].append(img_info["file_name"])
            elif len(feature_categories) > 1:
                self.stats["multi_label_count"] += 1

            # Check for healthy tongue
            if label_vector[18] == 1 and np.sum(label_vector[:18]) == 0:
                self.stats["healthy_tongue_count"] += 1

            # Check if only syndrome labels
            if len(feature_categories) == 0 and len(syndrome_categories) > 0:
                self.stats["syndrome_only_count"] += 1

            # Category distribution
            for cat_id in feature_categories:
                self.stats["category_distribution"][cat_id] += 1
                # Map to dimension
                if cat_id in CLASS_MAPPING:
                    for dim_name, _ in CLASS_MAPPING[cat_id]:
                        self.stats["dimension_distribution"][dim_name] += 1

            # Multi-label co-occurrence (for feature categories only)
            if len(feature_categories) > 1:
                for cat1, cat2 in combinations(feature_categories, 2):
                    pair = tuple(sorted([cat1, cat2]))
                    multi_label_cooccurrence_local[pair] += 1

            # Format: image_name<TAB>label1,label2,...,label19
            label_str = ",".join(map(str, label_vector.tolist()))
            label_lines.append(f"{img_info['file_name']}\t{label_str}")

            self.stats["label_vectors"].append(label_vector)

            self.stats["processed_images"] += 1

        # Merge co-occurrence
        for pair, count in multi_label_cooccurrence_local.items():
            self.stats["multi_label_cooccurrence"][pair] += count

        # Write labels file
        with open(labels_file, 'w', encoding='utf-8') as f:
            for line in label_lines:
                f.write(line + '\n')

        logger.info(f"Written {len(label_lines)} labels to {labels_file}")

        return {
            "split": split,
            "total_images": len(image_ids),
            "processed_images": len(label_lines),
            "empty_labels": len([l for l in label_lines if "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1" in l]),
            "multi_label_images": sum(1 for v in self.stats["label_vectors"][-len(image_ids):] if np.sum(v[:18]) > 1)
        }

    def generate_mapping_table(self) -> str:
        """
        生成完整的类别映射表（CSV格式）

        Returns:
            CSV格式的映射表字符串
        """
        lines = []
        lines.append("原始类别ID,类别名称,舌色,苔色,舌形,苔质,特征标记,健康标记,证型关联,说明")

        for cat_id, name in enumerate(ORIGINAL_CLASSES):
            mappings = CLASS_MAPPING.get(cat_id, [])

            # Initialize dimension mappings
            dims = {
                "tongue_color": "-",
                "coating_color": "-",
                "tongue_shape": "-",
                "coating_quality": "-",
                "features": "-",
                "health": "-"
            }

            for dim_name, cat_idx in mappings:
                if dim_name == "health":
                    dims["health"] = "1" if cat_idx == 1 else "0"
                else:
                    categories = DIMENSION_CATEGORIES[dim_name]
                    dims[dim_name] = categories[cat_idx]

            # Determine syndrome type
            if cat_id >= 13:
                syndrome_map = {
                    13: "肾气虚", 14: "肾气虚+",
                    15: "肝胆偏颇", 16: "肝胆偏颇+",
                    17: "脾胃虚弱", 18: "脾胃虚弱+",
                    19: "心肺气虚", 20: "心肺气虚+"
                }
                syndrome = syndrome_map.get(cat_id, "")
                note = "证型标注"
            else:
                syndrome = "-"
                note_map = {
                    0: "健康舌", 1: "薄白苔", 2: "红舌", 3: "绛紫舌",
                    4: "胖大舌", 5: "瘦薄舌", 6: "红点舌", 7: "裂纹舌",
                    8: "齿痕舌", 9: "白苔", 10: "黄苔", 11: "黑苔", 12: "花剥苔"
                }
                note = note_map.get(cat_id, "")

            line = f"{cat_id},{name},{dims['tongue_color']},{dims['coating_color']},{dims['tongue_shape']},{dims['coating_quality']},{dims['features']},{dims['health']},{syndrome},{note}"
            lines.append(line)

        return "\n".join(lines)

    def generate_cooccurrence_matrix(self) -> Dict[str, Any]:
        """
        生成多标签共现矩阵分析

        Returns:
            共现矩阵分析结果
        """
        # Build feature dimension co-occurrence
        dimension_cooccurrence = defaultdict(lambda: defaultdict(int))

        for (cat1, cat2), count in self.stats["multi_label_cooccurrence"].items():
            if cat1 in CLASS_MAPPING and cat2 in CLASS_MAPPING:
                dim1 = CLASS_MAPPING[cat1][0][0] if CLASS_MAPPING[cat1] else None
                dim2 = CLASS_MAPPING[cat2][0][0] if CLASS_MAPPING[cat2] else None

                if dim1 and dim2 and dim1 != "health" and dim2 != "health":
                    dimension_cooccurrence[dim1][dim2] += count
                    if dim1 != dim2:
                        dimension_cooccurrence[dim2][dim1] += count

        return dict(dimension_cooccurrence)

    def calculate_class_weights(self) -> Dict[str, float]:
        """
        计算类别权重（用于处理类别不平衡）

        使用公式: weight_i = total / (num_classes × count_i)

        Returns:
            类别权重字典
        """
        weights = {}

        # Calculate weights for each dimension's categories
        for dim_name, (start, end) in DIMENSION_INDICES.items():
            if dim_name == "health":
                continue

            dim_size = end - start
            dim_counts = [0] * dim_size

            # Count occurrences of each category
            for vector in self.stats["label_vectors"]:
                for i in range(dim_size):
                    if vector[start + i] == 1:
                        dim_counts[i] += 1

            # Calculate weights
            total_samples = len(self.stats["label_vectors"])
            base_weight = total_samples / (dim_size * max(sum(dim_counts), 1))

            for i, count in enumerate(dim_counts):
                if count > 0:
                    weight = total_samples / (dim_size * count)
                else:
                    weight = base_weight * 2  # Higher weight for unseen classes

                weights[f"{dim_name}_{i}"] = round(weight, 4)

        return weights

    def save_reports(self) -> List[str]:
        """
        保存所有报告文件

        Returns:
            保存的文件路径列表
        """
        report_files = []

        # 1. Mapping table (CSV)
        mapping_file = self.output_base / "class_mapping_table.csv"
        mapping_file.parent.mkdir(parents=True, exist_ok=True)

        with open(mapping_file, 'w', encoding='utf-8-sig') as f:
            f.write(self.generate_mapping_table())

        report_files.append(str(mapping_file))
        logger.info(f"Saved mapping table to {mapping_file}")

        # 2. Class weights (JSON)
        weights_file = self.output_base / "class_weights.json"
        weights = self.calculate_class_weights()

        with open(weights_file, 'w', encoding='utf-8') as f:
            json.dump({
                "dimension_sizes": DIMENSION_SIZES,
                "total_categories": TOTAL_CATEGORIES,
                "weights": weights,
                "weight_formula": "weight_i = total / (num_classes × count_i)"
            }, f, indent=2, ensure_ascii=False)

        report_files.append(str(weights_file))
        logger.info(f"Saved class weights to {weights_file}")

        # 3. Statistics report (JSON)
        stats_file = self.output_base / "statistics_report.json"

        # Calculate summary statistics
        total_vectors = np.array(self.stats["label_vectors"])
        dimension_summary = {}

        for dim_name, (start, end) in DIMENSION_INDICES.items():
            if dim_name == "health":
                continue

            dim_data = total_vectors[:, start:end]
            dimension_summary[dim_name] = {
                "categories": DIMENSION_CATEGORIES[dim_name],
                "positive_counts": [int(np.sum(dim_data[:, i])) for i in range(end - start)],
                "prevalence": [round(float(np.sum(dim_data[:, i]) / len(total_vectors) * 100), 2) for i in range(end - start)]
            }

        stats_report = {
            "total_images_processed": self.stats["total_images"],
            "empty_labels_count": len(self.stats["empty_labels"]),
            "multi_label_images": self.stats["multi_label_count"],
            "healthy_tongue_count": self.stats["healthy_tongue_count"],
            "syndrome_only_count": self.stats["syndrome_only_count"],
            "average_labels_per_image": round(np.mean([np.sum(v[:18]) for v in self.stats["label_vectors"]]), 2),
            "category_distribution": dict(self.stats["category_distribution"]),
            "dimension_distribution": dict(self.stats["dimension_distribution"]),
            "dimension_summary": dimension_summary,
            "cooccurrence_matrix": self.generate_cooccurrence_matrix()
        }

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_report, f, indent=2, ensure_ascii=False)

        report_files.append(str(stats_file))
        logger.info(f"Saved statistics report to {stats_file}")

        # 4. Mapping documentation (Markdown)
        doc_file = self.output_base / "MAPPING_DOCUMENTATION.md"

        with open(doc_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_documentation())

        report_files.append(str(doc_file))
        logger.info(f"Saved documentation to {doc_file}")

        return report_files

    def _generate_documentation(self) -> str:
        """生成映射说明文档"""
        doc = f"""# 多标签编码映射说明文档

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
"""

        for cat_id, name in enumerate(ORIGINAL_CLASSES):
            mappings = CLASS_MAPPING.get(cat_id, [])

            dim_strs = []
            for dim_idx in range(6):
                dim_names = ["tongue_color", "coating_color", "tongue_shape", "coating_quality", "features", "health"]
                dim_name = dim_names[dim_idx]

                if dim_name == "health":
                    for _, (m_dim, m_cat) in enumerate(mappings):
                        if m_dim == "health":
                            dim_strs.append("1" if m_cat == 1 else "0")
                            break
                    else:
                        dim_strs.append("0")
                else:
                    found = False
                    for _, (m_dim, m_cat) in enumerate(mappings):
                        if m_dim == dim_name:
                            categories = DIMENSION_CATEGORIES[dim_name]
                            dim_strs.append(categories[m_cat])
                            found = True
                            break
                    if not found:
                        dim_strs.append("-")

            if cat_id >= 13:
                note = "证型标注（不参与分类训练）"
            else:
                note = "-"

            doc += f"| {cat_id} | {name} | {dim_strs[0]} | {dim_strs[1]} | {dim_strs[2]} | {dim_strs[3]} | {dim_strs[4]} | {dim_strs[5]} | {note} |\n"

        doc += f"""

## 统计信息

- 总处理图像数: {self.stats['total_images']}
- 空标签图像数: {len(self.stats['empty_labels'])}
- 多标签图像数: {self.stats['multi_label_count']}
- 健康舌数量: {self.stats['healthy_tongue_count']}
- 平均每图标签数: {np.mean([np.sum(v[:18]) for v in self.stats['label_vectors']]) if self.stats['label_vectors'] else 0:.2f}

## 使用示例

### 读取标签文件

```python
import numpy as np

# 读取标签文件
with open('datasets/processed/clas_v1/train/labels.txt', 'r') as f:
    lines = f.readlines()

# 解析单行
filename, labels_str = lines[0].strip().split('\\t')
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
    result = {{}}
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
# {{'tongue_color': ['红'], 'coating_color': ['黄苔'], ...}}
```

## 注意事项

1. **证型类别不参与分类训练**: 类别ID 13-20（证型标签）仅用于云端LLM诊断的few-shot示例，不包含在分类模型的输出中。

2. **多标签处理**: 单张图像可能包含多个标签，使用one-hot编码时需要注意多个类别可以同时为1。

3. **健康舌特殊处理**: 当图像仅标注为"jiankangshe"（健康舌）时，所有特征维度为0，健康标记为1。

4. **类别权重**: 由于原始数据集存在严重的类别不平衡，建议使用计算得到的类别权重进行训练。

## 生成信息

- 生成时间: {self._get_current_time()}
- 数据集版本: shezhenv3-coco
- 脚本版本: v1.0
"""

        return doc

    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== Main Function ====================

def main():
    parser = argparse.ArgumentParser(
        description="多标签编码映射脚本（21类→6维度18类）",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--data_root",
        type=str,
        default="shezhenv3-coco",
        help="COCO数据集根目录"
    )

    parser.add_argument(
        "--output_base",
        type=str,
        default=None,
        help="输出基础目录 (默认: datasets/processed/clas_v1)"
    )

    parser.add_argument(
        "--split",
        type=str,
        choices=["train", "val", "test"],
        default=None,
        help="处理单个数据集划分"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="处理所有数据集划分 (train/val/test)"
    )

    parser.add_argument(
        "--report_only",
        action="store_true",
        help="仅生成报告（不重新处理标签）"
    )

    args = parser.parse_args()

    # Initialize converter
    converter = ClassMappingConverter(args.data_root, args.output_base)

    # Process splits
    if not args.report_only:
        splits_to_process = ["train", "val", "test"] if args.all else ([args.split] if args.split else [])
        results = []

        for split in splits_to_process:
            result = converter.process_split(split)
            if result:
                results.append(result)
                logger.info(f"Split {split}: {result}")

    # Save reports
    report_files = converter.save_reports()
    logger.info(f"Generated reports: {report_files}")

    # Print summary
    logger.info("=" * 60)
    logger.info("Processing Summary:")
    logger.info(f"  Total images processed: {converter.stats['total_images']}")
    logger.info(f"  Multi-label images: {converter.stats['multi_label_count']}")
    logger.info(f"  Healthy tongue samples: {converter.stats['healthy_tongue_count']}")
    logger.info(f"  Empty labels: {len(converter.stats['empty_labels'])}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
