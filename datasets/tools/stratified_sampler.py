#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分层采样器（Stratified Sampler）

实现多标签分类任务的分层采样，确保每个batch包含多数类和少数类的平衡样本。
支持类别权重计算、批次内类别平衡、难例采样等功能。

Features:
- 自动计算类别权重（weight_i = total / (num_classes × count_i)）
- 按类别分层的批次采样（50%多数类 + 50%少数类）
- 支持多标签数据的采样策略
- 可配置的采样比例和批次大小

Usage:
    from datasets.tools.stratified_sampler import StratifiedSampler, ClassWeights

    # Calculate class weights
    weights_calculator = ClassWeights(labels_file='datasets/processed/clas_v1/train/labels.txt')
    class_weights = weights_calculator.calculate()

    # Create stratified sampler for DataLoader
    sampler = StratifiedSampler(
        labels_file='datasets/processed/clas_v1/train/labels.txt',
        batch_size=32,
        majority_ratio=0.5
    )
    train_loader = DataLoader(dataset, batch_sampler=sampler, ...)
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Iterator
from collections import defaultdict
import random
import numpy as np

import torch
from torch.utils.data import Sampler, Dataset
from torch.utils.data.sampler import BatchSampler

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


# ==================== Dimension Indices ====================

# Dimension indices in flattened vector (consistent with class_mapping.py)
DIMENSION_INDICES = {
    "tongue_color": (0, 4),
    "coating_color": (4, 8),
    "tongue_shape": (8, 11),
    "coating_quality": (11, 14),
    "features": (14, 17),
    "health": (17, 19)
}

DIMENSION_CATEGORIES = {
    "tongue_color": ["淡白", "淡红", "红", "绛紫"],
    "coating_color": ["白苔", "黄苔", "黑苔", "花剥苔"],
    "tongue_shape": ["正常", "胖大", "瘦薄"],
    "coating_quality": ["薄苔", "厚苔", "腻苔"],
    "features": ["红点", "裂纹", "齿痕"],
    "health": ["非健康舌", "健康舌"]
}

# Total feature categories (excluding health flag which is at index 18)
TOTAL_FEATURE_CATEGORIES = 18


# ==================== Class Weights Calculator ====================

