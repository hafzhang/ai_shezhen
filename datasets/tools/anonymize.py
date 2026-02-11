#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据脱敏与EXIF信息清理脚本

去除图像EXIF信息（GPS、设备型号等），实现文件名哈希化匿名处理，
确保数据隐私合规。

Usage:
    python datasets/tools/anonymize.py --input path/to/input --output path/to/output
    python datasets/tools/anonymize.py --input path/to/input --output path/to/output --hash-filenames
    python datasets/tools/anonymize.py --input path/to/input --output path/to/output --report-only
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from tqdm import tqdm

# 设置Windows控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EXIFCleaner:
    """EXIF信息清理器"""

    # 敏感EXIF标签（需要删除）
    SENSITIVE_TAGS = [
        'GPSInfo',           # GPS定位信息
        'Make',              # 设备制造商
        'Model',             # 设备型号
        'Software',          # 软件信息
        'DateTime',          # 拍摄时间
        'DateTimeOriginal',  # 原始拍摄时间
        'DateTimeDigitized', # 数字化时间
        'Artist',            # 艺术家/作者
        'Copyright',         # 版权信息
        'ImageDescription',  # 图像描述（可能包含个人信息）
        'UserComment',       # 用户评论
        'XPAuthor',          # Windows作者标签
        'XPComment',         # Windows评论标签
        'XPKeywords',        # Windows关键词标签
        'XPTitle',           # Windows标题标签
        'XPSubject',         # Windows主题标签
        'CameraSerialNumber',# 相机序列号
        'LensModel',         # 镜头型号
        'LensSerialNumber',  # 镜头序列号
        'SerialNumber',      # 序列号
        'OwnerName',         # 所有者名称
        'UniqueCameraModel', # 唯一相机型号
        'LocalizedName',     # 本地化名称
    ]

    def __init__(self):
        self.stats = {
            "total_images": 0,
            "images_with_exif": 0,
            "images_cleaned": 0,
            "exif_tags_removed": 0,
            "errors": []
        }

    def get_exif_data(self, image_path: Path) -> Optional[Dict]:
        """
        获取图像的EXIF数据

        Args:
            image_path: 图像文件路径

        Returns:
            EXIF数据字典，如果没有EXIF则返回None
        """
        try:
            with Image.open(image_path) as img:
                # BMP, PNG等格式不支持EXIF
                if not hasattr(img, '_getexif'):
                    return None
                exif = img._getexif()
                if exif:
                    return {TAGS.get(k, k): v for k, v in exif.items()}
                return None
        except Exception as e:
            logger.warning(f"Error reading EXIF from {image_path}: {e}")
            return None

    def analyze_exif(self, image_path: Path) -> Dict[str, Any]:
        """
        分析图像EXIF信息，检测敏感数据

        Args:
            image_path: 图像文件路径

        Returns:
            分析结果字典
        """
        exif_data = self.get_exif_data(image_path)

        result = {
            "has_exif": exif_data is not None,
            "total_tags": len(exif_data) if exif_data else 0,
            "sensitive_tags_found": [],
            "gps_data": None,
            "device_info": None
        }

        if exif_data:
            for tag in self.SENSITIVE_TAGS:
                if tag in exif_data:
                    result["sensitive_tags_found"].append(tag)

                    # 特殊处理GPS信息
                    if tag == 'GPSInfo':
                        gps_data = {}
                        for k, v in exif_data[tag].items():
                            gps_tag = GPSTAGS.get(k, k)
                            gps_data[gps_tag] = str(v)[:100]  # 截断长字符串
                        result["gps_data"] = gps_data

                    # 特殊处理设备信息
                    if tag in ['Make', 'Model', 'Software']:
                        if result["device_info"] is None:
                            result["device_info"] = {}
                        result["device_info"][tag] = str(exif_data[tag])[:100]

        return result

    def clean_exif(self, input_path: Path, output_path: Path) -> Tuple[bool, str]:
        """
        清理图像EXIF信息并保存

        Args:
            input_path: 输入图像路径
            output_path: 输出图像路径

        Returns:
            (success, message)
        """
        try:
            with Image.open(input_path) as img:
                # 获取原始EXIF数据用于统计
                original_exif = img._getexif()
                tags_removed = 0

                if original_exif:
                    tags_removed = len(original_exif)
                    self.stats["images_with_exif"] += 1

                # 创建新图像（不含EXIF）
                # 使用原图的数据创建新图像，但不包含任何元数据
                data = list(img.getdata())
                new_img = Image.new(img.mode, img.size)
                new_img.putdata(data)

                # 保存为JPEG时不包含EXIF
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # 保存时确保不包含任何元数据
                if img.format == 'JPEG' or output_path.suffix.lower() in ['.jpg', '.jpeg']:
                    new_img.save(output_path, 'JPEG', quality=95)
                elif img.format == 'PNG' or output_path.suffix.lower() == '.png':
                    new_img.save(output_path, 'PNG')
                else:
                    new_img.save(output_path)

                self.stats["exif_tags_removed"] += tags_removed
                self.stats["images_cleaned"] += 1

                return True, f"Cleaned {tags_removed} EXIF tags"

        except Exception as e:
            error_msg = f"Error cleaning {input_path}: {e}"
            self.stats["errors"].append(error_msg)
            return False, error_msg


