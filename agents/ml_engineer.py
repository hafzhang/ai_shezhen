#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML Engineer Agent - AI舌诊智能诊断系统

Role: 专注于医学图像AI的机器学习工程师
Responsibilities:
    - 数据集分析与预处理
    - PaddleSeg分割模型训练
    - PaddleClas分类模型训练
    - 类别不平衡专项处理
    - 模型量化与部署优化

Author: ML Engineer Agent
Date: 2026-02-11
"""

import os
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns

# PaddlePaddle imports
import paddle
import paddle.nn as nn
from paddle.io import Dataset, DataLoader, Sampler
from paddle.vision.transforms import Compose

# COCO API
from pycocotools.coco import COCO
from pycocotools import mask as coco_mask

# MLflow for experiment tracking
import mlflow
import mlflow.paddle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ml_engineer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class DatasetConfig:
    """数据集配置"""
    base_path: str = r"C:\Users\Administrator\Desktop\AI_shezhen\shezhenv3-coco"
    train_annotations: str = "train/annotations/train.json"
    val_annotations: str = "val/annotations/val.json"
    test_annotations: str = "test/annotations/test.json"
    image_size: Tuple[int, int] = (512, 512)
    num_classes: int = 21


@dataclass
class TrainingConfig:
    """训练配置"""
    # 基础参数
    batch_size: int = 16
    num_epochs: int = 80
    learning_rate: float = 0.01
    momentum: float = 0.9
    weight_decay: float = 5e-4

    # 学习率调度
    warmup_epochs: int = 2
    lr_power: float = 0.9

    # Early Stopping
    early_stopping_patience: int = 10
    min_delta: float = 1e-4

    # 设备
    device: str = "gpu" if paddle.is_compiled_with_cuda() else "cpu"
    num_workers: int = 4
    use_amp: bool = True  # 混合精度训练

    # 检查点
    checkpoint_dir: str = "checkpoints"
    save_freq: int = 5  # 每N个epoch保存一次


@dataclass
class SegmentationConfig:
    """分割模型配置 (PaddleSeg - BiSeNetV2)"""
    model_name: str = "BiSeNetV2"
    backbone: str = "STDCNet2"
    pretrained: str = "CITYSCAPES"

    # 输入输出
    in_channels: int = 3
    num_classes: int = 2  # tongue / background

    # 损失函数权重
    loss_weights: Dict[str, float] = field(default_factory=lambda: {
        "ce_loss": 0.5,
        "dice_loss": 0.3,
        "boundary_loss": 0.2
    })

    # 评估指标目标
    target_miou: float = 0.92
    target_dice: float = 0.95
    target_inference_time: float = 33  # ms (CPU)


@dataclass
class ClassificationConfig:
    """分类模型配置 (PaddleClas - PP-HGNetV2-B4)"""
    model_name: str = "PP-HGNetV2_B4"
    pretrained: str = "ImageNet22k"

    # 多标签分类头配置
    num_heads: int = 6  # 6个维度
    head_config: Dict[str, Any] = field(default_factory=lambda: {
        "tongue_color": {"num_classes": 4, "names": ["pale", "light_red", "red", "purple"]},
        "coating_color": {"num_classes": 4, "names": ["white", "yellow", "black", "peeling"]},
        "tongue_shape": {"num_classes": 3, "names": ["normal", "swollen", "thin"]},
        "coating_quality": {"num_classes": 3, "names": ["thin", "thick", "greasy"]},
        "features": {"num_classes": 3, "names": ["red_dots", "cracks", "teeth_marks"]},
        "health": {"num_classes": 1, "names": ["healthy"]}
    })

    # 损失函数
    use_focal_loss: bool = True
    focal_alpha: float = 0.25
    focal_gamma: float = 2.0
    use_asymmetric_loss: bool = True
    class_weights: str = "sqrt_inv"  # "sqrt_inv" / "inv" / None

    # 采样策略
    sampling_strategy: str = "stratified"  # "stratified" / "balance" / "oversample"
    majority_ratio: float = 0.8  # 多数类保留比例
    target_imbalance_ratio: float = 10.0  # 目标类别比例

    # 评估指标目标
    target_macro_f1: float = 0.65
    target_map: float = 0.70
    target_minority_recall: float = 0.60


class MLEngineerAgent:
    """
    ML Engineer Agent - 机器学习工程师代理

    负责舌诊AI模型的完整开发流程，包括数据处理、模型训练、
    类别不平衡处理和性能优化。
    """

    def __init__(
        self,
        dataset_config: DatasetConfig,
        training_config: TrainingConfig,
        seg_config: SegmentationConfig,
        cls_config: ClassificationConfig
    ):
        self.dataset_config = dataset_config
        self.training_config = training_config
        self.seg_config = seg_config
        self.cls_config = cls_config

        # 创建必要目录
        self._create_directories()

        # 初始化MLflow
        self._init_mlflow()

        # 数据集统计信息缓存
        self.dataset_stats = {}

        logger.info("ML Engineer Agent initialized successfully")

    def _create_directories(self):
        """创建必要的目录结构"""
        dirs = [
            "experiments",
            "checkpoints/segmentation",
            "checkpoints/classification",
            "logs",
            "outputs/visualizations",
            "outputs/reports"
        ]

        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def _init_mlflow(self):
        """初始化MLflow实验跟踪"""
        mlflow.set_tracking_uri("file:///C:/Users/Administrator/Desktop/AI_shezhen/mlruns")
        mlflow.set_experiment("shezhen_diagnosis_system")
        logger.info("MLflow tracking initialized")

    # ==================== 数据分析模块 ====================

    def analyze_dataset(self, split: str = "train") -> Dict[str, Any]:
        """
        分析数据集统计信息

        Args:
            split: 数据集划分 ("train", "val", "test")

        Returns:
            包含统计信息的字典
        """
        logger.info(f"Analyzing {split} dataset...")

        # 加载COCO标注
        if split == "train":
            ann_file = os.path.join(self.dataset_config.base_path,
                                    self.dataset_config.train_annotations)
        elif split == "val":
            ann_file = os.path.join(self.dataset_config.base_path,
                                    self.dataset_config.val_annotations)
        else:
            ann_file = os.path.join(self.dataset_config.base_path,
                                    self.dataset_config.test_annotations)

        coco = COCO(ann_file)

        # 基础统计
        stats = {
            "split": split,
            "num_images": len(coco.imgs),
            "num_annotations": len(coco.anns),
            "num_categories": len(coco.cats),
            "categories": {cat["id"]: cat["name"] for cat in coco.cats.values()}
        }

        # 类别分布统计
        cat_ids = [ann["category_id"] for ann in coco.anns.values()]
        cat_counter = Counter(cat_ids)

        stats["category_distribution"] = {}
        for cat_id, count in cat_counter.most_common():
            cat_name = stats["categories"][cat_id]
            percentage = count / stats["num_images"] * 100
            stats["category_distribution"][cat_name] = {
                "count": count,
                "percentage": percentage
            }

        # 多标签统计
        img_id_to_cats = defaultdict(set)
        for ann in coco.anns.values():
            img_id_to_cats[ann["image_id"]].add(ann["category_id"])

        labels_per_image = [len(cats) for cats in img_id_to_cats.values()]
        stats.update({
            "avg_labels_per_image": np.mean(labels_per_image),
            "max_labels_per_image": max(labels_per_image),
            "min_labels_per_image": min(labels_per_image)
        })

        # 类别不平衡分析
        counts = list(cat_counter.values())
        imbalance_ratio = max(counts) / min(counts)
        stats["imbalance_ratio"] = imbalance_ratio

        # 识别少数类
        median_count = np.median(counts)
        stats["minority_classes"] = [
            stats["categories"][cid] for cid, cnt in cat_counter.items()
            if cnt < median_count * 0.5
        ]

        # 缓存统计信息
        self.dataset_stats[split] = stats

        # 记录到MLflow
        with mlflow.start_run(run_name=f"dataset_analysis_{split}"):
            mlflow.log_params({
                f"{split}_num_images": stats["num_images"],
                f"{split}_num_annotations": stats["num_annotations"],
                f"{split}_avg_labels": stats["avg_labels_per_image"],
                f"{split}_imbalance_ratio": imbalance_ratio
            })

        logger.info(f"Dataset analysis complete: {stats['num_images']} images, "
                   f"{stats['avg_labels_per_image']:.2f} avg labels, "
                   f"imbalance ratio: {imbalance_ratio:.2f}")

        return stats

    def visualize_dataset(self, split: str = "train", save_dir: str = "outputs/visualizations"):
        """
        生成数据集可视化报告

        Args:
            split: 数据集划分
            save_dir: 保存目录
        """
        logger.info(f"Generating visualizations for {split} dataset...")

        stats = self.dataset_stats.get(split)
        if not stats:
            stats = self.analyze_dataset(split)

        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # 1. 类别分布柱状图
        cat_names = list(stats["category_distribution"].keys())
        cat_counts = [stats["category_distribution"][name]["count"] for name in cat_names]

        axes[0, 0].barh(cat_names, cat_counts)
        axes[0, 0].set_xlabel("Count")
        axes[0, 0].set_title("Category Distribution")
        axes[0, 0].set_xscale("log")

        # 2. 类别占比饼图
        axes[0, 1].pie(cat_counts, labels=cat_names, autopct='%1.1f%%')
        axes[0, 1].set_title("Category Percentage")

        # 3. 标签数量分布
        # 这里需要重新计算
        ann_file = os.path.join(self.dataset_config.base_path,
                               self.dataset_config.train_annotations if split == "train" else
                               self.dataset_config.val_annotations if split == "val" else
                               self.dataset_config.test_annotations)
        coco = COCO(ann_file)
        img_id_to_cats = defaultdict(set)
        for ann in coco.anns.values():
            img_id_to_cats[ann["image_id"]].add(ann["category_id"])
        labels_per_image = [len(cats) for cats in img_id_to_cats.values()]

        axes[1, 0].hist(labels_per_image, bins=range(1, max(labels_per_image)+2),
                        edgecolor='black', alpha=0.7)
        axes[1, 0].set_xlabel("Number of Labels per Image")
        axes[1, 0].set_ylabel("Frequency")
        axes[1, 0].set_title("Multi-label Distribution")

        # 4. 不平衡分析
        sorted_counts = sorted(cat_counts, reverse=True)
        axes[1, 1].plot(range(1, len(sorted_counts)+1), sorted_counts,
                        marker='o', linestyle='--')
        axes[1, 1].set_xlabel("Rank")
        axes[1, 1].set_ylabel("Count")
        axes[1, 1].set_title("Class Imbalance Analysis")
        axes[1, 1].set_yscale("log")
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        save_path = os.path.join(save_dir, f"{split}_dataset_analysis.png")
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Visualizations saved to {save_path}")

    def generate_report(self, split: str = "train") -> str:
        """
        生成数据分析报告

        Args:
            split: 数据集划分

        Returns:
            报告内容
        """
        stats = self.dataset_stats.get(split)
        if not stats:
            stats = self.analyze_dataset(split)

        report = f"""
