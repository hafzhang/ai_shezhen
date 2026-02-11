#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据集分析脚本

快速分析shezhenv3-coco数据集的统计信息

Usage:
    python analyze_dataset.py --split train --visualize --report
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter, defaultdict
import numpy as np

from pycocotools.coco import COCO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_coco_dataset(ann_file: str) -> dict:
    """
    分析COCO格式数据集

    Args:
        ann_file: 标注文件路径

    Returns:
        统计信息字典
    """
    logger.info(f"Analyzing dataset: {ann_file}")

    # 加载COCO标注
    coco = COCO(ann_file)

    # 基础统计
    stats = {
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
        "avg_labels_per_image": float(np.mean(labels_per_image)),
        "max_labels_per_image": max(labels_per_image),
        "min_labels_per_image": min(labels_per_image)
    })

    # 类别不平衡分析
    counts = list(cat_counter.values())
    imbalance_ratio = max(counts) / min(counts) if min(counts) > 0 else float('inf')
    stats["imbalance_ratio"] = imbalance_ratio

    # 识别少数类
    median_count = np.median(counts)
    stats["minority_classes"] = [
        stats["categories"][cid] for cid, cnt in cat_counter.items()
        if cnt < median_count * 0.5
    ]

    # 识别多数类
    stats["majority_classes"] = [
        stats["categories"][cid] for cid, cnt in cat_counter.items()
        if cnt > median_count * 1.5
    ]

    return stats


