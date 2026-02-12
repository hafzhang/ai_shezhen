#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
证型诊断数据集构建脚本

提取证型标签（13-20类），构建图文对（舌象特征向量+证型标签+专家辨证依据），
筛选典型病例用于Few-shot Prompt。

证型类别（13-20）：
- 13: shenquao (肾气虚证)
- 14: shenqutu (肾气虚图)
- 15: gandanao (肝胆湿热证)
- 16: gandantu (肝胆湿热图)
- 17: piweiao (脾胃虚弱证)
- 18: piweitu (脾胃虚弱图)
- 19: xinfeiao (心肺气虚证)
- 20: xinfeitu (心肺气虚图)

Usage:
    python datasets/tools/build_syndrome_dataset.py --data_root path/to/shezhenv3-coco --split train
    python datasets/tools/build_syndrome_dataset.py --all
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict, Counter
from copy import deepcopy
from datetime import datetime

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


# ==================== Syndrome Class Definitions ====================

# Original 21 classes
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

# Syndrome class IDs (13-20)
SYNDROME_IDS = list(range(13, 21))

# Syndrome information (TCM knowledge base)
SYNDROME_INFO = {
    13: {
        "name": "肾气虚证",
        "name_en": "Kidney Qi Deficiency",
        "pinyin": "shenqixu",
        "key_features": ["腰膝酸软", "乏力", "耳鸣", "小便清长"],
        "tongue_features": ["舌淡", "苔白", "舌体胖大", "齿痕"],
        "diagnosis_basis": "肾气不足，气化失常，舌体失养",
        "treatment_principle": "补肾益气"
    },
    14: {
        "name": "肾气虚图",
        "name_en": "Kidney Qi Deficiency Pattern",
        "pinyin": "shenqixutu",
        "key_features": ["腰膝酸软", "畏寒肢冷"],
        "tongue_features": ["舌质淡", "苔薄白", "舌体胖嫩"],
        "diagnosis_basis": "肾阳不足，温煦失职",
        "treatment_principle": "温补肾阳"
    },
    15: {
        "name": "肝胆湿热证",
        "name_en": "Liver-Gallbladder Damp-Heat",
        "pinyin": "gandanshire",
        "key_features": ["口苦", "咽干", "烦躁", "身目发黄"],
        "tongue_features": ["舌红", "苔黄腻", "舌边尖红"],
        "diagnosis_basis": "湿热蕴结肝胆，疏泄失常",
        "treatment_principle": "清热利湿，疏利肝胆"
    },
    16: {
        "name": "肝胆湿热图",
        "name_en": "Liver-Gallbladder Damp-Heat Pattern",
        "pinyin": "gandanshiretu",
        "key_features": ["胁肋胀痛", "口苦"],
        "tongue_features": ["舌质红", "苔黄厚腻"],
        "diagnosis_basis": "肝胆湿热内蕴",
        "treatment_principle": "清热利湿"
    },
    17: {
        "name": "脾胃虚弱证",
        "name_en": "Spleen-Stomach Weakness",
        "pinyin": "piweixuruo",
        "key_features": ["腹胀", "便溏", "食欲不振", "乏力"],
        "tongue_features": ["舌淡", "苔白腻", "舌体胖大有齿痕", "舌质嫩"],
        "diagnosis_basis": "脾胃运化失司，气血生化不足",
        "treatment_principle": "健脾益气，和胃运湿"
    },
    18: {
        "name": "脾胃虚弱图",
        "name_en": "Spleen-Stomach Weakness Pattern",
        "pinyin": "piweixuruotu",
        "key_features": ["消化不良", "面色萎黄"],
        "tongue_features": ["舌质淡胖", "苔白滑"],
        "diagnosis_basis": "中气不足，运化无力",
        "treatment_principle": "补中益气"
    },
    19: {
        "name": "心肺气虚证",
        "name_en": "Heart-Lung Qi Deficiency",
        "pinyin": "xinfeiqixu",
        "key_features": ["心悸", "气短", "自汗", "易感冒"],
        "tongue_features": ["舌淡", "苔薄白", "舌体胖大"],
        "diagnosis_basis": "心肺气虚，血行不畅，呼吸无力",
        "treatment_principle": "补益心肺气"
    },
    20: {
        "name": "心肺气虚图",
        "name_en": "Heart-Lung Qi Deficiency Pattern",
        "pinyin": "xinfeiqixutu",
        "key_features": ["胸闷", "气促"],
        "tongue_features": ["舌质淡白", "苔薄白"],
        "diagnosis_basis": "心肺两脏气虚",
        "treatment_principle": "补气养心"
    }
}

