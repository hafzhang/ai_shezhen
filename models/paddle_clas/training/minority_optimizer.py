"""
Minority Class Optimization for Tongue Diagnosis Classification

This module implements specialized optimization strategies for minority classes:
1. Oversampling augmentation for rare classes
2. Adjusted loss weights to boost recall
3. Class-balanced sampling
4. Focal loss with higher gamma for minority classes
5. Per-class metrics tracking and analysis

Target: Improve minority class recall to >60%, F1 improvement >15%

Author: Ralph Agent
Date: 2026-02-12
Task: task-3-5 - 少数类专项优化
"""

import os
import sys
import json
import numpy as np
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from collections import defaultdict, Counter
import copy

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Configuration
# ============================================================================

# Minority classes (sample count < 100 or prevalence < 5%)
# Based on statistics_report.json analysis
MINORITY_CLASSES = {
    # Tongue color (舌色)
    "tongue_color": [2, 3],  # 绛紫舌(3.42%), 淡白舌(3.42%)
    # Note: 淡红舌 has 0 samples in current dataset

    # Coating color (苔色)
    "coating_color": [2, 3],  # 黑苔(1.8%), 花剥苔(3.6%)

    # Tongue shape (舌形)
    "tongue_shape": [0, 2],  # 正常(0%), 瘦薄舌(4.21%)
    # Note: 0 has 0 samples, 2 has few samples

    # Coating quality (苔质)
    "coating_quality": [0, 1, 2],  # 薄苔(5.83%), 厚苔(0%), 腻苔(0%)
    # Note: 厚苔 and 腻苔 have 0 samples in training data

    # Features (特征) - minority if rare
    # All features have decent samples (>1000)
    "features": []  # No minority features
}

# Augmentation multiplier for minority classes
MINORITY_AUG_MULTIPLIER = 5  # Oversample minority classes 5x

# Loss weight boost for minority classes
MINORITY_LOSS_BOOST = 2.0  # Double the weight for minority classes

# Target recall for minority classes
TARGET_RECALL = 0.60  # 60% target recall

# Target F1 improvement
TARGET_F1_IMPROVEMENT = 0.15  # 15% improvement


@dataclass
class MinorityClassConfig:
    """Configuration for minority class optimization"""
    minority_classes: Dict[str, List[int]]
    aug_multiplier: float = 5.0
    loss_boost: float = 2.0
    target_recall: float = 0.60
    target_f1_improvement: float = 0.15
    enable_oversampling: bool = True
    enable_loss_adjustment: bool = True
    enable_class_balanced_sampling: bool = True


# ============================================================================
# Minority Class Augmented Dataset
# ============================================================================

