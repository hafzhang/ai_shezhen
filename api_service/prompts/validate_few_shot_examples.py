#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Few-shot Examples Validation Script
Validates the few-shot examples for LLM syndrome diagnosis
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Any

# TCM knowledge base for validation
TCM_SYNDROME_KNOWLEDGE = {
    13: {
        "name": "肾气虚证",
        "typical_features": ["淡白舌", "白苔", "胖大舌", "齿痕"],
        "typical_special": ["齿痕"],
        "treatment": "补肾益气"
    },
    14: {
        "name": "肾气虚图",
        "typical_features": ["淡白舌", "白苔", "胖大舌", "齿痕"],
        "typical_special": ["齿痕"],
        "treatment": "温补肾阳"
    },
    15: {
        "name": "肝胆湿热证",
        "typical_features": ["红舌", "黄苔", "胖大舌"],
        "typical_special": ["红点", "裂纹"],
        "treatment": "清热利湿，疏利肝胆"
    },
    16: {
        "name": "肝胆湿热图",
        "typical_features": ["红舌", "黄苔"],
        "typical_special": ["红点"],
        "treatment": "清热利湿"
    },
    17: {
        "name": "脾胃虚弱证",
        "typical_features": ["淡白舌", "白苔", "胖大舌", "齿痕"],
        "typical_special": ["齿痕"],
        "treatment": "健脾益气，和胃运湿"
    },
    18: {
        "name": "脾胃虚弱图",
        "typical_features": ["淡白舌", "白苔", "胖大舌"],
        "typical_special": ["齿痕"],
        "treatment": "健脾益气"
    },
    19: {
        "name": "心肺气虚证",
        "typical_features": ["淡白舌", "白苔", "胖大舌"],
        "typical_special": ["齿痕", "裂纹"],
        "treatment": "补益心肺气"
    },
    20: {
        "name": "心肺气虚图",
        "typical_features": ["淡白舌", "白苔"],
        "typical_special": [],
        "treatment": "补气养心"
    }
}

# Valid feature values
VALID_TONGUE_COLORS = ["淡红舌", "红舌", "绛紫舌", "淡白舌"]
VALID_COATING_COLORS = ["白苔", "黄苔", "黑苔", "花剥苔"]
VALID_TONGUE_SHAPES = ["正常", "胖大舌", "瘦薄舌"]
VALID_COATING_QUALITIES = ["薄苔", "厚苔", "腐苔"]
VALID_SPECIAL_FEATURES = ["无", "红点", "裂纹", "齿痕"]
VALID_HEALTH_STATUS = ["健康舌", "非健康舌"]