# Mapping from non-syndrome class IDs to feature names
FEATURE_CLASS_NAMES = {
    0: "健康舌",
    1: "薄苔",
    2: "红舌",
    3: "绛紫舌",
    4: "胖大舌",
    5: "瘦薄舌",
    6: "红点",
    7: "裂纹",
    8: "齿痕",
    9: "白苔",
    10: "黄苔",
    11: "黑苔",
    12: "花剥苔"
}

# Dimension mapping for feature extraction
DIMENSION_MAPPING = {
    "tongue_color": {
        2: "红舌",
        3: "绛紫舌",
        "default": "淡白舌"
    },
    "coating_color": {
        9: "白苔",
        10: "黄苔",
        11: "黑苔",
        12: "花剥苔"
    },
    "tongue_shape": {
        4: "胖大舌",
        5: "瘦薄舌",
        "default": "正常舌形"
    },
    "features": {
        6: "红点",
        7: "裂纹",
        8: "齿痕"
    },
    "coating_quality": {
        1: "薄苔"
    }
}


# ==================== Syndrome Dataset Builder ====================

class SyndromeDatasetBuilder:
    """证型诊断数据集构建器"""

    def __init__(self, data_root: str, output_base: str = None):
        """
        初始化构建器

        Args:
            data_root: COCO数据集根目录
            output_base: 输出基础目录 (默认: datasets/processed/syndrome_cases)
        """
        self.data_root = Path(data_root)
        if output_base is None:
            output_base = Path(__file__).parent.parent.parent / "processed" / "syndrome_cases"
        else:
            output_base = Path(output_base)

        self.output_base = output_base
        self.output_base.mkdir(parents=True, exist_ok=True)

        # Create prompts directory
        self.prompts_dir = self.output_base / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        self.stats = {
            "total_images": 0,
            "syndrome_images": 0,
            "syndrome_distribution": defaultdict(int),
            "multi_syndrome_count": 0,
            "feature_distribution": defaultdict(int),
            "selected_typical_cases": defaultdict(int)
        }

    def extract_features(self, category_ids: List[int]) -> Dict[str, Any]:
        """
        从类别ID列表中提取舌象特征

        Args:
            category_ids: 原始类别ID列表

        Returns:
            特征字典
        """
        features = {
            "tongue_color": None,
            "coating_color": None,
            "tongue_shape": None,
            "coating_quality": None,
            "special_features": [],
            "health_status": "非健康舌"
        }

        # Filter out syndrome IDs
        non_syndrome_ids = [cid for cid in category_ids if cid not in SYNDROME_IDS]

        for cat_id in non_syndrome_ids:
            if cat_id == 0:
                features["health_status"] = "健康舌"
            elif cat_id in DIMENSION_MAPPING["tongue_color"]:
                features["tongue_color"] = DIMENSION_MAPPING["tongue_color"][cat_id]
            elif cat_id in DIMENSION_MAPPING["coating_color"]:
                features["coating_color"] = DIMENSION_MAPPING["coating_color"][cat_id]
            elif cat_id in DIMENSION_MAPPING["tongue_shape"]:
                features["tongue_shape"] = DIMENSION_MAPPING["tongue_shape"][cat_id]
            elif cat_id in DIMENSION_MAPPING["features"]:
                feature_name = DIMENSION_MAPPING["features"][cat_id]
                # Avoid duplicates in special_features
                if feature_name not in features["special_features"]:
                    features["special_features"].append(feature_name)
            elif cat_id in DIMENSION_MAPPING["coating_quality"]:
                features["coating_quality"] = DIMENSION_MAPPING["coating_quality"][cat_id]

        return features

    def generate_expert_reasoning(self, syndrome_id: int, features: Dict[str, Any]) -> str:
        """
        生成专家辨证依据

        Args:
            syndrome_id: 证型ID
            features: 舌象特征字典

        Returns:
            专家辨证依据文本
        """
        info = SYNDROME_INFO.get(syndrome_id, {})
        syndrome_name = info.get("name", f"证型{syndrome_id}")
        diagnosis_basis = info.get("diagnosis_basis", "")
        key_features = info.get("tongue_features", [])

        # Build reasoning text
        reasoning_parts = []

        # Start with observed features
        observed_features = []
        if features.get("tongue_color"):
            observed_features.append(f"舌色{features['tongue_color']}")
        if features.get("coating_color"):
            observed_features.append(f"苔色{features['coating_color']}")
        if features.get("tongue_shape"):
            observed_features.append(f"舌形{features['tongue_shape']}")
        if features.get("special_features"):
            observed_features.extend(features["special_features"])

        if observed_features:
            reasoning_parts.append(f"【舌象观察】{', '.join(observed_features)}")

        # Add syndrome-specific reasoning
        if key_features:
            reasoning_parts.append(f"【典型特征】{syndrome_name}典型舌象表现为：{', '.join(key_features)}")

        # Add diagnosis basis
        if diagnosis_basis:
            reasoning_parts.append(f"【辨证分析】{diagnosis_basis}")

        # Add treatment principle
        treatment = info.get("treatment_principle", "")
        if treatment:
            reasoning_parts.append(f"【治则】{treatment}")

        return "\n".join(reasoning_parts)

    def build_case_entry(self, image_info: Dict, syndrome_ids: List[int],
                       all_category_ids: List[int]) -> Dict[str, Any]:
        """
        构建单个病例条目

        Args:
            image_info: COCO图像信息
            syndrome_ids: 该图像的证型ID列表
            all_category_ids: 所有类别ID列表

        Returns:
            病例字典
        """
        filename = image_info["file_name"]
        image_id = image_info["id"]

        # Extract features
        features = self.extract_features(all_category_ids)

        # Generate syndrome information
        syndromes = []
        for sid in syndrome_ids:
            syndrome_info = SYNDROME_INFO.get(sid, {})
            syndromes.append({
                "id": sid,
                "name": syndrome_info.get("name", f"证型{sid}"),
                "name_en": syndrome_info.get("name_en", ""),
                "pinyin": syndrome_info.get("pinyin", ""),
                "treatment_principle": syndrome_info.get("treatment_principle", "")
            })

        # Generate expert reasoning for primary syndrome
        primary_syndrome_id = syndrome_ids[0]
        expert_reasoning = self.generate_expert_reasoning(primary_syndrome_id, features)

        # Build case entry
        case = {
            "image_id": image_id,
            "filename": filename,
            "syndromes": syndromes,
            "tongue_features": {
                "tongue_color": features.get("tongue_color"),
                "coating_color": features.get("coating_color"),
                "tongue_shape": features.get("tongue_shape"),
                "coating_quality": features.get("coating_quality"),
                "special_features": features.get("special_features", []),
                "health_status": features.get("health_status")
            },
            "expert_reasoning": expert_reasoning,
            "category_ids": all_category_ids,
            "metadata": {
                "width": image_info.get("width", 0),
                "height": image_info.get("height", 0)
            }
        }

        return case

    def select_typical_cases(self, cases: List[Dict], target_per_syndrome: int = 10) -> List[Dict]:
        """
        筛选典型病例用于Few-shot Prompt

        优先选择：
        1. 单证型病例（避免多证型混淆）
        2. 特征明显的病例（有多个特征标注）
        3. 每个证型均匀分布

        Args:
            cases: 所有病例列表
            target_per_syndrome: 每个证型目标病例数

        Returns:
            精选典型病例列表
        """
        # Group by primary syndrome
        syndrome_cases = defaultdict(list)
        for case in cases:
            if case["syndromes"]:
                primary_syndrome = case["syndromes"][0]["id"]
                syndrome_cases[primary_syndrome].append(case)

        # Select top cases per syndrome
        typical_cases = []

        for syndrome_id, case_list in syndrome_cases.items():
            # Sort by feature count (more features = more typical)
            case_list.sort(
                key=lambda x: (
                    len(x["tongue_features"]["special_features"]) +
                    (1 if x["tongue_features"]["tongue_color"] else 0) +
                    (1 if x["tongue_features"]["coating_color"] else 0) +
                    (1 if x["tongue_features"]["tongue_shape"] else 0)
                ),
                reverse=True
            )

            # Select top cases
            selected = case_list[:target_per_syndrome]
            typical_cases.extend(selected)

            self.stats["selected_typical_cases"][syndrome_id] = len(selected)

        return typical_cases

    def process_split(self, split: str = "train") -> Dict[str, Any]:
        """
        处理单个数据集划分

        Args:
            split: train/val/test

        Returns:
            处理结果统计
        """
        logger.info(f"Processing {split} split...")

        # Load COCO annotations
        annotation_file = self.data_root / split / "annotations" / f"{split}.json"
        if not annotation_file.exists():
            logger.error(f"Annotation file not found: {annotation_file}")
            return None

        coco = COCO(str(annotation_file))

        # Find all images with syndrome labels
        cases = []
        syndrome_distribution = defaultdict(int)

        for img_info in tqdm(coco.dataset["images"], desc=f"Processing {split}"):
            img_id = img_info["id"]
            ann_ids = coco.getAnnIds(imgIds=[img_id])
            anns = coco.loadAnns(ann_ids)

            if not anns:
                continue

            category_ids = [ann["category_id"] for ann in anns]
            syndrome_ids = [cid for cid in category_ids if cid in SYNDROME_IDS]

            if not syndrome_ids:
                continue

            # Build case entry
            case = self.build_case_entry(img_info, syndrome_ids, category_ids)
            cases.append(case)

            # Update statistics
            for sid in syndrome_ids:
                syndrome_distribution[sid] += 1
            if len(syndrome_ids) > 1:
                self.stats["multi_syndrome_count"] += 1

        self.stats["total_images"] = len(coco.dataset["images"])
        self.stats["syndrome_images"] = len(cases)
        for sid, count in syndrome_distribution.items():
            self.stats["syndrome_distribution"][sid] += count

        # Save all cases
        output_file = self.output_base / f"{split}_syndrome_cases.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(cases)} cases to {output_file}")

        # Select and save typical cases for few-shot learning
        typical_cases = self.select_typical_cases(cases, target_per_syndrome=10)
        typical_file = self.output_base / f"{split}_few_shot_examples.json"
        with open(typical_file, "w", encoding="utf-8") as f:
            json.dump(typical_cases, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(typical_cases)} typical cases to {typical_file}")

        return {
            "split": split,
            "total_images": len(coco.dataset["images"]),
            "syndrome_cases": len(cases),
            "typical_cases": len(typical_cases),
            "syndrome_distribution": dict(syndrome_distribution)
        }

    def build_few_shot_prompt_template(self) -> str:
        """
        构建Few-shot Prompt模板

        Returns:
            Prompt模板字符串
        """
        template = """# 舌诊中医辨证诊断助手

你是一位经验丰富的中医舌诊专家，擅长通过舌象图片进行辨证分析。

## 辨证流程

1. **舌象观察**：仔细观察舌色、舌苔、舌形等特征
2. **特征提取**：识别舌象中的关键特征（舌色、苔色、舌形、特殊征象）
3. **辨证分析**：根据舌象特征，结合中医理论进行分析
4. **证型判断**：确定主要证型及相关证型
5. **给出建议**：提供治则建议

## 输出格式

请严格按照以下JSON格式输出：

```json
{
  "tongue_features": {
    "tongue_color": "舌色描述",
    "coating_color": "苔色描述",
    "tongue_shape": "舌形描述",
    "special_features": ["特殊征象1", "特殊征象2"]
  },
  "syndrome_diagnosis": {
    "primary_syndrome": "主要证型",
    "secondary_syndromes": ["次要证型"],
    "diagnosis_basis": "辨证依据",
    "treatment_principle": "治则建议"
  },
  "health_status": "健康/亚健康/不健康",
  "confidence": 0.85
}
```

## 注意事项

- 仅根据舌象特征进行判断，不涉及其他症状
- 对于特征不明显的病例，confidence应相应降低
- 如果舌象正常，应判断为健康舌
- 重点关注舌色、苔色、舌形三大要素
"""
        return template

    def save_prompt_template(self):
        """保存Prompt模板到文件"""
        template = self.build_few_shot_prompt_template()

        template_file = self.prompts_dir / "system_prompt.txt"
        with open(template_file, "w", encoding="utf-8") as f:
            f.write(template)

        logger.info(f"Saved prompt template to {template_file}")

        # Also save as JSON for programmatic use
        json_file = self.prompts_dir / "few_shot_examples.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({"system_prompt": template}, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved prompt template to {json_file}")

    def generate_report(self) -> Dict[str, Any]:
        """
        生成数据集构建报告

        Returns:
            报告字典
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_images": self.stats["total_images"],
                "syndrome_images": self.stats["syndrome_images"],
                "coverage_rate": f"{self.stats['syndrome_images'] / max(self.stats['total_images'], 1) * 100:.2f}%"
            },
            "syndrome_distribution": {},
            "typical_cases_selected": {},
            "multi_syndrome_cases": self.stats["multi_syndrome_count"]
        }

        # Format syndrome distribution
        for sid in sorted(self.stats["syndrome_distribution"].keys()):
            info = SYNDROME_INFO.get(sid, {})
            report["syndrome_distribution"][sid] = {
                "id": sid,
                "name": info.get("name", f"证型{sid}"),
                "name_en": info.get("name_en", ""),
                "count": self.stats["syndrome_distribution"][sid],
                "key_features": info.get("key_features", []),
                "treatment_principle": info.get("treatment_principle", "")
            }

        # Format typical cases
        for sid in sorted(self.stats["selected_typical_cases"].keys()):
            info = SYNDROME_INFO.get(sid, {})
            report["typical_cases_selected"][sid] = {
                "id": sid,
                "name": info.get("name", f"证型{sid}"),
                "count": self.stats["selected_typical_cases"][sid]
            }

        return report

    def save_report(self, report: Dict[str, Any]):
        """
        保存报告到JSON文件

        Args:
            report: 报告字典
        """
        report_file = self.output_base / "syndrome_dataset_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved report to {report_file}")


# ==================== Main Execution ====================

def main():
    parser = argparse.ArgumentParser(description="构建证型诊断数据集")
    parser.add_argument("--data_root", type=str, default="shezhenv3-coco",
                        help="COCO数据集根目录")
    parser.add_argument("--split", type=str, default="train",
                        choices=["train", "val", "test", "all"],
                        help="数据集划分")
    parser.add_argument("--output_base", type=str, default=None,
                        help="输出目录")

    args = parser.parse_args()

    # Initialize builder
    builder = SyndromeDatasetBuilder(args.data_root, args.output_base)

    # Process splits
    splits = ["train", "val", "test"] if args.split == "all" else [args.split]

    for split in splits:
        result = builder.process_split(split)
        if result:
            logger.info(f"{split} split complete: {result}")

    # Save prompt template
    builder.save_prompt_template()

    # Generate and save report
    report = builder.generate_report()
    builder.save_report(report)

    logger.info("=" * 60)
    logger.info("证型诊断数据集构建完成")
    logger.info(f"总计证型样本: {builder.stats['syndrome_images']}")
    logger.info(f"多证型样本: {builder.stats['multi_syndrome_count']}")
    logger.info(f"精选典型病例: {sum(builder.stats['selected_typical_cases'].values())}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