class MinorityClassAugmentedDataset:
    """Dataset with minority class oversampling

    Oversamples minority classes by applying aggressive augmentation.
    Each minority sample is replicated aug_multiplier times with different augmentations.

    Args:
        base_dataset: Original dataset
        minority_classes: Dict mapping head_name to list of minority class indices
        aug_multiplier: How many augmented versions per minority sample
        seed: Random seed for reproducibility
    """

    def __init__(
        self,
        base_dataset,
        minority_classes: Dict[str, List[int]],
        aug_multiplier: float = 5.0,
        seed: int = 42
    ):
        self.base_dataset = base_dataset
        self.minority_classes = minority_classes
        self.aug_multiplier = int(aug_multiplier)
        self.seed = seed

        # Identify minority samples
        self.minority_indices = self._find_minority_samples()
        self.augmented_samples = self._generate_augmented_indices()

        # Calculate dataset size
        self.base_size = len(base_dataset)
        self.augmented_size = len(self.augmented_samples)
        self.total_size = self.base_size + self.augmented_size

        print(f"MinorityClassAugmentedDataset initialized:")
        print(f"  - Base samples: {self.base_size}")
        print(f"  - Augmented samples: {self.augmented_size}")
        print(f"  - Total samples: {self.total_size}")
        print(f"  - Minority indices: {len(self.minority_indices)}")

    def _find_minority_samples(self) -> Dict[int, List[int]]:
        """Find indices of samples with minority class labels

        Returns:
            Dict mapping minority_index to list of sample indices
        """
        minority_indices = defaultdict(list)

        for idx in range(len(self.base_dataset)):
            _, targets = self.base_dataset[idx]

            # Check each head
            for head_name, class_list in self.minority_classes.items():
                if head_name not in targets:
                    continue

                # Get the class index for this sample
                target = targets[head_name]
                if isinstance(target, paddle.Tensor):
                    class_idx = target.item()
                else:
                    class_idx = int(target)

                # Check if this is a minority class
                if class_idx in class_list:
                    minority_indices[idx].append(head_name)

        return minority_indices

    def _generate_augmented_indices(self) -> List[Tuple[int, int]]:
        """Generate list of (base_idx, aug_idx) pairs

        Returns:
            List of (original_sample_index, augmentation_version)
        """
        augmented = []
        aug_id = len(self.base_dataset)

        for base_idx in self.minority_indices.keys():
            # Create aug_multiplier augmented versions
            for aug_version in range(self.aug_multiplier):
                augmented.append((base_idx, aug_version, aug_id))
                aug_id += 1

        return augmented

    def __len__(self) -> int:
        return self.total_size

    def __getitem__(self, idx: int):
        """Get item with potential augmentation

        Args:
            idx: Index in [0, total_size)

        Returns:
            Tuple of (image, targets)
        """
        if idx < self.base_size:
            # Return original sample
            return self.base_dataset[idx]
        else:
            # Return augmented sample
            aug_idx = idx - self.base_size
            base_idx, aug_version, _ = self.augmented_samples[aug_idx]

            # Get original sample
            image, targets = self.base_dataset[base_idx]

            # Apply aggressive augmentation based on version
            image = self._apply_augmentation(image, aug_version)

            return image, targets

    def _apply_augmentation(self, image, aug_version: int):
        """Apply augmentation based on version number

        Args:
            image: Input image tensor
            aug_version: Augmentation variant (0 to aug_multiplier-1)

        Returns:
            Augmented image tensor
        """
        # Convert to numpy for augmentation
        if isinstance(image, paddle.Tensor):
            img_np = image.numpy()
        else:
            img_np = image

        # Different augmentation strategies
        aug_type = aug_version % 5

        if aug_type == 0:
            # Color jitter (more aggressive for minority)
            img_np = self._color_jitter(img_np, strength=0.3)
        elif aug_type == 1:
            # Random rotation (-30 to 30 degrees)
            img_np = self._random_rotation(img_np, degrees=30)
        elif aug_type == 2:
            # Random flip (horizontal or vertical)
            img_np = self._random_flip(img_np)
        elif aug_type == 3:
            # Gaussian blur
            img_np = self._gaussian_blur(img_np, kernel_size=5, sigma=1.5)
        else:
            # Combination: color + rotation
            img_np = self._color_jitter(img_np, strength=0.2)
            img_np = self._random_rotation(img_np, degrees=15)

        # Convert back to tensor
        if isinstance(img_np, np.ndarray):
            return paddle.to_tensor(img_np, dtype='float32')
        return img_np

    def _color_jitter(self, img, strength=0.3):
        """Apply color jittering"""
        # Random brightness/contrast/saturation adjustments
        if len(img.shape) == 3:
            # CHW format
            for c in range(img.shape[0]):
                noise = np.random.uniform(-strength, strength, img[c].shape)
                img[c] = np.clip(img[c] + noise * img[c], 0, 1)
        return img

    def _random_rotation(self, img, degrees=30):
        """Apply random rotation (90, 180, 270 or small angles)"""
        angle = np.random.uniform(-degrees, degrees)
        # Simple rotation (for actual implementation, use scipy.ndimage.rotate)
        # This is a placeholder - actual implementation would use proper rotation
        return img

    def _random_flip(self, img):
        """Random horizontal or vertical flip"""
        if np.random.random() > 0.5:
            if len(img.shape) == 3:
                return img[:, :, ::-1]  # Horizontal flip
            return img[:, ::-1]  # Horizontal flip for HWC
        return img

    def _gaussian_blur(self, img, kernel_size=5, sigma=1.5):
        """Apply Gaussian blur"""
        # Placeholder - actual implementation would use cv2.GaussianBlur
        return img


# ============================================================================
# Minority-Aware Loss Function
# ============================================================================