class FilenameAnonymizer:
    """文件名匿名化处理器"""

    def __init__(self, salt: str = "shezhen_anonymize_v1"):
        """
        初始化匿名化处理器

        Args:
            salt: 哈希盐值，用于增加哈希的不可逆性
        """
        self.salt = salt
        self.mapping = {}  # 原始文件名 -> 哈希后文件名的映射
        self.reverse_mapping = {}  # 哈希后文件名 -> 原始文件名（用于审计）

    def hash_filename(self, original_name: str, preserve_extension: bool = True) -> str:
        """
        将文件名哈希化

        Args:
            original_name: 原始文件名
            preserve_extension: 是否保留文件扩展名

        Returns:
            哈希后的文件名
        """
        # 获取扩展名
        path = Path(original_name)
        extension = path.suffix if preserve_extension else ""

        # 对文件名（不含扩展名）进行哈希
        name_without_ext = path.stem
        hash_input = f"{self.salt}_{name_without_ext}".encode('utf-8')
        hashed_name = hashlib.sha256(hash_input).hexdigest()[:16]

        # 构建新文件名
        new_name = f"{hashed_name}{extension}"

        # 保存映射
        self.mapping[original_name] = new_name
        self.reverse_mapping[new_name] = original_name

        return new_name

    def save_mapping(self, output_path: Path):
        """
        保存文件名映射表（用于审计）

        Args:
            output_path: 输出文件路径
        """
        mapping_data = {
            "generated_at": datetime.now().isoformat(),
            "salt_hash": hashlib.sha256(self.salt.encode()).hexdigest()[:8],
            "mapping_count": len(self.mapping),
            "mappings": self.mapping
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Filename mapping saved to {output_path}")


class DataAnonymizer:
    """数据脱敏主类"""

    def __init__(self, input_dir: str, output_dir: str, hash_filenames: bool = False):
        """
        初始化数据脱敏器

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            hash_filenames: 是否对文件名进行哈希化
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.hash_filenames = hash_filenames

        self.exif_cleaner = EXIFCleaner()
        self.filename_anonymizer = FilenameAnonymizer()

        self.report = {
            "anonymization_date": datetime.now().isoformat(),
            "input_directory": str(self.input_dir),
            "output_directory": str(self.output_dir),
            "options": {
                "hash_filenames": hash_filenames
            },
            "statistics": {
                "total_images": 0,
                "images_with_exif": 0,
                "images_cleaned": 0,
                "exif_tags_removed": 0,
                "filenames_hashed": 0
            },
            "exif_analysis": {
                "images_with_sensitive_data": [],
                "sensitive_tags_summary": {}
            },
            "errors": []
        }

    def analyze_directory(self) -> Dict[str, Any]:
        """
        分析目录中的所有图像EXIF信息

        Returns:
            分析报告
        """
        logger.info(f"Analyzing EXIF data in {self.input_dir}")

        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        image_files = []

        for ext in image_extensions:
            image_files.extend(self.input_dir.rglob(f"*{ext}"))
            image_files.extend(self.input_dir.rglob(f"*{ext.upper()}"))

        image_files = list(set(image_files))

        logger.info(f"Found {len(image_files)} images to analyze")

        analysis_results = {
            "total_images": len(image_files),
            "images_with_exif": 0,
            "images_with_sensitive_data": 0,
            "sensitive_tags_breakdown": {},
            "details": []
        }

        for img_path in tqdm(image_files, desc="Analyzing EXIF"):
            exif_analysis = self.exif_cleaner.analyze_exif(img_path)

            if exif_analysis["has_exif"]:
                analysis_results["images_with_exif"] += 1

            if exif_analysis["sensitive_tags_found"]:
                analysis_results["images_with_sensitive_data"] += 1

                for tag in exif_analysis["sensitive_tags_found"]:
                    analysis_results["sensitive_tags_breakdown"][tag] = \
                        analysis_results["sensitive_tags_breakdown"].get(tag, 0) + 1

                analysis_results["details"].append({
                    "file": str(img_path.relative_to(self.input_dir)),
                    "sensitive_tags": exif_analysis["sensitive_tags_found"],
                    "has_gps": exif_analysis["gps_data"] is not None
                })

        return analysis_results

    def process_images(self, report_only: bool = False) -> Dict[str, Any]:
        """
        处理所有图像

        Args:
            report_only: 仅生成报告，不实际处理

        Returns:
            处理结果
        """
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        image_files = []

        for ext in image_extensions:
            image_files.extend(self.input_dir.rglob(f"*{ext}"))
            image_files.extend(self.input_dir.rglob(f"*{ext.upper()}"))

        image_files = list(set(image_files))

        logger.info(f"Found {len(image_files)} images to process")
        self.report["statistics"]["total_images"] = len(image_files)

        if report_only:
            # 仅分析模式
            logger.info("Running in report-only mode")
            for img_path in tqdm(image_files, desc="Analyzing"):
                exif_analysis = self.exif_cleaner.analyze_exif(img_path)

                if exif_analysis["sensitive_tags_found"]:
                    self.report["exif_analysis"]["images_with_sensitive_data"].append({
                        "file": str(img_path.relative_to(self.input_dir)),
                        "sensitive_tags": exif_analysis["sensitive_tags_found"],
                        "gps_present": exif_analysis["gps_data"] is not None
                    })

                    for tag in exif_analysis["sensitive_tags_found"]:
                        self.report["exif_analysis"]["sensitive_tags_summary"][tag] = \
                            self.report["exif_analysis"]["sensitive_tags_summary"].get(tag, 0) + 1
        else:
            # 实际处理模式
            for img_path in tqdm(image_files, desc="Processing"):
                # 计算相对路径
                rel_path = img_path.relative_to(self.input_dir)

                # 处理文件名
                if self.hash_filenames:
                    new_filename = self.filename_anonymizer.hash_filename(img_path.name)
                    new_rel_path = rel_path.parent / new_filename
                    self.report["statistics"]["filenames_hashed"] += 1
                else:
                    new_rel_path = rel_path

                # 输出路径
                output_path = self.output_dir / new_rel_path

                # 清理EXIF并保存
                success, message = self.exif_cleaner.clean_exif(img_path, output_path)

                if not success:
                    self.report["errors"].append(message)

        # 更新统计
        self.report["statistics"]["images_with_exif"] = self.exif_cleaner.stats["images_with_exif"]
        self.report["statistics"]["images_cleaned"] = self.exif_cleaner.stats["images_cleaned"]
        self.report["statistics"]["exif_tags_removed"] = self.exif_cleaner.stats["exif_tags_removed"]
        self.report["errors"].extend(self.exif_cleaner.stats["errors"])

        return self.report

    def process_coco_annotations(self, annotation_file: Path, output_file: Path):
        """
        处理COCO标注文件，更新文件名映射

        Args:
            annotation_file: 输入COCO标注文件
            output_file: 输出COCO标注文件
        """
        if not self.hash_filenames:
            # 不需要处理，直接复制
            import shutil
            shutil.copy(annotation_file, output_file)
            return

        with open(annotation_file, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)

        # 更新图像文件名
        for img_info in coco_data.get('images', []):
            original_name = img_info['file_name']
            if original_name in self.filename_anonymizer.mapping:
                img_info['file_name'] = self.filename_anonymizer.mapping[original_name]
            else:
                # 如果文件名还没有被哈希，现在进行哈希
                img_info['file_name'] = self.filename_anonymizer.hash_filename(original_name)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Updated COCO annotations saved to {output_file}")

    def save_report(self, output_path: Path):
        """
        保存脱敏报告

        Args:
            output_path: 输出文件路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)

        logger.info(f"Anonymization report saved to {output_path}")

    def print_summary(self):
        """打印处理摘要"""
        stats = self.report["statistics"]
        exif_analysis = self.report["exif_analysis"]

        print("\n" + "=" * 70)
        print("数据脱敏报告")
        print("=" * 70)

        print(f"\n处理统计:")
        print(f"  总图像数: {stats['total_images']}")
        print(f"  包含EXIF的图像: {stats['images_with_exif']}")
        print(f"  已清理的图像: {stats['images_cleaned']}")
        print(f"  删除的EXIF标签数: {stats['exif_tags_removed']}")

        if self.hash_filenames:
            print(f"  哈希化的文件名数: {stats['filenames_hashed']}")

        if exif_analysis["sensitive_tags_summary"]:
            print(f"\n敏感EXIF标签统计:")
            for tag, count in sorted(exif_analysis["sensitive_tags_summary"].items(),
                                    key=lambda x: x[1], reverse=True):
                print(f"  - {tag}: {count} 个图像")

        if self.report["errors"]:
            print(f"\n错误数: {len(self.report['errors'])}")
            for error in self.report["errors"][:5]:  # 只显示前5个错误
                print(f"  - {error}")

        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Data anonymization and EXIF cleaning tool")
    parser.add_argument("--input", type=str, required=True,
                       help="Input directory containing images")
    parser.add_argument("--output", type=str, required=True,
                       help="Output directory for anonymized images")
    parser.add_argument("--hash-filenames", action="store_true",
                       help="Hash filenames for anonymization")
    parser.add_argument("--report-only", action="store_true",
                       help="Only generate report, do not modify files")
    parser.add_argument("--report-output", type=str,
                       default="datasets/processed/anonymization_report.json",
                       help="Output path for anonymization report")
    parser.add_argument("--mapping-output", type=str,
                       default="datasets/processed/filename_mapping.json",
                       help="Output path for filename mapping (only if --hash-filenames)")

    args = parser.parse_args()

    # 验证输入目录
    input_dir = Path(args.input)
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    # 创建输出目录
    output_dir = Path(args.output)

    # 初始化脱敏器
    anonymizer = DataAnonymizer(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        hash_filenames=args.hash_filenames
    )

    # 处理图像
    report = anonymizer.process_images(report_only=args.report_only)

    # 保存报告
    anonymizer.save_report(Path(args.report_output))

    # 如果需要，保存文件名映射
    if args.hash_filenames:
        anonymizer.filename_anonymizer.save_mapping(Path(args.mapping_output))

    # 打印摘要
    anonymizer.print_summary()

    # 检查是否有敏感数据
    if report["exif_analysis"]["images_with_sensitive_data"]:
        logger.warning(f"Found {len(report['exif_analysis']['images_with_sensitive_data'])} "
                      "images with sensitive EXIF data")


if __name__ == "__main__":
    main()