class ClassWeights:
    """
    类别权重计算器

    计算用于处理类别不平衡的权重，使用公式:
    weight_i = total_samples / (num_classes × count_i)

    Attributes:
        labels_file: 标签文件路径
        labels: 标签向量列表
        filename_to_idx: 文件名到索引的映射
    """

    def __init__(self, labels_file: str):
        """
        初始化权重计算器

        Args:
            labels_file: 标签文件路径 (格式: filename<TAB>label1,label2,...)
        """
        self.labels_file = Path(labels_file)
        self.labels: List[np.ndarray] = []
        self.filename_to_idx: Dict[str, int] = {}

        self._load_labels()

    def _load_labels(self) -> None:
        """加载标签文件"""
        if not self.labels_file.exists():
            raise FileNotFoundError(f"Labels file not found: {self.labels_file}")

        logger.info(f"Loading labels from {self.labels_file}")

        with open(self.labels_file, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) < 2:
                    continue

                filename = parts[0]
                label_str = parts[1]

                # Parse label vector
                label_vector = np.array([int(x) for x in label_str.split(',')], dtype=np.int8)

                self.labels.append(label_vector)
                self.filename_to_idx[filename] = idx

        logger.info(f"Loaded {len(self.labels)} labels")

    def calculate(self, method: str = "balanced") -> Dict[str, float]:
        """
        计算类别权重

        Args:
            method: 权重计算方法
                - "balanced": weight_i = total / (num_classes × count_i)
                - "sqrt": weight_i = sqrt(total / count_i)
                - "log": weight_i = log(total / count_i) + 1

        Returns:
            类别权重字典 {dim_name_cat_idx: weight}
        """
        if not self.labels:
            raise ValueError("No labels loaded. Call _load_labels() first.")

        weights = {}
        total_samples = len(self.labels)

        # Calculate weights for each dimension's categories
        for dim_name, (start, end) in DIMENSION_INDICES.items():
            if dim_name == "health":
                continue  # Skip health flag for now

            dim_size = end - start
            dim_counts = np.zeros(dim_size, dtype=np.int64)

            # Count occurrences of each category
            for label in self.labels:
                dim_vector = label[start:end]
                # For multi-label, count all positive labels
                for i in range(dim_size):
                    if dim_vector[i] == 1:
                        dim_counts[i] += 1

            # Calculate weights based on method
            for i, count in enumerate(dim_counts):
                key = f"{dim_name}_{i}"

                if count == 0:
                    # Handle unseen classes
                    if method == "balanced":
                        weight = 10.0  # High weight for unseen
                    elif method == "sqrt":
                        weight = 5.0
                    else:  # log
                        weight = 3.0
                else:
                    if method == "balanced":
                        weight = total_samples / (dim_size * count)
                    elif method == "sqrt":
                        weight = np.sqrt(total_samples / count)
                    else:  # log
                        weight = np.log(total_samples / count) + 1

                weights[key] = round(float(weight), 4)

        logger.info(f"Calculated {len(weights)} class weights using '{method}' method")
        return weights

    def get_category_counts(self) -> Dict[str, int]:
        """
        获取每个类别的样本数量

        Returns:
            类别计数字典 {dim_name_cat_idx: count}
        """
        counts = {}

        for dim_name, (start, end) in DIMENSION_INDICES.items():
            if dim_name == "health":
                continue

            dim_size = end - start
            dim_counts = np.zeros(dim_size, dtype=np.int64)

            for label in self.labels:
                dim_vector = label[start:end]
                for i in range(dim_size):
                    if dim_vector[i] == 1:
                        dim_counts[i] += 1

            for i, count in enumerate(dim_counts):
                counts[f"{dim_name}_{i}"] = int(count)

        return counts

    def save_weights(self, output_file: str, method: str = "balanced") -> None:
        """
        保存类别权重到JSON文件

        Args:
            output_file: 输出文件路径
            method: 权重计算方法
        """
        weights = self.calculate(method=method)
        counts = self.get_category_counts()

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        weights_data = {
            "method": method,
            "total_samples": len(self.labels),
            "dimension_sizes": {
                dim_name: end - start
                for dim_name, (start, end) in DIMENSION_INDICES.items()
                if dim_name != "health"
            },
            "weights": weights,
            "counts": counts,
            "weight_formula": "weight_i = total / (num_classes × count_i)"
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(weights_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved class weights to {output_path}")

    def get_majority_minority_split(self, threshold: float = 0.1) -> Tuple[List[str], List[str]]:
        """
        识别多数类和少数类

        Args:
            threshold: 少数类阈值（低于总样本数×threshold的类别）

        Returns:
            (majority_classes, minority_classes) 元组
        """
        counts = self.get_category_counts()
        total = len(self.labels)
        threshold_count = total * threshold

        majority = []
        minority = []

        for class_name, count in counts.items():
            if count < threshold_count:
                minority.append(class_name)
            else:
                majority.append(class_name)

        logger.info(f"Majority classes: {len(majority)}, Minority classes: {len(minority)}")
        return majority, minority


# ==================== Stratified Batch Sampler ====================

class StratifiedBatchSampler(Sampler):
    """
    分层批次采样器

    确保每个batch包含多数类和少数类的平衡样本。
    对于多标签数据，根据主标签进行分层。

    Attributes:
        labels_file: 标签文件路径
        batch_size: 批次大小
        majority_ratio: 多数类在batch中的比例 (0-1)
        drop_last: 是否丢弃最后不完整的batch
        shuffle: 是否打乱数据
    """

    def __init__(
        self,
        labels_file: str,
        batch_size: int = 32,
        majority_ratio: float = 0.5,
        drop_last: bool = False,
        shuffle: bool = True
    ):
        """
        初始化分层采样器

        Args:
            labels_file: 标签文件路径
            batch_size: 批次大小
            majority_ratio: 多数类在batch中的比例 (默认0.5即50%)
            drop_last: 是否丢弃最后不完整的batch
            shuffle: 是否在每个epoch开始时打乱数据
        """
        self.labels_file = Path(labels_file)
        self.batch_size = batch_size
        self.majority_ratio = majority_ratio
        self.drop_last = drop_last
        self.shuffle = shuffle

        # Load labels
        self.labels: List[np.ndarray] = []
        self.filenames: List[str] = []
        self._load_labels()

        # Organize samples by dominant class
        self.class_indices: Dict[str, List[int]] = defaultdict(list)
        self._organize_by_class()

        # Split into majority and minority classes
        self.majority_classes: List[str] = []
        self.minority_classes: List[str] = []
        self._split_classes()

        # Calculate batch composition
        self.majority_per_batch = int(batch_size * majority_ratio)
        self.minority_per_batch = batch_size - self.majority_per_batch

        # Generate batches
        self.batches: List[List[int]] = []
        self._generate_batches()

    def _load_labels(self) -> None:
        """加载标签文件"""
        logger.info(f"Loading labels from {self.labels_file}")

        with open(self.labels_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) < 2:
                    continue

                filename = parts[0]
                label_str = parts[1]
                label_vector = np.array([int(x) for x in label_str.split(',')], dtype=np.int8)

                self.filenames.append(filename)
                self.labels.append(label_vector)

        logger.info(f"Loaded {len(self.labels)} labels")

    def _organize_by_class(self) -> None:
        """根据主标签组织样本索引"""
        for idx, label in enumerate(self.labels):
            # Find the dominant class (first positive label in feature dimensions)
            dominant_class = None

            for dim_name, (start, end) in DIMENSION_INDICES.items():
                if dim_name == "health":
                    continue

                dim_vector = label[start:end]
                positive_indices = np.where(dim_vector == 1)[0]

                if len(positive_indices) > 0:
                    dominant_class = f"{dim_name}_{positive_indices[0]}"
                    break

            # If no feature label, assign to "healthy" or "unlabeled"
            if dominant_class is None:
                if label[18] == 1:  # Health flag
                    dominant_class = "healthy"
                else:
                    dominant_class = "unlabeled"

            self.class_indices[dominant_class].append(idx)

        logger.info(f"Organized {len(self.labels)} samples into {len(self.class_indices)} classes")

    def _split_classes(self, threshold: float = 0.1) -> None:
        """
        分割多数类和少数类

        Args:
            threshold: 少数类阈值（低于总样本数×threshold的类别）
        """
        total = len(self.labels)
        threshold_count = total * threshold

        class_counts = {
            class_name: len(indices)
            for class_name, indices in self.class_indices.items()
        }

        for class_name, count in class_counts.items():
            if count < threshold_count:
                self.minority_classes.append(class_name)
            else:
                self.majority_classes.append(class_name)

        logger.info(f"Majority classes ({len(self.majority_classes)}): {self.majority_classes}")
        logger.info(f"Minority classes ({len(self.minority_classes)}): {self.minority_classes}")

    def _sample_majority(self) -> List[int]:
        """从多数类中采样"""
        samples = []

        # Flatten majority class indices
        majority_indices = []
        for class_name in self.majority_classes:
            majority_indices.extend(self.class_indices[class_name])

        # Handle case with no majority classes
        if len(majority_indices) == 0:
            # Fill with random samples from all classes
            all_indices = list(range(len(self.labels)))
            if self.majority_per_batch > 0:
                return random.sample(all_indices, min(len(all_indices), self.majority_per_batch))
            return samples

        if len(majority_indices) >= self.majority_per_batch:
            samples = random.sample(majority_indices, self.majority_per_batch)
        else:
            # Not enough majority samples, use all and repeat
            samples = majority_indices.copy()
            while len(samples) < self.majority_per_batch:
                n_needed = self.majority_per_batch - len(samples)
                n_sample = min(len(majority_indices), n_needed)
                additional = random.sample(majority_indices, n_sample)
                samples.extend(additional)
            samples = samples[:self.majority_per_batch]

        return samples

    def _sample_minority(self) -> List[int]:
        """从少数类中采样（过采样）"""
        samples = []

        # Get minority class indices
        minority_indices = []
        for class_name in self.minority_classes:
            minority_indices.extend(self.class_indices[class_name])

        # Handle case with no minority classes
        if len(minority_indices) == 0:
            # Fill with random samples from all classes
            all_indices = list(range(len(self.labels)))
            if self.minority_per_batch > 0:
                return random.sample(all_indices, min(len(all_indices), self.minority_per_batch))
            return samples

        if len(minority_indices) >= self.minority_per_batch:
            samples = random.sample(minority_indices, self.minority_per_batch)
        else:
            # Oversample minority classes
            samples = minority_indices.copy()
            while len(samples) < self.minority_per_batch:
                n_needed = self.minority_per_batch - len(samples)
                n_sample = min(len(minority_indices), n_needed)
                additional = random.sample(minority_indices, n_sample)
                samples.extend(additional)
            samples = samples[:self.minority_per_batch]

        return samples

    def _generate_batches(self) -> None:
        """生成批次索引"""
        num_samples = len(self.labels)

        # Calculate total number of batches
        if self.drop_last:
            num_batches = num_samples // self.batch_size
        else:
            num_batches = (num_samples + self.batch_size - 1) // self.batch_size

        for _ in range(num_batches):
            # Sample from majority and minority classes
            majority_samples = self._sample_majority()
            minority_samples = self._sample_minority()

            # Combine and shuffle within batch
            batch_samples = majority_samples + minority_samples
            random.shuffle(batch_samples)

            self.batches.append(batch_samples)

        logger.info(f"Generated {len(self.batches)} batches")

    def __iter__(self) -> Iterator[List[int]]:
        """返回批次迭代器"""
        if self.shuffle:
            random.shuffle(self.batches)

        for batch in self.batches:
            yield batch

    def __len__(self) -> int:
        """返回批次数"""
        return len(self.batches)

    def get_batch_statistics(self) -> Dict[str, any]:
        """
        获取批次统计信息

        Returns:
            批次统计字典
        """
        return {
            "total_batches": len(self.batches),
            "batch_size": self.batch_size,
            "majority_ratio": self.majority_ratio,
            "majority_per_batch": self.majority_per_batch,
            "minority_per_batch": self.minority_per_batch,
            "majority_classes": self.majority_classes,
            "minority_classes": self.minority_classes,
            "class_distribution": {
                class_name: len(indices)
                for class_name, indices in self.class_indices.items()
            }
        }


# ==================== PyTorch Dataset Wrapper ====================

class StratifiedSampler:
    """
    分层采样器包装类

    提供便捷的接口用于创建PyTorch DataLoader兼容的采样器。

    Usage:
        sampler = StratifiedSampler(
            labels_file='datasets/processed/clas_v1/train/labels.txt',
            batch_size=32
        )
        train_loader = torch.utils.data.DataLoader(
            dataset,
            batch_sampler=sampler.get_batch_sampler(),
            ...
        )
    """

    def __init__(
        self,
        labels_file: str,
        batch_size: int = 32,
        majority_ratio: float = 0.5,
        drop_last: bool = False,
        shuffle: bool = True
    ):
        """
        初始化分层采样器

        Args:
            labels_file: 标签文件路径
            batch_size: 批次大小
            majority_ratio: 多数类在batch中的比例 (默认0.5即50%)
            drop_last: 是否丢弃最后不完整的batch
            shuffle: 是否在每个epoch开始时打乱数据
        """
        self.labels_file = labels_file
        self.batch_size = batch_size
        self.majority_ratio = majority_ratio
        self.drop_last = drop_last
        self.shuffle = shuffle

        # Initialize batch sampler
        self.batch_sampler = StratifiedBatchSampler(
            labels_file=labels_file,
            batch_size=batch_size,
            majority_ratio=majority_ratio,
            drop_last=drop_last,
            shuffle=shuffle
        )

    def get_batch_sampler(self) -> StratifiedBatchSampler:
        """获取PyTorch BatchSampler实例"""
        return self.batch_sampler

    def get_class_weights(self, method: str = "balanced") -> Dict[str, float]:
        """
        获取类别权重

        Args:
            method: 权重计算方法

        Returns:
            类别权重字典
        """
        weights_calculator = ClassWeights(self.labels_file)
        return weights_calculator.calculate(method=method)

    def save_class_weights(self, output_file: str, method: str = "balanced") -> None:
        """
        保存类别权重到文件

        Args:
            output_file: 输出文件路径
            method: 权重计算方法
        """
        weights_calculator = ClassWeights(self.labels_file)
        weights_calculator.save_weights(output_file, method=method)

    def get_statistics(self) -> Dict[str, any]:
        """获取采样器统计信息"""
        return self.batch_sampler.get_batch_statistics()


# ==================== Main Function ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="分层采样器工具 - 计算类别权重并创建平衡批次",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--labels_file",
        type=str,
        default="datasets/processed/clas_v1/train/labels.txt",
        help="标签文件路径"
    )

    parser.add_argument(
        "--output_weights",
        type=str,
        default="datasets/processed/clas_v1/sampler_class_weights.json",
        help="类别权重输出文件"
    )

    parser.add_argument(
        "--batch_size",
        type=int,
        default=32,
        help="批次大小"
    )

    parser.add_argument(
        "--majority_ratio",
        type=float,
        default=0.5,
        help="多数类在batch中的比例 (0-1)"
    )

    parser.add_argument(
        "--method",
        type=str,
        choices=["balanced", "sqrt", "log"],
        default="balanced",
        help="权重计算方法"
    )

    parser.add_argument(
        "--visualize",
        action="store_true",
        help="可视化类别分布和采样效果"
    )

    args = parser.parse_args()

    # Calculate and save class weights
    logger.info("=" * 60)
    logger.info("Stratified Sampler - Class Weights Calculator")
    logger.info("=" * 60)

    weights_calc = ClassWeights(args.labels_file)

    # Calculate weights
    weights = weights_calc.calculate(method=args.method)
    logger.info(f"\nCalculated {len(weights)} class weights using '{args.method}' method")

    # Get category counts
    counts = weights_calc.get_category_counts()

    # Print summary
    logger.info("\n--- Category Counts and Weights ---")
    for dim_name, (start, end) in DIMENSION_INDICES.items():
        if dim_name == "health":
            continue

        dim_size = end - start
        categories = DIMENSION_CATEGORIES[dim_name]

        logger.info(f"\n{dim_name} ({DIMENSION_INDICES[dim_name][0]}:{DIMENSION_INDICES[dim_name][1]}):")

        for i in range(dim_size):
            key = f"{dim_name}_{i}"
            count = counts.get(key, 0)
            weight = weights.get(key, 0)
            percentage = (count / len(weights_calc.labels) * 100) if len(weights_calc.labels) > 0 else 0

            logger.info(f"  {categories[i]:8s} (idx={i}): count={count:5d}, weight={weight:7.4f}, {percentage:6.2f}%")

    # Get majority/minority split
    majority, minority = weights_calc.get_majority_minority_split()
    logger.info(f"\n--- Majority/Minority Split ---")
    logger.info(f"Majority classes ({len(majority)}): {', '.join(majority[:10])}{'...' if len(majority) > 10 else ''}")
    logger.info(f"Minority classes ({len(minority)}): {', '.join(minority[:10])}{'...' if len(minority) > 10 else ''}")

    # Save weights
    weights_calc.save_weights(args.output_weights, method=args.method)

    # Create stratified sampler
    logger.info(f"\n--- Creating Stratified Sampler ---")
    sampler = StratifiedSampler(
        labels_file=args.labels_file,
        batch_size=args.batch_size,
        majority_ratio=args.majority_ratio
    )

    stats = sampler.get_statistics()
    logger.info(f"Total batches: {stats['total_batches']}")
    logger.info(f"Batch size: {stats['batch_size']}")
    logger.info(f"Majority per batch: {stats['majority_per_batch']}")
    logger.info(f"Minority per batch: {stats['minority_per_batch']}")

    # Visualization
    if args.visualize:
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')

            # Set font for Chinese characters
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False

            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

            # 1. Category counts bar chart
            ax1 = axes[0, 0]
            categories = []
            values = []
            colors = []

            for dim_name, (start, end) in DIMENSION_INDICES.items():
                if dim_name == "health":
                    continue
                for i in range(end - start):
                    key = f"{dim_name}_{i}"
                    categories.append(key)
                    values.append(counts.get(key, 0))
                    # Color by dimension
                    color_map = {
                        "tongue_color": "#FF6B6B",
                        "coating_color": "#4ECDC4",
                        "tongue_shape": "#45B7D1",
                        "coating_quality": "#FFA07A",
                        "features": "#98D8C8"
                    }
                    colors.append(color_map.get(dim_name, "#CCCCCC"))

            ax1.bar(range(len(categories)), values, color=colors)
            ax1.set_xticks(range(len(categories)))
            ax1.set_xticklabels(categories, rotation=45, ha='right', fontsize=8)
            ax1.set_ylabel('Sample Count')
            ax1.set_title('Category Distribution')
            ax1.grid(axis='y', alpha=0.3)

            # 2. Category weights bar chart
            ax2 = axes[0, 1]
            weight_values = [weights.get(cat, 0) for cat in categories]
            ax2.bar(range(len(categories)), weight_values, color=colors)
            ax2.set_xticks(range(len(categories)))
            ax2.set_xticklabels(categories, rotation=45, ha='right', fontsize=8)
            ax2.set_ylabel('Weight')
            ax2.set_title('Class Weights')
            ax2.grid(axis='y', alpha=0.3)

            # 3. Pie chart of majority vs minority
            ax3 = axes[1, 0]
            majority_count = sum(len(weights_calc.class_indices.get(c, [])) for c in majority)
            minority_count = sum(len(weights_calc.class_indices.get(c, [])) for c in minority)
            ax3.pie([majority_count, minority_count], labels=['Majority', 'Minority'], autopct='%1.1f%%', colors=['#4ECDC4', '#FF6B6B'])
            ax3.set_title('Majority vs Minority Sample Distribution')

            # 4. Log-scale distribution
            ax4 = axes[1, 1]
            sorted_values = sorted(values, reverse=True)
            ax4.plot(range(len(sorted_values)), sorted_values, marker='o', color='#FF6B6B')
            ax4.set_yscale('log')
            ax4.set_xlabel('Category Rank')
            ax4.set_ylabel('Sample Count (log scale)')
            ax4.set_title('Class Distribution (Log Scale)')
            ax4.grid(True, alpha=0.3)

            plt.tight_layout()

            # Save figure
            output_dir = Path(args.output_weights).parent
            fig_path = output_dir / "sampling_visualization.png"
            plt.savefig(fig_path, dpi=150, bbox_inches='tight')
            logger.info(f"\nSaved visualization to {fig_path}")

        except ImportError:
            logger.warning("matplotlib not available, skipping visualization")

    logger.info("\n" + "=" * 60)
    logger.info("Stratified Sampler setup complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