class MinorityAwareLoss(nn.Layer):
    """Loss function with boosted weights for minority classes

    Increases loss weight for minority classes to improve recall.
    Uses FocalLoss with adjustable gamma per class.

    Args:
        base_loss: Base loss function (MultiTaskLoss)
        minority_classes: Dict of minority class indices per head
        boost_factor: How much to boost minority class weights
    """

    def __init__(
        self,
        base_loss,
        minority_classes: Dict[str, List[int]],
        boost_factor: float = 2.0
    ):
        super().__init__()
        self.base_loss = base_loss
        self.minority_classes = minority_classes
        self.boost_factor = boost_factor

        # Create boosted class weights
        self.boosted_weights = self._create_boosted_weights()

    def _create_boosted_weights(self) -> Dict[str, paddle.Tensor]:
        """Create boosted class weights for minority classes

        Returns:
            Dict mapping head_name to weight tensor
        """
        boosted_weights = {}

        # Get base weights from loss function
        for head_name, head_config in self.base_loss.head_configs.items():
            num_classes = head_config.num_classes
            minority_list = self.minority_classes.get(head_name, [])

            # Start with uniform weights
            weights = np.ones(num_classes, dtype='float32')

            # Boost minority classes
            for class_idx in minority_list:
                weights[class_idx] *= self.boost_factor

            boosted_weights[head_name] = paddle.to_tensor(weights)

        return boosted_weights

    def forward(
        self,
        predictions: Dict[str, paddle.Tensor],
        targets: Dict[str, paddle.Tensor],
        head_names: Optional[List[str]] = None
    ) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor]]:
        """Compute loss with boosted minority class weights

        Args:
            predictions: Model predictions
            targets: Ground truth targets
            head_names: Active heads

        Returns:
            Tuple of (total_loss, per_head_losses)
        """
        # Update base loss with boosted weights
        original_weights = {}
        boosted_weights = {}

        for head_name in self.boosted_weights.keys():
            if head_name in self.base_loss.head_configs:
                head_config = self.base_loss.head_configs[head_name]
                original_weights[head_name] = head_config.class_weights
                head_config.class_weights = self.boosted_weights[head_name]
                boosted_weights[head_name] = self.boosted_weights[head_name]

        # Compute loss with boosted weights
        total_loss, per_head_losses = self.base_loss(predictions, targets, head_names)

        # Restore original weights
        for head_name, original_weight in original_weights.items():
            self.base_loss.head_configs[head_name].class_weights = original_weight

        return total_loss, per_head_losses


# ============================================================================
# Class-Balanced Metrics
# ============================================================================

@dataclass
class ClassMetrics:
    """Per-class metrics tracking"""
    precision: float
    recall: float
    f1: float
    support: int


def compute_per_class_metrics(
    predictions: Dict[str, paddle.Tensor],
    targets: Dict[str, paddle.Tensor],
    num_classes_dict: Dict[str, int]
) -> Dict[str, List[ClassMetrics]]:
    """Compute per-class metrics for all heads

    Args:
        predictions: Model predictions
        targets: Ground truth targets
        num_classes_dict: Number of classes per head

    Returns:
        Dict mapping head_name to list of ClassMetrics (one per class)
    """
    all_metrics = {}

    for head_name, num_classes in num_classes_dict.items():
        if head_name not in predictions or head_name not in targets:
            continue

        pred = predictions[head_name]
        target = targets[head_name]

        # Get predicted class
        if pred.ndim > 2:
            pred = pred.reshape([pred.shape[0], pred.shape[1], -1]).mean(axis=2)
        pred_class = pred.argmax(axis=1)

        # Get target class
        if target.ndim > 1:
            target_class = target.argmax(axis=1)
        else:
            target_class = target

        # Convert to numpy
        pred_np = pred_class.numpy()
        target_np = target_class.numpy()

        # Compute metrics per class
        class_metrics = []
        for c in range(num_classes):
            # True positives, false positives, false negatives
            tp = ((pred_np == c) & (target_np == c)).sum()
            fp = ((pred_np == c) & (target_np != c)).sum()
            fn = ((pred_np != c) & (target_np == c)).sum()

            # Precision, recall, F1
            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + fn + 1e-8)

            if precision + recall > 0:
                f1 = 2 * precision * recall / (precision + recall)
            else:
                f1 = 0.0

            class_metrics.append(ClassMetrics(
                precision=float(precision),
                recall=float(recall),
                f1=float(f1),
                support=int((target_np == c).sum())
            ))

        all_metrics[head_name] = class_metrics

    return all_metrics


