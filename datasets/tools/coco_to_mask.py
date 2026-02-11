#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COCO到分割标签格式转换脚本

将COCO格式的polygon标注转换为二值mask图像。
支持处理多边形、孔洞（舌面裂纹）等复杂情况。
生成的mask图像：舌体区域=255，背景=0

Usage:
    python datasets/tools/coco_to_mask.py --data_root path/to/shezhenv3-coco --split train
    python datasets/tools/coco_to_mask.py --all
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm
from pycocotools.coco import COCO

# 设置Windows控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class COCOToMaskConverter:
    """COCO标注到二值mask转换器"""

    def __init__(self, data_root: str, output_base: str = None):
        """
        初始化转换器

        Args:
            data_root: COCO数据集根目录
            output_base: 输出基础目录 (默认: datasets/processed/seg_v1)
        """
        self.data_root = Path(data_root)
        if output_base is None:
            output_base = Path(__file__).parent.parent.parent / "processed" / "seg_v1"
        else:
            output_base = Path(output_base)

        self.output_base = output_base
        self.stats = {
            "total_images": 0,
            "processed_images": 0,
            "failed_images": [],
            "empty_annotations": [],
            "multi_polygon_images": 0,
            "holes_processed": 0,
            "total_polygons": 0,
            "polygon_stats": defaultdict(int)
        }

    def polygon_to_mask(self, polygon: List[List[float]],
                       image_size: Tuple[int, int]) -> np.ndarray:
        """
        将单个polygon转换为二值mask

        Args:
            polygon: 多边形坐标列表 [[x1,y1,x2,y2,...], ...]
            image_size: 图像尺寸 (height, width)

        Returns:
            二值mask (H, W), 值为0或255
        """
        height, width = image_size
        mask = np.zeros((height, width), dtype=np.uint8)

        # 处理所有多边形（外轮廓和孔洞）
        # 在COCO格式中，一个annotation可以有多个segmentation
        # 通常第一个是外轮廓，后续的是孔洞
        for i, poly_coords in enumerate(polygon):
            if len(poly_coords) < 6:  # 至少需要3个点 (6个坐标值)
                logger.warning(f"Invalid polygon with {len(poly_coords)} coordinates")
                continue

            # 将坐标重塑为 (N, 2) 格式
            pts = np.array(poly_coords, dtype=np.int32).reshape(-1, 2)

            # 使用fillPoly填充多边形
            # 第一个多边形用255填充，后续多边形需要判断是孔洞还是独立区域
            if i == 0:
                cv2.fillPoly(mask, [pts], 255)
            else:
                # 对于后续多边形，判断是否为孔洞
                # 简单策略：检查多边形中心点是否在已有mask内
                center = pts.mean(axis=0).astype(int)
                y, x = center[1], center[0]

                if 0 <= y < height and 0 <= x < width:
                    if mask[y, x] == 255:
                        # 中心点在mask内，认为是孔洞，用0填充
                        cv2.fillPoly(mask, [pts], 0)
                        self.stats["holes_processed"] += 1
                    else:
                        # 中心点在mask外，认为是独立区域，用255填充
                        cv2.fillPoly(mask, [pts], 255)
                else:
                    # 边界情况，默认视为独立区域
                    cv2.fillPoly(mask, [pts], 255)

        return mask

    def annotations_to_mask(self, annotations: List[Dict],
                          image_size: Tuple[int, int]) -> np.ndarray:
        """
        将所有annotations合并为一个mask

        Args:
            annotations: 该图像的所有标注列表
            image_size: 图像尺寸 (height, width)

        Returns:
            合并后的二值mask
        """
        height, width = image_size
        combined_mask = np.zeros((height, width), dtype=np.uint8)

        if not annotations:
            return combined_mask

        # 统计多边形数量
        polygon_count = sum(len(ann.get("segmentation", [])) for ann in annotations)
        self.stats["polygon_stats"][polygon_count] += 1
        self.stats["total_polygons"] += polygon_count

        if polygon_count > 1:
            self.stats["multi_polygon_images"] += 1

        # 处理每个annotation
        for ann in annotations:
            segmentation = ann.get("segmentation", [])
            if not segmentation:
                continue

            # 将该annotation的多边形转换为mask
            ann_mask = self.polygon_to_mask(segmentation, image_size)

            # 合并到总mask
            combined_mask = cv2.bitwise_or(combined_mask, ann_mask)

        return combined_mask

    def convert_split(self, split: str) -> Dict[str, Any]:
        """
        转换单个数据集划分

        Args:
            split: 数据集划分名称 (train/val/test)

        Returns:
            转换结果统计
        """
        logger.info(f"Converting {split} split...")

        split_dir = self.data_root / split
        images_dir = split_dir / "images"
        ann_file = split_dir / "annotations" / f"{split}.json"

        # 输出目录
        output_images_dir = self.output_base / split / "images"
        output_masks_dir = self.output_base / split / "masks"
        output_images_dir.mkdir(parents=True, exist_ok=True)
        output_masks_dir.mkdir(parents=True, exist_ok=True)

        # 检查文件存在性
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

        # 构建image_id到annotations的映射
        img_id_to_anns = defaultdict(list)
        for ann in coco.anns.values():
            img_id_to_anns[ann["image_id"]].append(ann)

        # 处理每个图像
        processed_count = 0
        failed_list = []
        empty_list = []

        images = list(coco.imgs.values())
        self.stats["total_images"] += len(images)

        for img_info in tqdm(images, desc=f"Converting {split}"):
            img_id = img_info["id"]
            img_filename = img_info["file_name"]

            # 获取图像路径
            img_path = images_dir / img_filename
            if not img_path.exists():
                failed_list.append(f"{img_filename}: image file not found")
                continue

            # 读取图像获取尺寸
            try:
                img = cv2.imread(str(img_path))
                if img is None:
                    failed_list.append(f"{img_filename}: failed to read image")
                    continue
                height, width = img.shape[:2]
            except Exception as e:
                failed_list.append(f"{img_filename}: {str(e)}")
                continue

            # 获取该图像的annotations
            annotations = img_id_to_anns.get(img_id, [])

            if not annotations:
                empty_list.append(img_filename)
                # 仍然生成全0的mask
                mask = np.zeros((height, width), dtype=np.uint8)
            else:
                # 生成mask
                mask = self.annotations_to_mask(annotations, (height, width))

            # 确定输出文件名（处理不规则文件名）
            # 使用原始文件名的stem，改为.png格式
            output_stem = Path(img_filename).stem
            mask_filename = f"{output_stem}.png"

            # 保存mask
            mask_path = output_masks_dir / mask_filename
            cv2.imwrite(str(mask_path), mask)

            # 可选：复制/链接原始图像到输出目录
            # 这里我们创建一个符号或复制，取决于需求
            # 为简单起见，我们只保存mask路径信息

            processed_count += 1

        self.stats["processed_images"] += processed_count
        self.stats["failed_images"].extend(failed_list)
        self.stats["empty_annotations"].extend(empty_list)

        logger.info(f"{split} conversion complete: {processed_count} images processed")

        return {
            "split": split,
            "processed": processed_count,
            "failed": len(failed_list),
            "empty_masks": len(empty_list),
            "output_dir": str(self.output_base / split)
        }

    def visualize_sample_masks(self, split: str, num_samples: int = 5,
                               output_dir: str = None) -> List[str]:
        """
        可视化mask转换效果，叠加在原图上

        Args:
            split: 数据集划分
            num_samples: 可视化样本数量
            output_dir: 输出目录

        Returns:
            可视化图像路径列表
        """
        if output_dir is None:
            output_dir = self.output_base / "visualizations" / split
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        split_dir = self.data_root / split
        images_dir = split_dir / "images"
        masks_dir = self.output_base / split / "masks"

        # 获取一些样本
        mask_files = list(masks_dir.glob("*.png"))[:num_samples]

        visualization_paths = []

        for mask_path in mask_files:
            # 读取原图和mask
            img_stem = mask_path.stem
            img_files = list(images_dir.glob(f"{img_stem}.*"))

            if not img_files:
                continue

            img_path = img_files[0]
            img = cv2.imread(str(img_path))
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

            if img is None or mask is None:
                continue

            # 调整mask尺寸以匹配原图
            if mask.shape[:2] != img.shape[:2]:
                mask = cv2.resize(mask, (img.shape[1], img.shape[0]),
                                 interpolation=cv2.INTER_NEAREST)

            # 创建叠加可视化
            # 半透明红色显示mask区域
            overlay = img.copy()
            colored_mask = np.zeros_like(img)
            colored_mask[mask > 127] = [0, 0, 255]  # 红色

            cv2.addWeighted(overlay, 0.7, colored_mask, 0.3, 0, overlay)

            # 绘制边界
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                          cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, (0, 255, 0), 2)

            # 保存
            vis_path = output_dir / f"vis_{img_stem}.jpg"
            cv2.imwrite(str(vis_path), overlay)
            visualization_paths.append(str(vis_path))

        logger.info(f"Generated {len(visualization_paths)} visualizations")
        return visualization_paths

    def validate_masks(self, split: str) -> Dict[str, Any]:
        """
        验证生成的mask质量

        Args:
            split: 数据集划分

        Returns:
            验证结果
        """
        logger.info(f"Validating masks for {split}...")

        masks_dir = self.output_base / split / "masks"
        mask_files = list(masks_dir.glob("*.png"))

        if not mask_files:
            return {"error": "No mask files found"}

        validation_results = {
            "total_masks": len(mask_files),
            "valid_masks": 0,
            "empty_masks": 0,
            "full_masks": 0,
            "size_mismatches": [],
            "corrupted_masks": []
        }

        split_dir = self.data_root / split
        images_dir = split_dir / "images"

        for mask_path in tqdm(mask_files, desc=f"Validating {split} masks"):
            try:
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is None:
                    validation_results["corrupted_masks"].append(mask_path.name)
                    continue

                # 检查是否为空
                if np.sum(mask) == 0:
                    validation_results["empty_masks"] += 1
                # 检查是否全满
                elif np.all(mask == 255):
                    validation_results["full_masks"] += 1
                else:
                    validation_results["valid_masks"] += 1

                # 检查尺寸是否与原图匹配
                img_stem = mask_path.stem
                img_files = list(images_dir.glob(f"{img_stem}.*"))

                if img_files:
                    img = cv2.imread(str(img_files[0]))
                    if img is not None and mask.shape[:2] != img.shape[:2]:
                        validation_results["size_mismatches"].append({
                            "mask": mask_path.name,
                            "mask_size": mask.shape[:2],
                            "image_size": img.shape[:2]
                        })

            except Exception as e:
                validation_results["corrupted_masks"].append(f"{mask_path.name}: {str(e)}")

        # 计算通过率
        total = validation_results["total_masks"]
        valid = validation_results["valid_masks"]
        pass_rate = (valid / total * 100) if total > 0 else 0

        validation_results["pass_rate"] = pass_rate

        logger.info(f"Validation complete: {pass_rate:.1f}% pass rate")

        return validation_results

    def generate_report(self, output_path: str = None):
        """
        生成转换报告

        Args:
            output_path: 输出路径
        """
        if output_path is None:
            output_path = self.output_base / "conversion_report.json"

        report = {
            "conversion_summary": dict(self.stats),
            "polygon_distribution": dict(self.stats["polygon_stats"])
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"Conversion report saved to {output_path}")

        # 打印摘要
        self._print_summary()

    def _print_summary(self):
        """打印转换摘要"""
        print("\n" + "=" * 70)
        print("COCO到Mask转换报告")
        print("=" * 70)

        print(f"\n转换统计:")
        print(f"  总图像数: {self.stats['total_images']:,}")
        print(f"  成功处理: {self.stats['processed_images']:,}")
        print(f"  失败数量: {len(self.stats['failed_images'])}")
        print(f"  空标注数量: {len(self.stats['empty_annotations'])}")

        print(f"\n多边形统计:")
        print(f"  总多边形数: {self.stats['total_polygons']:,}")
        print(f"  多多边形图像数: {self.stats['multi_polygon_images']:,}")
        print(f"  处理的孔洞数: {self.stats['holes_processed']:,}")

        print(f"\n多边形分布:")
        for count, num_images in sorted(self.stats['polygon_stats'].items()):
            print(f"  {count} 个多边形: {num_images} 图像")

        print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Convert COCO annotations to binary masks")
    parser.add_argument("--data_root", type=str,
                       default="shezhenv3-coco",
                       help="Root directory of COCO dataset")
    parser.add_argument("--output_base", type=str,
                       default="datasets/processed/seg_v1",
                       help="Base output directory for converted masks")
    parser.add_argument("--split", type=str, default=None,
                       choices=["train", "val", "test"],
                       help="Specific split to convert (default: all)")
    parser.add_argument("--all", action="store_true",
                       help="Convert all splits")
    parser.add_argument("--visualize", action="store_true",
                       help="Generate visualization samples")
    parser.add_argument("--validate", action="store_true",
                       help="Validate generated masks")
    parser.add_argument("--vis_samples", type=int, default=10,
                       help="Number of visualization samples per split")

    args = parser.parse_args()

    converter = COCOToMaskConverter(args.data_root, args.output_base)

    if args.all or args.split is None:
        # 转换所有划分
        splits = ["train", "val", "test"]
        results = {}

        for split in splits:
            result = converter.convert_split(split)
            results[split] = result

            # 验证
            if args.validate:
                val_result = converter.validate_masks(split)
                results[f"{split}_validation"] = val_result

            # 可视化
            if args.visualize:
                converter.visualize_sample_masks(split, args.vis_samples)

        # 生成报告
        converter.generate_report()

    else:
        # 转换单个划分
        result = converter.convert_split(args.split)

        if args.validate:
            val_result = converter.validate_masks(args.split)
            result["validation"] = val_result

        if args.visualize:
            converter.visualize_sample_masks(args.split, args.vis_samples)

        converter.generate_report()


if __name__ == "__main__":
    main()