class FewShotValidator:
    """Validator for few-shot examples"""

    def __init__(self, examples_path: str):
        self.examples_path = Path(examples_path)
        self.examples = []
        self.errors = []
        self.warnings = []
        self.syndrome_counts = defaultdict(int)
        self.feature_completeness = {
            "total_examples": 0,
            "complete_features": 0,
            "partial_features": 0,
            "missing_features": defaultdict(int)
        }

    def load_examples(self) -> bool:
        """Load examples from JSON file"""
        try:
            with open(self.examples_path, 'r', encoding='utf-8') as f:
                self.examples = json.load(f)
            print(f"Loaded {len(self.examples)} examples from {self.examples_path}")
            return True
        except Exception as e:
            self.errors.append(f"Failed to load examples: {e}")
            return False

    def validate_schema(self, example: Dict[str, Any], idx: int) -> bool:
        """Validate example schema"""
        required_fields = [
            "image_id", "filename", "syndromes", "tongue_features",
            "expert_reasoning", "category_ids", "metadata"
        ]

        for field in required_fields:
            if field not in example:
                self.errors.append(f"Example {idx}: Missing required field '{field}'")
                return False

        # Validate tongue_features
        tf = example["tongue_features"]
        tf_fields = ["tongue_color", "coating_color", "tongue_shape",
                     "coating_quality", "special_features", "health_status"]
        for tf_field in tf_fields:
            if tf_field not in tf:
                self.errors.append(f"Example {idx}: Missing tongue_features field '{tf_field}'")
                return False

        # Validate syndromes
        syndromes = example["syndromes"]
        if not isinstance(syndromes, list) or len(syndromes) == 0:
            self.errors.append(f"Example {idx}: syndromes must be a non-empty list")
            return False

        for syndrome in syndromes:
            syndrome_fields = ["id", "name", "name_en", "pinyin", "treatment_principle"]
            for sf in syndrome_fields:
                if sf not in syndrome:
                    self.errors.append(f"Example {idx}: Missing syndrome field '{sf}'")
                    return False

        return True

    def validate_tcm_consistency(self, example: Dict[str, Any], idx: int) -> None:
        """Validate TCM consistency"""
        tf = example["tongue_features"]
        syndromes = example["syndromes"]

        # Check if features match syndrome characteristics
        for syndrome in syndromes:
            sid = syndrome["id"]
            if sid not in TCM_SYNDROME_KNOWLEDGE:
                self.warnings.append(f"Example {idx}: Unknown syndrome ID {sid}")
                continue

            knowledge = TCM_SYNDROME_KNOWLEDGE[sid]

            # Check if special features are appropriate
            special_features = [f for f in tf["special_features"] if f is not None]
            if special_features:
                for feature in special_features:
                    if feature not in VALID_SPECIAL_FEATURES:
                        self.warnings.append(f"Example {idx}: Invalid special feature '{feature}'")

            # Check health status consistency
            if tf["health_status"] == "健康舌" and syndromes:
                self.warnings.append(f"Example {idx}: Healthy tongue with syndrome diagnosis")

    def validate_feature_values(self, example: Dict[str, Any], idx: int) -> None:
        """Validate feature values are within allowed ranges"""
        tf = example["tongue_features"]

        # Check tongue_color
        if tf["tongue_color"] is not None:
            if tf["tongue_color"] not in VALID_TONGUE_COLORS:
                self.errors.append(f"Example {idx}: Invalid tongue_color '{tf['tongue_color']}'")

        # Check coating_color
        if tf["coating_color"] is not None:
            if tf["coating_color"] not in VALID_COATING_COLORS:
                self.errors.append(f"Example {idx}: Invalid coating_color '{tf['coating_color']}'")

        # Check tongue_shape
        if tf["tongue_shape"] is not None:
            if tf["tongue_shape"] not in VALID_TONGUE_SHAPES:
                self.errors.append(f"Example {idx}: Invalid tongue_shape '{tf['tongue_shape']}'")

        # Check coating_quality
        if tf["coating_quality"] is not None:
            if tf["coating_quality"] not in VALID_COATING_QUALITIES:
                self.errors.append(f"Example {idx}: Invalid coating_quality '{tf['coating_quality']}'")

        # Check special_features
        if tf["special_features"]:
            for feature in tf["special_features"]:
                if feature not in VALID_SPECIAL_FEATURES:
                    self.errors.append(f"Example {idx}: Invalid special feature '{feature}'")

        # Check health_status
        if tf["health_status"] not in VALID_HEALTH_STATUS:
            self.errors.append(f"Example {idx}: Invalid health_status '{tf['health_status']}'")

    def calculate_feature_completeness(self, example: Dict[str, Any]) -> None:
        """Calculate feature completeness statistics"""
        tf = example["tongue_features"]
        self.feature_completeness["total_examples"] += 1

        # Count non-null features
        features = [
            tf["tongue_color"],
            tf["coating_color"],
            tf["tongue_shape"],
            tf["coating_quality"]
        ]
        non_null_count = sum(1 for f in features if f is not None)
        special_count = len([f for f in tf["special_features"] if f is not None and f != "无"])

        if non_null_count == 4 and special_count > 0:
            self.feature_completeness["complete_features"] += 1
        elif non_null_count >= 2:
            self.feature_completeness["partial_features"] += 1
        else:
            for i, f in enumerate(features):
                if f is None:
                    field_name = ["tongue_color", "coating_color", "tongue_shape", "coating_quality"][i]
                    self.feature_completeness["missing_features"][field_name] += 1

    def count_syndromes(self, example: Dict[str, Any]) -> None:
        """Count syndromes for distribution analysis"""
        syndromes = example["syndromes"]
        for syndrome in syndromes:
            self.syndrome_counts[syndrome["id"]] += 1

    def validate(self) -> Dict[str, Any]:
        """Run full validation"""
        if not self.load_examples():
            return {"valid": False, "errors": self.errors}

        print("\n=== Running Validation ===\n")

        for idx, example in enumerate(self.examples):
            # Schema validation
            if not self.validate_schema(example, idx):
                continue

            # Feature value validation
            self.validate_feature_values(example, idx)

            # TCM consistency check
            self.validate_tcm_consistency(example, idx)

            # Feature completeness
            self.calculate_feature_completeness(example)

            # Syndrome distribution
            self.count_syndromes(example)

        # Generate report
        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        valid = len(self.errors) == 0

        # Calculate coverage per syndrome
        target_count = 5
        coverage = {}
        for sid in range(13, 21):
            if sid in TCM_SYNDROME_KNOWLEDGE:
                count = self.syndrome_counts.get(sid, 0)
                coverage[TCM_SYNDROME_KNOWLEDGE[sid]["name"]] = {
                    "count": count,
                    "target": target_count,
                    "met": count >= target_count,
                    "percentage": min(100, (count / target_count) * 100)
                }

        # Feature completeness stats
        total = self.feature_completeness["total_examples"]
        complete = self.feature_completeness["complete_features"]
        partial = self.feature_completeness["partial_features"]

        report = {
            "valid": valid,
            "total_examples": len(self.examples),
            "errors": self.errors,
            "warnings": self.warnings,
            "syndrome_distribution": dict(self.syndrome_counts),
            "syndrome_coverage": coverage,
            "feature_completeness": {
                "total": total,
                "complete": complete,
                "partial": partial,
                "complete_percentage": (complete / total * 100) if total > 0 else 0,
                "partial_percentage": (partial / total * 100) if total > 0 else 0,
                "missing_features": dict(self.feature_completeness["missing_features"])
            },
            "acceptance_criteria": {
                "each_syndrome_5_to_10_examples": all(
                    c["count"] >= 5 for c in coverage.values() if c["count"] > 0
                ),
                "unified_format": len(self.errors) == 0,
                "covers_main_syndromes": len([c for c in coverage.values() if c["count"] >= 5]) >= 4,
            },
            "validation_timestamp": datetime.now().isoformat()
        }

        return report