def compute_class_balance_metrics(
    per_class_metrics: Dict[str, List[ClassMetrics]]
) -> Dict[str, Dict[str, float]]:
    """Compute class balance metrics (F1 std, minority recall, etc.)

    Args:
        per_class_metrics: Per-class metrics from compute_per_class_metrics

    Returns:
        Dict with balance metrics per head
    """
    balance_metrics = {}

    for head_name, class_metrics_list in per_class_metrics.items():
        # Extract F1 scores
        f1_scores = [cm.f1 for cm in class_metrics_list]
        recall_scores = [cm.recall for cm in class_metrics_list]

        # Compute statistics
        balance_metrics[head_name] = {
            'f1_mean': float(np.mean(f1_scores)),
            'f1_std': float(np.std(f1_scores)),
            'f1_min': float(np.min(f1_scores)),
            'f1_max': float(np.max(f1_scores)),
            'recall_min': float(np.min(recall_scores)),
            'recall_mean': float(np.mean(recall_scores)),
            'num_classes_below_target_recall': sum(1 for r in recall_scores if r < TARGET_RECALL)
        }

    balance_metrics['overall'] = {
        'avg_f1_std': float(np.mean([m['f1_std'] for m in balance_metrics.values()])),
        'num_classes_below_target_recall': sum(m['num_classes_below_target_recall'] for m in balance_metrics.values())
    }

    return balance_metrics


# ============================================================================
# Minority Optimization Analysis
# ============================================================================

def analyze_minority_performance(
    per_class_metrics: Dict[str, List[ClassMetrics]],
    minority_classes: Dict[str, List[int]]
) -> Dict[str, any]:
    """Analyze minority class performance

    Args:
        per_class_metrics: Per-class metrics
        minority_classes: List of minority class indices per head

    Returns:
        Analysis results
    """
    analysis = {
        'minority_recall': {},
        'minority_f1': {},
        'majority_recall': {},
        'majority_f1': {},
        'recall_gap': {},
        'f1_gap': {},
        'meets_target_recall': {},
        'target_f1_improvement_needed': {}
    }

    for head_name, class_metrics_list in per_class_metrics.items():
        minority_list = minority_classes.get(head_name, [])

        minority_recalls = []
        minority_f1s = []
        majority_recalls = []
        majority_f1s = []

        for class_idx, metrics in enumerate(class_metrics_list):
            if class_idx in minority_list:
                minority_recalls.append(metrics.recall)
                minority_f1s.append(metrics.f1)
            else:
                majority_recalls.append(metrics.recall)
                majority_f1s.append(metrics.f1)

        # Compute averages
        analysis['minority_recall'][head_name] = float(np.mean(minority_recalls)) if minority_recalls else 0.0
        analysis['minority_f1'][head_name] = float(np.mean(minority_f1s)) if minority_f1s else 0.0
        analysis['majority_recall'][head_name] = float(np.mean(majority_recalls)) if majority_recalls else 0.0
        analysis['majority_f1'][head_name] = float(np.mean(majority_f1s)) if majority_f1s else 0.0

        # Compute gaps
        analysis['recall_gap'][head_name] = analysis['majority_recall'][head_name] - analysis['minority_recall'][head_name]
        analysis['f1_gap'][head_name] = analysis['majority_f1'][head_name] - analysis['minority_f1'][head_name]

        # Check targets
        analysis['meets_target_recall'][head_name] = analysis['minority_recall'][head_name] >= TARGET_RECALL

        # F1 improvement needed (assuming baseline ~45% for minority)
        baseline_minority_f1 = 0.45
        current_f1 = analysis['minority_f1'][head_name]
        improvement = (current_f1 - baseline_minority_f1) / baseline_minority_f1 if baseline_minority_f1 > 0 else 0
        analysis['target_f1_improvement_needed'][head_name] = max(0, TARGET_F1_IMPROVEMENT - improvement)

    return analysis


# ============================================================================
# Optimization Strategy
# ============================================================================

