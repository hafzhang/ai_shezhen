#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据集验证脚本

验证shezhenv3-coco数据集的完整性，处理不规则文件名，
检查图像与标注对应关系，统计类别分布。

Usage:
    python datasets/tools/validate_dataset.py --data_root path/to/shezhenv3-coco --split train
    python datasets/tools/validate_dataset.py --data_root path/to/shezhenv3-coco --all
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

# 设置Windows控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pycocotools.coco import COCO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatasetValidator:
    """数据集验证器"""

    def __init__(self, data_root: str):
        """
        初始化验证器

        Args:
            data_root: 数据集根目录
        """
        self.data_root = Path(data_root)
        self.results = {
            "total_samples": 0,
            "valid_samples": 0,
            "corrupted_images": [],
            "missing_annotations": [],
            "missing_images": [],
            "irregular_filenames": [],
            "category_distribution": {},
            "imbalance_analysis": {},
            "multi_label_stats": {}
        }

    def check_file_exists(self, file_path: Path) -> bool:
        """检查文件是否存在且可读"""
        return file_path.exists() and file_path.is_file()

    def check_image_readable(self, image_path: Path) -> Tuple[bool, str]:
        """
        检查图像是否可读

        Args:
            image_path: 图像文件路径

        Returns:
            (is_readable, error_message)
        """
        try:
            # 尝试使用PIL读取
            with Image.open(image_path) as img:
                img.verify()
            # 尝试使用cv2读取（更严格）
            img = cv2.imread(str(image_path))
            if img is None:
                return False, "cv2.imread failed"
            return True, ""
        except Exception as e:
            return False, str(e)

    def detect_irregular_filename(self, filename: str) -> bool:
        """
        检测不规则文件名（如带括号、空格等）

        Args:
            filename: 文件名

        Returns:
            是否为不规则文件名
        """
        irregular_patterns = ['(', ')', ' ', '（', '）']
        return any(pattern in filename for pattern in irregular_patterns)

    def validate_split(self, split: str) -> Dict[str, Any]:
        """
        验证单个数据集划分

        Args:
            split: 数据集划分名称 (train/val/test)

        Returns:
            验证结果字典
        """
        logger.info(f"Validating {split} split...")

        split_dir = self.data_root / split
        images_dir = split_dir / "images"
        ann_file = split_dir / "annotations" / f"{split}.json"

        # 检查目录和文件是否存在
        if not images_dir.exists():
            logger.error(f"Images directory not found: {images_dir}")
            return {"error": f"Images directory not found: {images_dir}"}

        if not ann_file.exists():
            logger.error(f"Annotation file not found: {ann_file}")
            return {"error": f"Annotation file not found: {ann_file}"}

        # 加载COCO标注
        try:
            coco = COCO(str(ann_file))
        except Exception as e:
            logger.error(f"Failed to load COCO annotations: {e}")
            return {"error": f"Failed to load COCO annotations: {e}"}

        # 获取所有图像文件
        image_files = list(images_dir.glob("*"))
        image_files = [f for f in image_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]

        logger.info(f"Found {len(image_files)} image files")

        # 构建文件名到ID的映射
        filename_to_id = {}
        for img_id, img_info in coco.imgs.items():
            original_name = img_info["file_name"]
            # 处理可能的文件名问题
            filename_to_id[original_name] = img_id

        # 验证每个图像
        valid_count = 0
        corrupted_list = []
        missing_ann_list = []
        irregular_filenames = []

        for img_file in tqdm(image_files, desc=f"Validating {split} images"):
            img_filename = img_file.name

            # 检测不规则文件名
            if self.detect_irregular_filename(img_filename):
                irregular_filenames.append(str(img_file))

            # 检查是否在标注中
            if img_filename not in filename_to_id:
                # 尝试去掉扩展名再匹配
                base_name = Path(img_filename).stem
                found = False
                for ann_name in filename_to_id.keys():
                    if Path(ann_name).stem == base_name:
                        filename_to_id[img_filename] = filename_to_id[ann_name]
                        found = True
                        break

                if not found:
                    missing_ann_list.append(img_filename)
                    continue

            # 检查图像可读性
            is_readable, error_msg = self.check_image_readable(img_file)
            if not is_readable:
                corrupted_list.append(f"{img_filename}: {error_msg}")
                continue

            valid_count += 1

        # 检查标注中的图像是否都存在
        missing_images = []
        for img_id, img_info in coco.imgs.items():
            img_path = images_dir / img_info["file_name"]
            if not img_path.exists():
                missing_images.append(img_info["file_name"])

        # 统计类别分布
        cat_counter = Counter()
        for ann in coco.anns.values():
            cat_counter[ann["category_id"]] += 1

        category_distribution = {}
        for cat_id, cat_info in coco.cats.items():
            count = cat_counter.get(cat_id, 0)
            category_distribution[cat_info["name"]] = {
                "id": cat_id,
                "count": count,
                "percentage": count / len(coco.imgs) * 100 if coco.imgs else 0
            }

        # 多标签统计
        img_id_to_cats = defaultdict(set)
        for ann in coco.anns.values():
            img_id_to_cats[ann["image_id"]].add(ann["category_id"])

        labels_per_image = [len(cats) for cats in img_id_to_cats.values()]
        multi_label_stats = {
            "avg_labels_per_image": float(np.mean(labels_per_image)) if labels_per_image else 0,
            "max_labels_per_image": max(labels_per_image) if labels_per_image else 0,
            "min_labels_per_image": min(labels_per_image) if labels_per_image else 0,
            "label_distribution": dict(Counter(labels_per_image))
        }

        # 不平衡分析
        counts = list(cat_counter.values())
        imbalance_ratio = max(counts) / min(counts) if counts and min(counts) > 0 else float('inf')

        median_count = np.median(counts) if counts else 0
        minority_classes = []
        majority_classes = []

        for cat_id, count in cat_counter.items():
            if cat_id not in coco.cats:
                logger.warning(f"Category ID {cat_id} not found in coco.cats, skipping.")
                continue
            cat_name = coco.cats[cat_id]["name"]
            if count < median_count * 0.5:
                minority_classes.append(cat_name)
            elif count > median_count * 1.5:
                majority_classes.append(cat_name)

        imbalance_analysis = {
            "imbalance_ratio": float(imbalance_ratio),
            "min_count": int(min(counts)) if counts else 0,
            "max_count": int(max(counts)) if counts else 0,
            "median_count": float(median_count),
            "minority_classes": minority_classes,
            "majority_classes": majority_classes
        }

        results = {
            "split": split,
            "total_images": len(image_files),
            "valid_images": valid_count,
            "corrupted_images": corrupted_list,
            "missing_annotations": missing_ann_list,
            "missing_images": missing_images,
            "irregular_filenames": irregular_filenames,
            "category_distribution": category_distribution,
            "multi_label_stats": multi_label_stats,
            "imbalance_analysis": imbalance_analysis,
            "total_annotations": len(coco.anns),
            "total_categories": len(coco.cats)
        }

        return results

    def generate_quality_report(self, results: Dict[str, Any], output_path: str):
        """
        生成数据集质量报告

        Args:
            results: 验证结果
            output_path: 输出路径
        """
        report = {
            "dataset_name": "shezhenv3-coco",
            "validation_date": str(Path.cwd()),
            "summary": {
                "total_samples": results.get("total_images", 0),
                "valid_samples": results.get("valid_images", 0),
                "corrupted_count": len(results.get("corrupted_images", [])),
                "missing_annotations_count": len(results.get("missing_annotations", [])),
                "missing_images_count": len(results.get("missing_images", [])),
                "irregular_filenames_count": len(results.get("irregular_filenames", []))
            },
            "details": results
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"Quality report saved to {output_path}")

        # 打印摘要
        self._print_summary(results)

    def _print_summary(self, results: Dict[str, Any]):
        """打印验证摘要"""
        print("\n" + "=" * 70)
        print(f"数据集验证报告 - {results.get('split', 'Unknown').upper()}")
        print("=" * 70)

        print(f"\n基础统计:")
        print(f"  总样本数: {results.get('total_images', 0):,}")
        print(f"  有效样本数: {results.get('valid_images', 0):,}")
        print(f"  标注数量: {results.get('total_annotations', 0):,}")
        print(f"  类别数量: {results.get('total_categories', 0)}")

        print(f"\n数据质量:")
        print(f"  损坏文件数: {len(results.get('corrupted_images', []))}")
        print(f"  缺失标注数: {len(results.get('missing_annotations', []))}")
        print(f"  缺失图像数: {len(results.get('missing_images', []))}")
        print(f"  不规则文件名数: {len(results.get('irregular_filenames', []))}")

        multi_label = results.get('multi_label_stats', {})
        print(f"\n多标签统计:")
        print(f"  平均标签数/图: {multi_label.get('avg_labels_per_image', 0):.2f}")
        print(f"  最大标签数: {multi_label.get('max_labels_per_image', 0)}")
        print(f"  最小标签数: {multi_label.get('min_labels_per_image', 0)}")

        imbalance = results.get('imbalance_analysis', {})
        print(f"\n类别不平衡分析:")
        print(f"  不平衡比: {imbalance.get('imbalance_ratio', 0):.2f}:1")
        print(f"  最小类别样本数: {imbalance.get('min_count', 0)}")
        print(f"  最大类别样本数: {imbalance.get('max_count', 0)}")

        print(f"\n少数类 (需要特别关注):")
        minority = imbalance.get('minority_classes', [])
        if minority:
            for cls in minority:
                print(f"  - {cls}")
        else:
            print("  无")

        print(f"\n多数类:")
        majority = imbalance.get('majority_classes', [])
        if majority:
            for cls in majority:
                print(f"  - {cls}")
        else:
            print("  无")

        print("\n" + "=" * 70)

        # 类别分布详情
        print("\n类别分布详情 (按样本数排序):")
        cat_dist = results.get('category_distribution', {})
        sorted_cats = sorted(cat_dist.items(), key=lambda x: x[1]['count'], reverse=True)

        print(f"{'排名':<6} {'类别名称':<20} {'样本数':<10} {'占比':<10} {'状态':<15}")
        print("-" * 70)

        for i, (cat_name, info) in enumerate(sorted_cats, 1):
            count = info['count']
            percentage = info['percentage']

            # 判断状态
            if cat_name in minority:
                status = "[!] 少数类"
            elif cat_name in majority:
                status = "[*] 多数类"
            else:
                status = "[OK] 正常"

            print(f"{i:<6} {cat_name:<20} {count:<10} {percentage:<10.1f}% {status:<15}")

        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Validate shezhenv3-coco dataset")
    parser.add_argument("--data_root", type=str,
                       default="C:/Users/Administrator/Desktop/AI_shezhen/shezhenv3-coco",
                       help="Root directory of the dataset")
    parser.add_argument("--split", type=str, default=None,
                       choices=["train", "val", "test"],
                       help="Specific split to validate (default: all)")
    parser.add_argument("--all", action="store_true",
                       help="Validate all splits")
    parser.add_argument("--output", type=str,
                       default="datasets/raw/quality_report.json",
                       help="Output path for quality report")

    args = parser.parse_args()

    validator = DatasetValidator(args.data_root)

    if args.all or args.split is None:
        # 验证所有划分
        splits = ["train", "val", "test"]
        all_results = {}

        for split in splits:
            results = validator.validate_split(split)
            all_results[split] = results

        # 生成总报告
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        logger.info(f"Combined quality report saved to {output_path}")

        # 打印各划分摘要
        for split, results in all_results.items():
            if "error" not in results:
                validator._print_summary(results)

    else:
        # 验证单个划分
        results = validator.validate_split(args.split)
        validator.generate_quality_report(results, args.output)


if __name__ == "__main__":
    main()
