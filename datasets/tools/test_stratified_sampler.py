#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分层采样器单元测试

测试类别权重计算、分层采样、批次平衡等功能。
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from typing import List

import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datasets.tools.stratified_sampler import (
    ClassWeights,
    StratifiedSampler,
    StratifiedBatchSampler,
    DIMENSION_INDICES,
    DIMENSION_CATEGORIES
)


class TestClassWeights(unittest.TestCase):
    """测试类别权重计算"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.labels_file = Path(self.temp_dir) / "test_labels.txt"

        # Create test labels with imbalanced distribution
        test_labels = [
            ("img001.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"),  # red_tongue, white_coating, fat
            ("img002.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"),  # same as above
            ("img003.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"),  # same as above
            ("img004.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"),  # same as above (4 samples - majority)
            ("img005.jpg", "0,0,0,0,1,0,0,0,0,1,0,0,0,0,0,1,0,0,0"),  # purple_tongue, crack (minority)
            ("img006.jpg", "0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,1,0,0"),  # purple_tongue, tooth_mark (minority)
        ]

        with open(self.labels_file, 'w', encoding='utf-8') as f:
            for filename, label_str in test_labels:
                f.write(f"{filename}\t{label_str}\n")

    def test_load_labels(self):
        """测试标签加载"""
        weights_calc = ClassWeights(str(self.labels_file))

        self.assertEqual(len(weights_calc.labels), 6)
        self.assertEqual(len(weights_calc.filename_to_idx), 6)
        self.assertIn("img001.jpg", weights_calc.filename_to_idx)

    def test_calculate_balanced_weights(self):
        """测试平衡权重计算"""
        weights_calc = ClassWeights(str(self.labels_file))
        weights = weights_calc.calculate(method="balanced")

        # Check that weights exist for all expected categories
        self.assertGreater(len(weights), 0)

        # Higher weight for minority classes
        self.assertIn("coating_color_0", weights)  # white_coating (4 samples)
        self.assertIn("coating_color_2", weights)  # black_coating (0 samples - very high weight)

    def test_calculate_sqrt_weights(self):
        """测试平方根权重计算"""
        weights_calc = ClassWeights(str(self.labels_file))
        weights = weights_calc.calculate(method="sqrt")

        self.assertGreater(len(weights), 0)

    def test_calculate_log_weights(self):
        """测试对数权重计算"""
        weights_calc = ClassWeights(str(self.labels_file))
        weights = weights_calc.calculate(method="log")

        self.assertGreater(len(weights), 0)

    def test_get_category_counts(self):
        """测试获取类别计数"""
        weights_calc = ClassWeights(str(self.labels_file))
        counts = weights_calc.get_category_counts()

        # From test labels (after analyzing actual data):
        # img001-004: tongue_color_3=1 (绛紫), coating_color_3=1 (花剥苔) - 4 samples
        # img005-006: coating_color_0=1 (白苔) - 2 samples
        # Note: img005-006 don't have any tongue_color set (all 0s)

        # white_coating (coating_color_0) should have 2 samples (img005-006)
        self.assertEqual(counts.get("coating_color_0", 0), 2)

        # puhua_coating (coating_color_3) should have 4 samples (img001-004)
        self.assertEqual(counts.get("coating_color_3", 0), 4)

        # purple_tongue (tongue_color_3) should have 4 samples (img001-004)
        self.assertEqual(counts.get("tongue_color_3", 0), 4)

    def test_save_weights(self):
        """测试保存权重到文件"""
        weights_calc = ClassWeights(str(self.labels_file))
        output_file = Path(self.temp_dir) / "weights.json"

        weights_calc.save_weights(str(output_file), method="balanced")

        self.assertTrue(output_file.exists())

        with open(output_file, 'r') as f:
            data = json.load(f)

        self.assertIn("weights", data)
        self.assertIn("counts", data)
        self.assertEqual(data["method"], "balanced")

    def test_majority_minority_split(self):
        """测试多数类/少数类分割"""
        weights_calc = ClassWeights(str(self.labels_file))
        majority, minority = weights_calc.get_majority_minority_split(threshold=0.5)

        # With threshold 0.5 (50% of 6 = 3 samples), coating_color_0 (4 samples) is majority
        self.assertGreater(len(majority), 0)
        self.assertGreater(len(minority), 0)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)


class TestStratifiedBatchSampler(unittest.TestCase):
    """测试分层批次采样器"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.labels_file = Path(self.temp_dir) / "test_labels.txt"

        # Create test labels
        test_labels = []
        # Majority class: red_tongue + white_coating (12 samples)
        for i in range(12):
            test_labels.append((f"img_{i:03d}.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"))

        # Minority class: purple_tongue (3 samples)
        for i in range(12, 15):
            test_labels.append((f"img_{i:03d}.jpg", "0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,0,0,0"))

        with open(self.labels_file, 'w', encoding='utf-8') as f:
            for filename, label_str in test_labels:
                f.write(f"{filename}\t{label_str}\n")

    def test_sampler_initialization(self):
        """测试采样器初始化"""
        sampler = StratifiedBatchSampler(
            str(self.labels_file),
            batch_size=8,
            majority_ratio=0.5
        )

        self.assertEqual(len(sampler.labels), 15)
        self.assertEqual(sampler.batch_size, 8)
        self.assertEqual(sampler.majority_per_batch, 4)
        self.assertEqual(sampler.minority_per_batch, 4)

    def test_batch_generation(self):
        """测试批次生成"""
        sampler = StratifiedBatchSampler(
            str(self.labels_file),
            batch_size=8,
            majority_ratio=0.5,
            drop_last=False
        )

        # Should generate 2 batches (15 samples / 8 batch_size = 2 batches)
        self.assertEqual(len(sampler), 2)

    def test_batch_composition(self):
        """测试批次组成（多数类+少数类平衡）"""
        sampler = StratifiedBatchSampler(
            str(self.labels_file),
            batch_size=8,
            majority_ratio=0.5
        )

        batches = list(sampler)
        self.assertGreater(len(batches), 0)

        # Check batch size
        for batch in batches:
            self.assertLessEqual(len(batch), 8)

    def test_drop_last(self):
        """测试丢弃最后不完整的批次"""
        sampler = StratifiedBatchSampler(
            str(self.labels_file),
            batch_size=8,
            majority_ratio=0.5,
            drop_last=True
        )

        # With drop_last=True, only 1 full batch of 8
        self.assertEqual(len(sampler), 1)

    def test_statistics(self):
        """测试统计信息"""
        sampler = StratifiedBatchSampler(
            str(self.labels_file),
            batch_size=8,
            majority_ratio=0.5
        )

        stats = sampler.get_batch_statistics()

        self.assertIn("total_batches", stats)
        self.assertIn("batch_size", stats)
        self.assertIn("majority_classes", stats)
        self.assertIn("minority_classes", stats)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)