def visualize_dataset(stats: dict, split: str, save_dir: str = "outputs/visualizations"):
    """
    可视化数据集统计

    Args:
        stats: 统计信息字典
        split: 数据集划分名称
        save_dir: 保存目录
    """
    logger.info(f"Generating visualizations for {split} dataset...")

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    # 创建图表
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. 类别分布柱状图
    cat_names = list(stats["category_distribution"].keys())
    cat_counts = [stats["category_distribution"][name]["count"] for name in cat_names]

    bars = axes[0, 0].barh(cat_names, cat_counts)
    axes[0, 0].set_xlabel("Count", fontsize=12)
    axes[0, 0].set_title("Category Distribution", fontsize=14, fontweight='bold')
    axes[0, 0].set_xscale("log")

    # 标注少数类
    for i, name in enumerate(cat_names):
        if name in stats.get("minority_classes", []):
            bars[i].set_color('red')

    # 2. 类别占比饼图（Top 10）
    top_10 = sorted(
        stats["category_distribution"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:10]

    pie_names = [item[0] for item in top_10]
    pie_counts = [item[1]["count"] for item in top_10]

    axes[0, 1].pie(pie_counts, labels=pie_names, autopct='%1.1f%%', startangle=90)
    axes[0, 1].set_title("Top 10 Categories by Percentage", fontsize=14, fontweight='bold')

    # 3. 标签数量分布
    # 这里需要重新计算，用简单的方式展示
    avg_labels = stats["avg_labels_per_image"]
    max_labels = stats["max_labels_per_image"]
    min_labels = stats["min_labels_per_image"]

    axes[1, 0].bar(["Avg", "Min", "Max"], [avg_labels, min_labels, max_labels],
                   color=['skyblue', 'lightgreen', 'salmon'])
    axes[1, 0].set_ylabel("Number of Labels", fontsize=12)
    axes[1, 0].set_title("Labels Per Image", fontsize=14, fontweight='bold')
    axes[1, 0].set_ylim(0, max_labels + 1)

    # 4. 不平衡分析
    sorted_counts = sorted(cat_counts, reverse=True)
    axes[1, 1].plot(range(1, len(sorted_counts)+1), sorted_counts,
                    marker='o', linestyle='--', linewidth=2, markersize=8)
    axes[1, 1].set_xlabel("Rank", fontsize=12)
    axes[1, 1].set_ylabel("Count", fontsize=12)
    axes[1, 1].set_title(f"Class Imbalance Analysis (Ratio: {stats['imbalance_ratio']:.1f}:1)",
                        fontsize=14, fontweight='bold')
    axes[1, 1].set_yscale("log")
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    save_path = f"{save_dir}/{split}_dataset_analysis.png"
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()

    logger.info(f"Visualizations saved to {save_path}")


def generate_report(stats: dict, split: str, save_dir: str = "outputs/reports") -> str:
    """
    生成数据集分析报告

    Args:
        stats: 统计信息字典
        split: 数据集划分名称
        save_dir: 保存目录

    Returns:
        报告内容
    """
    logger.info(f"Generating report for {split} dataset...")

    Path(save_dir).mkdir(parents=True, exist_ok=True)

    report = f"""# 数据集分析报告 - {split.upper()}

## 基础信息

| 指标 | 数值 |
|------|------|
| 图像数量 | {stats['num_images']:,} |
| 标注数量 | {stats['num_annotations']:,} |
| 类别数量 | {stats['num_categories']} |
| 平均标签/图 | {stats['avg_labels_per_image']:.2f} |
| 最大标签数 | {stats['max_labels_per_image']} |
| 最小标签数 | {stats['min_labels_per_image']} |
| 类别不平衡比 | {stats['imbalance_ratio']:.2f}:1 |

---

## 类别分布详情

| 排名 | 类别名称 | 样本数 | 占比 | 状态 |
|------|----------|--------|------|------|
"""

    # 按数量排序
    sorted_cats = sorted(
        stats["category_distribution"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    for i, (cat_name, info) in enumerate(sorted_cats, 1):
        count = info["count"]
        percentage = info["percentage"]

        # 判断状态
        if cat_name in stats.get("minority_classes", []):
            status = "⚠️ 少数类"
        elif cat_name in stats.get("majority_classes", []):
            status = "🔥 多数类"
        else:
            status = "✓ 正常"

        report += f"| {i} | {cat_name} | {count} | {percentage:.1f}% | {status} |\n"

    report += f"""

---

## 不平衡分析

### 少数类（需要特别关注）
{', '.join(stats.get('minority_classes', ['无']))}

### 多数类
{', '.join(stats.get('majority_classes', ['无']))}

---

## 建议措施

"""

    # 根据不平衡程度给出建议
    if stats['imbalance_ratio'] > 50:
        report += "### 严重不平衡 (Ratio > 50:1)\n\n"
        report += "**必须采取的措施：**\n"
        report += "1. 使用Focal Loss（α=0.25, γ=2）\n"
        report += "2. 实施分层采样策略\n"
        report += "3. 对少数类进行强数据增强\n"
        report += "4. 考虑类别重加权（weight = 1/√count）\n"
        report += "5. 使用难例挖掘\n\n"

    elif stats['imbalance_ratio'] > 20:
        report += "### 中度不平衡 (Ratio > 20:1)\n\n"
        report += "**建议措施：**\n"
        report += "1. 使用Focal Loss\n"
        report += "2. 混合采样策略（过采样+欠采样）\n"
        report += "3. 适度的数据增强\n\n"

    elif stats['imbalance_ratio'] > 10:
        report += "### 轻度不平衡 (Ratio > 10:1)\n\n"
        report += "**建议措施：**\n"
        report += "1. 类别加权损失\n"
        report += "2. 轻微的过采样\n\n"

    else:
        report += "### 基本均衡\n\n"
        report += "**建议：**\n"
        report += "使用标准训练策略即可\n\n"

    report += "---\n\n"
    report += "## 模型训练目标\n\n"
    report += "### 分割模型\n"
    report += "- 目标mIoU: >0.92\n"
    report += "- 目标Dice: >0.95\n"
    report += "- 推理时延: <33ms (CPU)\n\n"

    report += "### 分类模型\n"
    report += "- 目标宏平均F1: >0.65\n"
    report += "- 目标mAP: >0.70\n"
    report += "- 少数类召回率: >60%\n"

    # 保存报告
    report_path = f"{save_dir}/{split}_analysis_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"Report saved to {report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Analyze COCO dataset")
    parser.add_argument("--split", type=str, default="train",
                       choices=["train", "val", "test"],
                       help="Dataset split to analyze")
    parser.add_argument("--data_root", type=str,
                       default="C:/Users/Administrator/Desktop/AI_shezhen/shezhenv3-coco",
                       help="Root directory of the dataset")
    parser.add_argument("--visualize", action="store_true",
                       help="Generate visualizations")
    parser.add_argument("--report", action="store_true",
                       help="Generate report")

    args = parser.parse_args()

    # 构建标注文件路径
    ann_file = f"{args.data_root}/{args.split}/annotations/{args.split}.json"

    if not os.path.exists(ann_file):
        logger.error(f"Annotation file not found: {ann_file}")
        return

    # 分析数据集
    stats = analyze_coco_dataset(ann_file)

    # 打印摘要
    logger.info("\n" + "=" * 60)
    logger.info(f"Dataset Analysis Summary - {args.split.upper()}")
    logger.info("=" * 60)
    logger.info(f"Images: {stats['num_images']:,}")
    logger.info(f"Annotations: {stats['num_annotations']:,}")
    logger.info(f"Categories: {stats['num_categories']}")
    logger.info(f"Avg Labels/Image: {stats['avg_labels_per_image']:.2f}")
    logger.info(f"Imbalance Ratio: {stats['imbalance_ratio']:.2f}:1")
    logger.info(f"Minority Classes: {', '.join(stats['minority_classes'])}")
    logger.info("=" * 60 + "\n")

    # 生成可视化
    if args.visualize:
        visualize_dataset(stats, args.split)

    # 生成报告
    if args.report:
        report = generate_report(stats, args.split)
        print(report)


if __name__ == "__main__":
    main()