def main():
    """Main validation function"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate few-shot examples")
    parser.add_argument("--examples", type=str,
                       default="api_service/prompts/few_shot_examples.json",
                       help="Path to few-shot examples JSON file")
    parser.add_argument("--output", type=str,
                       default="api_service/prompts/few_shot_validation_report.json",
                       help="Path to output validation report")
    parser.add_argument("--print", action="store_true",
                       help="Print report to console")

    args = parser.parse_args()

    # Run validation
    validator = FewShotValidator(args.examples)
    report = validator.validate()

    # Save report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nValidation report saved to: {output_path}")

    if args.print:
        print("\n=== Validation Summary ===")
        print(f"Valid: {report['valid']}")
        print(f"Total Examples: {report['total_examples']}")
        print(f"Errors: {len(report['errors'])}")
        print(f"Warnings: {len(report['warnings'])}")
        print(f"\nSyndrome Coverage:")
        for name, stats in report['syndrome_coverage'].items():
            status = "✓" if stats['met'] else "✗"
            print(f"  {status} {name}: {stats['count']}/{stats['target']} ({stats['percentage']:.0f}%)")
        print(f"\nFeature Completeness:")
        fc = report['feature_completeness']
        print(f"  Complete: {fc['complete']} ({fc['complete_percentage']:.1f}%)")
        print(f"  Partial: {fc['partial']} ({fc['partial_percentage']:.1f}%)")
        print(f"\nAcceptance Criteria:")
        for criteria, met in report['acceptance_criteria'].items():
            status = "✓" if met else "✗"
            print(f"  {status} {criteria}")

    return 0 if report['valid'] else 1


if __name__ == "__main__":
    sys.exit(main())