# 数据集分析报告 - {split.upper()}

## 基础信息
- 图像数量: {stats['num_images']:,}
- 标注数量: {stats['num_annotations']:,}
- 类别数量: {stats['num_categories']}
- 平均标签/图: {stats['avg_labels_per_image']:.2f}
- 类别不平衡比: {stats['imbalance_ratio']:.2f}:1

## 类别分布详情
"""
        # 按数量排序
        sorted_cats = sorted(
            stats["category_distribution"].items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )

        for i, (cat_name, info) in enumerate(sorted_cats, 1):
            indicator = "⚠️" if i <= 3 else ""
            report += f"{i}. {cat_name}: {info['count']} ({info['percentage']:.1f}%) {indicator}\n"

        report += f"\n## 少数类识别\n"
        report += f"以下类别需要特别关注: {', '.join(stats['minority_classes'])}\n"

        report += f"\n## 建议措施\n"
        if stats['imbalance_ratio'] > 50:
            report += "- 严重不平衡，建议使用Focal Loss + 分层采样\n"
            report += "- 对少数类进行数据增强\n"
        elif stats['imbalance_ratio'] > 20:
            report += "- 中度不平衡，建议使用类别加权 + 混合采样\n"
        else:
            report += "- 轻度不平衡，使用基础采样策略即可\n"

        # 保存报告
        report_path = f"outputs/reports/{split}_analysis_report.md"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"Report saved to {report_path}")

        return report

    # ==================== 数据处理模块 ====================

    def polygon_to_mask(self, segmentation: List[float],
                       image_size: Tuple[int, int]) -> np.ndarray:
        """
        将COCO polygon标注转换为二进制mask

        Args:
            segmentation: COCO格式polygon
            image_size: (height, width)

        Returns:
            二进制mask数组
        """
        rle = coco_mask.frPyObjects(segmentation, image_size[0], image_size[1])
        mask = coco_mask.decode(rle)
        return mask

    def calculate_class_weights(self, split: str = "train") -> np.ndarray:
        """
        计算类别权重

        使用 sqrt_inv 策略: weight_i = 1 / sqrt(count_i)

        Args:
            split: 数据集划分

        Returns:
            类别权重数组
        """
        stats = self.dataset_stats.get(split)
        if not stats:
            stats = self.analyze_dataset(split)

        # 获取类别计数
        cat_counts = {
            cat_id: sum(1 for ann in stats.get("annotations", [])
                       if ann["category_id"] == cat_id)
            for cat_id in range(len(stats["categories"]))
        }

        # 计算权重
        weights = np.array([
            1 / np.sqrt(cnt) if cnt > 0 else 0
            for cnt in cat_counts.values()
        ])

        # 归一化
        weights = weights / weights.sum() * len(weights)

        logger.info(f"Class weights calculated: min={weights.min():.4f}, "
                   f"max={weights.max():.4f}, ratio={weights.max()/weights.min():.2f}")

        return weights


def main():
    """主函数 - 命令行接口"""
    parser = argparse.ArgumentParser(description="ML Engineer Agent - AI舌诊系统")
    parser.add_argument("--command", type=str, required=True,
                       choices=["analyze", "visualize", "report", "train-seg", "train-cls"],
                       help="执行命令")
    parser.add_argument("--split", type=str, default="train",
                       choices=["train", "val", "test"],
                       help="数据集划分")

    args = parser.parse_args()

    # 初始化配置
    dataset_config = DatasetConfig()
    training_config = TrainingConfig()
    seg_config = SegmentationConfig()
    cls_config = ClassificationConfig()

    # 初始化代理
    agent = MLEngineerAgent(dataset_config, training_config, seg_config, cls_config)

    # 执行命令
    if args.command == "analyze":
        stats = agent.analyze_dataset(args.split)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif args.command == "visualize":
        agent.visualize_dataset(args.split)

    elif args.command == "report":
        report = agent.generate_report(args.split)
        print(report)

    elif args.command == "train-seg":
        logger.info("Segmentation training - to be implemented")

    elif args.command == "train-cls":
        logger.info("Classification training - to be implemented")


if __name__ == "__main__":
    main()