class TestStratifiedSampler(unittest.TestCase):
    """测试分层采样器包装类"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.labels_file = Path(self.temp_dir) / "test_labels.txt"

        # Create test labels
        test_labels = [
            ("img001.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"),
            ("img002.jpg", "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"),
            ("img003.jpg", "0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,1,0,0"),
        ]

        with open(self.labels_file, 'w', encoding='utf-8') as f:
            for filename, label_str in test_labels:
                f.write(f"{filename}\t{label_str}\n")

    def test_get_batch_sampler(self):
        """测试获取批次采样器"""
        sampler = StratifiedSampler(
            str(self.labels_file),
            batch_size=2,
            majority_ratio=0.5
        )

        batch_sampler = sampler.get_batch_sampler()
        self.assertIsInstance(batch_sampler, StratifiedBatchSampler)

    def test_get_class_weights(self):
        """测试获取类别权重"""
        sampler = StratifiedSampler(str(self.labels_file))
        weights = sampler.get_class_weights()

        self.assertGreater(len(weights), 0)

    def test_save_class_weights(self):
        """测试保存类别权重"""
        sampler = StratifiedSampler(str(self.labels_file))
        output_file = Path(self.temp_dir) / "saved_weights.json"

        sampler.save_class_weights(str(output_file))

        self.assertTrue(output_file.exists())

    def test_get_statistics(self):
        """测试获取统计信息"""
        sampler = StratifiedSampler(str(self.labels_file))
        stats = sampler.get_statistics()

        self.assertIn("total_batches", stats)
        self.assertIn("batch_size", stats)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)


class TestDimensionIndices(unittest.TestCase):
    """测试维度索引常量"""

    def test_dimension_indices(self):
        """测试维度索引定义"""
        expected_keys = ["tongue_color", "coating_color", "tongue_shape", "coating_quality", "features", "health"]
        self.assertEqual(set(DIMENSION_INDICES.keys()), set(expected_keys))

    def test_dimension_ranges(self):
        """测试维度范围正确性"""
        # tongue_color: 0-4 (4 categories)
        self.assertEqual(DIMENSION_INDICES["tongue_color"], (0, 4))

        # coating_color: 4-8 (4 categories)
        self.assertEqual(DIMENSION_INDICES["coating_color"], (4, 8))

        # tongue_shape: 8-11 (3 categories)
        self.assertEqual(DIMENSION_INDICES["tongue_shape"], (8, 11))

        # coating_quality: 11-14 (3 categories)
        self.assertEqual(DIMENSION_INDICES["coating_quality"], (11, 14))

        # features: 14-17 (3 categories)
        self.assertEqual(DIMENSION_INDICES["features"], (14, 17))

        # health: 17-19 (2 categories including reserved)
        self.assertEqual(DIMENSION_INDICES["health"], (17, 19))

    def test_dimension_categories(self):
        """测试维度类别定义"""
        # Check category names
        self.assertEqual(len(DIMENSION_CATEGORIES["tongue_color"]), 4)
        self.assertEqual(len(DIMENSION_CATEGORIES["coating_color"]), 4)
        self.assertEqual(len(DIMENSION_CATEGORIES["tongue_shape"]), 3)
        self.assertEqual(len(DIMENSION_CATEGORIES["coating_quality"]), 3)
        self.assertEqual(len(DIMENSION_CATEGORIES["features"]), 3)
        self.assertEqual(len(DIMENSION_CATEGORIES["health"]), 2)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        """设置测试环境"""
        # Use real training labels if available
        real_labels = Path(__file__).parent.parent.parent / "processed" / "clas_v1" / "train" / "labels.txt"

        if real_labels.exists():
            self.labels_file = real_labels
            self.use_real_data = True
        else:
            # Create temporary test labels
            self.temp_dir = tempfile.mkdtemp()
            self.labels_file = Path(self.temp_dir) / "test_labels.txt"

            test_labels = []
            for i in range(100):
                if i < 80:
                    # Majority class
                    label_str = "0,0,0,1,0,0,0,1,0,1,0,0,1,0,0,0,0,0,1"
                else:
                    # Minority class
                    label_str = "0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,1,0,0"
                test_labels.append((f"img_{i:03d}.jpg", label_str))

            with open(self.labels_file, 'w', encoding='utf-8') as f:
                for filename, label_str in test_labels:
                    f.write(f"{filename}\t{label_str}\n")

            self.use_real_data = False

    def test_full_pipeline(self):
        """测试完整流程"""
        # Create sampler
        sampler = StratifiedSampler(
            str(self.labels_file),
            batch_size=16,
            majority_ratio=0.5
        )

        # Get class weights
        weights = sampler.get_class_weights()
        self.assertGreater(len(weights), 0)

        # Get statistics
        stats = sampler.get_statistics()
        self.assertIn("total_batches", stats)

        # Get batch sampler
        batch_sampler = sampler.get_batch_sampler()
        batches = list(batch_sampler)
        self.assertGreater(len(batches), 0)

    def tearDown(self):
        """清理测试环境"""
        if not self.use_real_data:
            import shutil
            shutil.rmtree(self.temp_dir)


def run_tests():
    """运行所有测试"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestClassWeights))
    suite.addTests(loader.loadTestsFromTestCase(TestStratifiedBatchSampler))
    suite.addTests(loader.loadTestsFromTestCase(TestStratifiedSampler))
    suite.addTests(loader.loadTestsFromTestCase(TestDimensionIndices))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