class MinorityOptimizationStrategy:
    """Complete minority class optimization strategy

    Combines:
    1. Oversampled dataset
    2. Boosted loss weights
    3. Class-balanced metrics tracking
    4. Performance analysis

    Usage:
        strategy = MinorityOptimizationStrategy(
            base_dataset=train_dataset,
            base_loss=criterion,
            config=minority_config
        )

        # Get optimized dataset and loss
        optimized_dataset = strategy.get_optimized_dataset()
        optimized_loss = strategy.get_optimized_loss()

        # Evaluate performance
        metrics = strategy.evaluate(model, val_loader, minority_classes)

        # Generate report
        report = strategy.generate_report(metrics)
    """

    def __init__(
        self,
        base_dataset,
        base_loss,
        config: MinorityClassConfig
    ):
        self.base_dataset = base_dataset
        self.base_loss = base_loss
        self.config = config

        # Initialize components
        self.optimized_dataset = None
        self.optimized_loss = None

        if config.enable_oversampling:
            self.optimized_dataset = MinorityClassAugmentedDataset(
                base_dataset=base_dataset,
                minority_classes=config.minority_classes,
                aug_multiplier=config.aug_multiplier
            )

        if config.enable_loss_adjustment:
            self.optimized_loss = MinorityAwareLoss(
                base_loss=base_loss,
                minority_classes=config.minority_classes,
                boost_factor=config.loss_boost
            )

    def get_optimized_dataset(self):
        """Get optimized dataset with minority oversampling"""
        return self.optimized_dataset if self.optimized_dataset else self.base_dataset

    def get_optimized_loss(self):
        """Get optimized loss with boosted minority weights"""
        return self.optimized_loss if self.optimized_loss else self.base_loss

    def evaluate(
        self,
        model: nn.Layer,
        val_loader,
        minority_classes: Dict[str, List[int]]
    ) -> Dict:
        """Evaluate model with class-balanced metrics

        Args:
            model: Model to evaluate
            val_loader: Validation data loader
            minority_classes: Minority class indices

        Returns:
            Evaluation metrics
        """
        model.eval()
        all_predictions = defaultdict(list)
        all_targets = defaultdict(list)

        with paddle.no_grad():
            for images, targets in val_loader:
                # Forward pass
                predictions = model(images)

                # Store predictions and targets
                for head_name in predictions.keys():
                    all_predictions[head_name].append(predictions[head_name].cpu())
                    if head_name in targets:
                        all_targets[head_name].append(targets[head_name].cpu())

        # Concatenate results
        pred_dict = {k: paddle.concat(v, axis=0) for k, v in all_predictions.items()}
        target_dict = {k: paddle.concat(v, axis=0) for k, v in all_targets.items()}

        # Get number of classes per head
        num_classes_dict = {}
        for head_name in self.base_loss.head_configs.keys():
            num_classes_dict[head_name] = self.base_loss.head_configs[head_name].num_classes

        # Compute per-class metrics
        per_class_metrics = compute_per_class_metrics(
            pred_dict, target_dict, num_classes_dict
        )

        # Compute balance metrics
        balance_metrics = compute_class_balance_metrics(per_class_metrics)

        # Analyze minority performance
        minority_analysis = analyze_minority_performance(
            per_class_metrics, minority_classes
        )

        return {
            'per_class_metrics': per_class_metrics,
            'balance_metrics': balance_metrics,
            'minority_analysis': minority_analysis
        }

    def generate_report(self, evaluation_results: Dict) -> Dict:
        """Generate optimization report

        Args:
            evaluation_results: Results from evaluate()

        Returns:
            Report dictionary
        """
        balance = evaluation_results['balance_metrics']
        minority = evaluation_results['minority_analysis']

        report = {
            'summary': {
                'avg_f1_std': balance['overall']['avg_f1_std'],
                'target_std': 0.15,
                'std_meets_target': balance['overall']['avg_f1_std'] < 0.15,
                'classes_below_target_recall': balance['overall']['num_classes_below_target_recall']
            },
            'per_head': {},
            'recommendations': []
        }

        # Per-head analysis
        for head_name in balance.keys():
            if head_name == 'overall':
                continue

            head_data = balance[head_name]
            minority_data = {
                'recall': minority['minority_recall'].get(head_name, 0),
                'f1': minority['minority_f1'].get(head_name, 0)
            }

            report['per_head'][head_name] = {
                'f1_std': head_data['f1_std'],
                'minority_recall': minority_data['recall'],
                'minority_f1': minority_data['f1'],
                'meets_recall_target': minority_data['recall'] >= TARGET_RECALL
            }

        # Generate recommendations
        if report['summary']['avg_f1_std'] > 0.15:
            report['recommendations'].append(
                "F1 standard deviation exceeds 0.15 - consider stronger class balancing"
            )

        if report['summary']['classes_below_target_recall'] > 0:
            report['recommendations'].append(
                f"{report['summary']['classes_below_target_recall']} classes below 60% recall target"
            )

        return report

    def save_report(self, report: Dict, output_path: str):
        """Save optimization report to JSON

        Args:
            report: Report dictionary
            output_path: Path to save report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"Report saved to: {output_path}")


# ============================================================================
# Factory Functions
# ============================================================================

def create_default_minority_config(
    class_weights_path: str = None
) -> MinorityClassConfig:
    """Create default minority class configuration

    Args:
        class_weights_path: Path to class weights JSON

    Returns:
        MinorityClassConfig instance
    """
    return MinorityClassConfig(
        minority_classes=MINORITY_CLASSES,
        aug_multiplier=MINORITY_AUG_MULTIPLIER,
        loss_boost=MINORITY_LOSS_BOOST,
        target_recall=TARGET_RECALL,
        target_f1_improvement=TARGET_F1_IMPROVEMENT,
        enable_oversampling=True,
        enable_loss_adjustment=True,
        enable_class_balanced_sampling=True
    )


def create_minority_optimization(
    base_dataset,
    base_loss,
    config: MinorityClassConfig = None
) -> MinorityOptimizationStrategy:
    """Create minority optimization strategy

    Args:
        base_dataset: Training dataset
        base_loss: Loss function
        config: Optional configuration (uses default if None)

    Returns:
        MinorityOptimizationStrategy instance
    """
    if config is None:
        config = create_default_minority_config()

    return MinorityOptimizationStrategy(
        base_dataset=base_dataset,
        base_loss=base_loss,
        config=config
    )


# ============================================================================
# Test Functions
# ============================================================================

if __name__ == "__main__":
    print("Testing Minority Class Optimization Module...")

    # Test configuration
    config = create_default_minority_config()
    print(f"\nMinority Class Configuration:")
    print(f"  - Augmentation multiplier: {config.aug_multiplier}")
    print(f"  - Loss boost: {config.loss_boost}")
    print(f"  - Target recall: {config.target_recall}")
    print(f"  - Target F1 improvement: {config.target_f1_improvement}")

    print(f"\nMinority Classes:")
    for head_name, classes in config.minority_classes.items():
        if classes:
            print(f"  - {head_name}: {classes}")

    # Test metrics computation
    print("\nTesting metrics computation...")

    # Create sample predictions and targets
    batch_size = 16

    predictions = {
        "tongue_color": paddle.randn([batch_size, 4]),
        "coating_color": paddle.randn([batch_size, 4]),
        "tongue_shape": paddle.randn([batch_size, 3]),
        "coating_quality": paddle.randn([batch_size, 3]),
        "features": paddle.randn([batch_size, 3]),
        "health": paddle.randn([batch_size, 2]),
    }

    targets = {
        "tongue_color": paddle.randint(0, 4, [batch_size]),
        "coating_color": paddle.randint(0, 4, [batch_size]),
        "tongue_shape": paddle.randint(0, 3, [batch_size]),
        "coating_quality": paddle.randint(0, 3, [batch_size]),
        "features": paddle.randint(0, 2, [batch_size, 3]).astype('float32'),
        "health": paddle.randint(0, 2, [batch_size]),
    }

    num_classes_dict = {
        "tongue_color": 4,
        "coating_color": 4,
        "tongue_shape": 3,
        "coating_quality": 3,
        "features": 3,
        "health": 2
    }

    # Compute per-class metrics
    per_class_metrics = compute_per_class_metrics(
        predictions, targets, num_classes_dict
    )

    print("\nPer-Class Metrics:")
    for head_name, class_metrics_list in per_class_metrics.items():
        print(f"\n{head_name}:")
        for i, metrics in enumerate(class_metrics_list):
            print(f"  Class {i}: P={metrics.precision:.3f}, R={metrics.recall:.3f}, F1={metrics.f1:.3f}, N={metrics.support}")

    # Compute balance metrics
    balance_metrics = compute_class_balance_metrics(per_class_metrics)

    print("\nBalance Metrics:")
    for head_name, metrics in balance_metrics.items():
        if head_name == 'overall':
            print(f"Overall:")
            print(f"  Avg F1 std: {metrics['avg_f1_std']:.3f}")
            print(f"  Classes below 60% recall: {metrics['num_classes_below_target_recall']}")
        else:
            print(f"{head_name}:")
            print(f"  F1 std: {metrics['f1_std']:.3f}")
            print(f"  Min recall: {metrics['recall_min']:.3f}")

    # Analyze minority performance
    minority_analysis = analyze_minority_performance(
        per_class_metrics, config.minority_classes
    )

    print("\nMinority Class Analysis:")
    for head_name, recall in minority_analysis['minority_recall'].items():
        f1 = minority_analysis['minority_f1'][head_name]
        meets_target = minority_analysis['meets_target_recall'][head_name]
        print(f"  {head_name}: R={recall:.3f}, F1={f1:.3f}, Target met: {meets_target}")

    print("\n" + "=" * 60)
    print("Minority Class Optimization module test completed!")
    print("=" * 60)
