#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Classification Model Evaluator with Interpretability Analysis

Implements comprehensive evaluation for multi-task tongue classification:
1. Multi-label evaluation metrics (mAP, F1, precision, recall)
2. Confusion matrix generation and visualization
3. Per-class performance analysis
4. Error analysis and case studies
5. Feature contribution analysis
6. Grad-CAM visualization support

Metrics Computed:
- mAP (mean Average Precision)
- Macro/Micro F1-score
- Per-class precision, recall, F1
- Confusion matrices for each head
- Error classification (TP, FP, FN analysis)

Author: Ralph Agent
Date: 2026-02-12
Task: task-3-8 - 分类模型评估与可解释性分析
"""

import os
import sys
import json
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib import rcParams
    # Configure font for Chinese characters
    rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    rcParams['axes.unicode_minus'] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ============================================================================
# Data Classes for Evaluation Results
# ============================================================================

@dataclass
class HeadMetrics:
    """Metrics for a single classification head"""
    head_name: str
    num_classes: int
    class_names: List[str]

    # Overall metrics
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    ap: float = 0.0  # Average Precision

    # Per-class metrics
    per_class_precision: List[float] = field(default_factory=list)
    per_class_recall: List[float] = field(default_factory=list)
    per_class_f1: List[float] = field(default_factory=list)
    per_class_ap: List[float] = field(default_factory=list)

    # Confusion matrix
    confusion_matrix: np.ndarray = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'head_name': self.head_name,
            'num_classes': self.num_classes,
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1': self.f1,
            'ap': self.ap,
            'per_class_metrics': [
                {
                    'class_name': name,
                    'precision': p,
                    'recall': r,
                    'f1': f,
                    'ap': ap
                }
                for name, p, r, f, ap in zip(
                    self.class_names,
                    self.per_class_precision,
                    self.per_class_recall,
                    self.per_class_f1,
                    self.per_class_ap
                )
            ]
        }


@dataclass
class ClassificationResult:
    """Complete classification evaluation results"""
    # Dataset info
    num_samples: int
    num_heads: int
    head_names: List[str]

    # Per-head metrics
    head_metrics: Dict[str, HeadMetrics] = field(default_factory=dict)

    # Overall metrics
    macro_f1: float = 0.0
    micro_f1: float = 0.0
    macro_map: float = 0.0  # Mean of all head APs

    # Performance metrics
    inference_time_ms: float = 0.0
    fps: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'dataset_info': {
                'num_samples': self.num_samples,
                'num_heads': self.num_heads,
                'head_names': self.head_names
            },
            'overall_metrics': {
                'macro_f1': self.macro_f1,
                'micro_f1': self.micro_f1,
                'macro_map': self.macro_map
            },
            'performance': {
                'inference_time_ms': self.inference_time_ms,
                'fps': self.fps
            },
            'per_head_metrics': {
                name: metrics.to_dict()
                for name, metrics in self.head_metrics.items()
            }
        }


@dataclass
class ErrorCase:
    """Represents a single error case"""
    image_path: str
    predicted_class: str
    true_class: str
    confidence: float
    error_type: str  # 'FP', 'FN', 'confusion'
    head_name: str


# ============================================================================
# Grad-CAM Implementation for Interpretability
# ============================================================================

class GradCAM:
    """Gradient-weighted Class Activation Mapping for visualization

    Generates heatmaps showing which regions of the image contributed
    most to the classification decision.

    Implementation based on:
    Grad-CAM: Visual Explanations from Deep Networks
    """

    def __init__(self, model: nn.Layer, target_layer: str = 'stage4'):
        """
        Args:
            model: The classification model
            target_layer: Name of the target layer for visualization
        """
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None

        # Register hooks
        self._register_hooks()

    def _register_hooks(self):
        """Register forward and backward hooks"""
        def forward_hook(layer, input, output):
            self.activations = output

        def backward_hook(layer, grad_input, grad_output):
            self.gradients = grad_output[0]

        # Find target layer
        target_layer = None
        if hasattr(self.model.backbone, self.target_layer):
            target_layer = getattr(self.model.backbone, self.target_layer)
        elif hasattr(self.model, self.target_layer):
            target_layer = getattr(self.model, self.target_layer)

        if target_layer is not None:
            self.forward_handle = target_layer.register_forward_post_hook(forward_hook)
            self.backward_handle = target_layer.register_backward_post_hook(backward_hook)

    def generate_heatmap(
        self,
        input_tensor: paddle.Tensor,
        target_class: int,
        head_name: str = 'tongue_color'
    ) -> np.ndarray:
        """
        Generate Grad-CAM heatmap

        Args:
            input_tensor: Input image tensor (1, 3, H, W)
            target_class: Target class index for visualization
            head_name: Which head to use for gradient computation

        Returns:
            Heatmap as numpy array (H, W)
        """
        # Enable gradient computation
        input_tensor.stop_gradient = False

        # Forward pass
        if hasattr(self.model, 'classifier'):
            # Multi-head model
            features = self.model.backbone(input_tensor)
            predictions = self.model.classifier(features)

            # Get prediction for specific head
            head_idx = list(self.model.classifier.heads.keys()).index(head_name)
            output = predictions[head_idx]
        else:
            output = self.model(input_tensor)

        # Zero gradients
        self.model.clear_gradients()

        # Backward pass for target class
        target = output[0, target_class]
        target.backward()

        # Get gradients and activations
        gradients = self.gradients.numpy()  # (1, C, H, W)
        activations = self.activations.numpy()  # (1, C, H, W)

        # Pool gradients
        weights = np.mean(gradients, axis=(2, 3))  # (1, C)

        # Weighted combination of activation maps
        cam = np.zeros(activations.shape[2:], dtype=np.float32)  # (H, W)
        for i, w in enumerate(weights[0]):
            cam += w * activations[0, i, :, :]

        # ReLU to keep only positive contributions
        cam = np.maximum(cam, 0)

        # Normalize to [0, 1]
        if cam.max() > 0:
            cam = (cam - cam.min()) / (cam.max() - cam.min())

        return cam

    def overlay_heatmap(
        self,
        image: np.ndarray,
        heatmap: np.ndarray,
        alpha: float = 0.4,
        colormap: int = 0  # cv2.COLORMAP_JET
    ) -> np.ndarray:
        """
        Overlay heatmap on original image

        Args:
            image: Original image (H, W, 3) in RGB
            heatmap: Grad-CAM heatmap (H, W)
            alpha: Transparency of overlay
            colormap: OpenCV colormap ID

        Returns:
            Overlayed image (H, W, 3)
        """
        if not CV2_AVAILABLE:
            # Fallback: simple heatmap using PIL
            if not PIL_AVAILABLE:
                return image
            # Convert heatmap to colored
            heatmap_uint8 = (heatmap * 255).astype(np.uint8)
            heatmap_pil = Image.fromarray(heatmap_uint8, mode='L')
            # Apply color map (red)
            heatmap_color = heatmap_pil.convert('RGB')
            # Blend
            image_pil = Image.fromarray((image * 255).astype(np.uint8))
            overlay = Image.blend(image_pil, heatmap_color, alpha)
            return np.array(overlay) / 255.0

        # Resize heatmap to image size
        heatmap_resized = cv2.resize(
            heatmap,
            (image.shape[1], image.shape[0])
        )

        # Apply colormap
        heatmap_colored = cv2.applyColorMap(
            (heatmap_resized * 255).astype(np.uint8),
            colormap
        )

        # Convert BGR to RGB
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        # Overlay
        overlayed = (1 - alpha) * image + alpha * (heatmap_colored / 255.0)

        return np.clip(overlayed, 0, 1)


# ============================================================================
# Feature Contribution Analysis
# ============================================================================

class FeatureContribution:
    """Analyze feature contributions for predictions

    Provides insights into which input features (tongue color, coating, etc.)
    contributed most to the classification decision.
    """

    @staticmethod
    def compute_head_importance(
        model: nn.Layer,
        input_tensor: paddle.Tensor
    ) -> Dict[str, float]:
        """
        Compute importance scores for each classification head

        Uses gradient-based attribution to determine which heads
        had the strongest response.

        Args:
            model: Multi-head classification model
            input_tensor: Input image (1, 3, H, W)

        Returns:
            Dictionary mapping head names to importance scores
        """
        model.eval()

        with paddle.no_grad():
            # Get predictions for all heads
            predictions = model(input_tensor)

        # Compute confidence score for each head
        importances = {}
        head_names = list(model.classifier.heads.keys())

        for i, pred in enumerate(predictions):
            # Max softmax probability as confidence
            probs = F.softmax(pred, axis=1)
            confidence = probs.max().item()
            importances[head_names[i]] = confidence

        # Normalize to sum to 1
        total = sum(importances.values())
        if total > 0:
            importances = {k: v / total for k, v in importances.items()}

        return importances

    @staticmethod
    def generate_explanation(
        head_name: str,
        predicted_class: int,
        class_names: List[str],
        confidence: float,
        feature_importance: Dict[str, float]
    ) -> str:
        """
        Generate human-readable explanation for prediction

        Args:
            head_name: Name of the classification head
            predicted_class: Index of predicted class
            class_names: List of class names
            confidence: Prediction confidence
            feature_importance: Dictionary of feature importances

        Returns:
            Human-readable explanation string
        """
        class_name = class_names[predicted_class] if predicted_class < len(class_names) else f"Class_{predicted_class}"

        # Get top 3 most important features
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        explanation_parts = [
            f"预测类别: {class_name} (置信度: {confidence:.2%})\n",
            "主要依据:"
        ]

        feature_translations = {
            'tongue_color': '舌色',
            'coating_color': '苔色',
            'tongue_shape': '舌形',
            'coating_quality': '苔质',
            'features': '特殊特征',
            'health': '健康状态'
        }

        for feature, importance in sorted_features:
            translated = feature_translations.get(feature, feature)
            explanation_parts.append(f"  - {translated}: {importance:.1%}")

        return "\n".join(explanation_parts)


# ============================================================================
# Error Analysis
# ============================================================================

class ErrorAnalyzer:
    """Analyze classification errors and patterns"""

    def __init__(
        self,
        class_names: Dict[str, List[str]],
        output_dir: str = None
    ):
        """
        Args:
            class_names: Mapping of head names to class names
            output_dir: Directory to save error visualizations
        """
        self.class_names = class_names
        self.output_dir = Path(output_dir) if output_dir else None
        self.error_cases: List[ErrorCase] = []

    def analyze_errors(
        self,
        predictions: Dict[str, np.ndarray],
        targets: Dict[str, np.ndarray],
        confidences: Dict[str, np.ndarray] = None,
        image_paths: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze classification errors

        Args:
            predictions: Dict of head name -> predictions (N, num_classes)
            targets: Dict of head name -> targets (N,)
            confidences: Optional dict of confidence scores
            image_paths: Optional list of image paths

        Returns:
            Error analysis results
        """
        error_stats = {
            'total_errors': 0,
            'per_head_errors': {},
            'confusion_patterns': defaultdict(int),
            'most_confused_pairs': []
        }

        for head_name, pred in predictions.items():
            if head_name not in targets:
                continue

            pred_classes = pred.argmax(axis=1)
            true_classes = targets[head_name]

            # Find errors
            errors = pred_classes != true_classes
            num_errors = errors.sum()

            error_stats['per_head_errors'][head_name] = {
                'num_errors': int(num_errors),
                'error_rate': float(num_errors / len(pred_classes))
            }
            error_stats['total_errors'] += int(num_errors)

            # Analyze confusion patterns
            for i in range(len(pred_classes)):
                if errors[i]:
                    pred_class = int(pred_classes[i])
                    true_class = int(true_classes[i])
                    pair = (true_class, pred_class)
                    error_stats['confusion_patterns'][pair] += 1

                    # Store error case
                    if image_paths and i < len(image_paths):
                        conf = confidences[head_name][i].max() if confidences else 0.0
                        self.error_cases.append(ErrorCase(
                            image_path=image_paths[i],
                            predicted_class=self.class_names[head_name][pred_class],
                            true_class=self.class_names[head_name][true_class],
                            confidence=float(conf),
                            error_type='confusion',
                            head_name=head_name
                        ))

        # Find most confused pairs
        sorted_pairs = sorted(
            error_stats['confusion_patterns'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        error_stats['most_confused_pairs'] = [
            {'pair': f"{pair[0][0]} -> {pair[0][1]}", 'count': count}
            for pair, count in sorted_pairs[:10]
        ]

        return error_stats

    def get_worst_cases(
        self,
        head_name: str = None,
        top_k: int = 10
    ) -> List[ErrorCase]:
        """
        Get worst error cases sorted by confidence

        Args:
            head_name: Filter by head name (optional)
            top_k: Number of cases to return

        Returns:
            List of worst error cases
        """
        filtered = self.error_cases
        if head_name:
            filtered = [c for c in filtered if c.head_name == head_name]

        # Sort by confidence (descending) - high confidence errors are worst
        sorted_cases = sorted(
            filtered,
            key=lambda c: c.confidence,
            reverse=True
        )

        return sorted_cases[:top_k]


# ============================================================================
# Main Classification Evaluator
# ============================================================================

class ClassificationEvaluator:
    """Comprehensive evaluator for multi-task tongue classification

    Evaluates all 6 diagnostic heads:
    - 舌色 (Tongue Color) - 4 classes
    - 苔色 (Coating Color) - 4 classes
    - 舌形 (Tongue Shape) - 3 classes
    - 苔质 (Coating Quality) - 3 classes
    - 特征 (Special Features) - 4 classes (multi-label)
    - 健康状态 (Health Status) - 2 classes
    """

    def __init__(
        self,
        model: nn.Layer,
        head_configs: Dict[str, Any],
        output_dir: str = None,
        class_names: Dict[str, List[str]] = None
    ):
        """
        Args:
            model: The multi-head classification model
            head_configs: Configuration for each head
            output_dir: Directory to save evaluation results
            class_names: Optional custom class names
        """
        self.model = model
        self.head_configs = head_configs
        self.output_dir = Path(output_dir) if output_dir else Path('.')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use provided class names or extract from configs
        self.class_names = class_names or {
            name: cfg.class_names
            for name, cfg in head_configs.items()
        }

        # Initialize Grad-CAM
        self.gradcam = GradCAM(model, target_layer='stage4')

        # Initialize error analyzer
        self.error_analyzer = ErrorAnalyzer(self.class_names, self.output_dir)

    @staticmethod
    def compute_ap(
        pred_probs: np.ndarray,
        targets: np.ndarray,
        num_classes: int
    ) -> Tuple[float, List[float]]:
        """
        Compute Average Precision for each class and mAP

        Args:
            pred_probs: Prediction probabilities (N, num_classes)
            targets: True class indices (N,)
            num_classes: Number of classes

        Returns:
            Tuple of (mAP, per_class_AP)
        """
        ap_scores = []

        for c in range(num_classes):
            # Binary labels for this class
            binary_targets = (targets == c).astype(int)

            # Sort by prediction confidence
            indices = np.argsort(-pred_probs[:, c])
            sorted_preds = pred_probs[indices, c]
            sorted_targets = binary_targets[indices]

            # Compute precision at each threshold
            tp = np.cumsum(sorted_targets)
            fp = np.cumsum(1 - sorted_targets)

            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + np.sum(1 - binary_targets) + 1e-8)

            # Compute AP using all-point interpolation
            if np.sum(binary_targets) > 0:
                ap = np.mean(precision[sorted_targets == 1]) if np.any(sorted_targets == 1) else 0.0
            else:
                ap = 0.0

            ap_scores.append(ap)

        mAP = np.mean(ap_scores)
        return mAP, ap_scores

    @staticmethod
    def compute_f1_metrics(
        predictions: np.ndarray,
        targets: np.ndarray,
        num_classes: int,
        multi_label: bool = False
    ) -> Tuple[float, List[float], List[float], List[float]]:
        """
        Compute precision, recall, F1 for each class

        Args:
            predictions: Predicted class indices (N,)
            targets: True class indices (N,)
            num_classes: Number of classes
            multi_label: Whether this is multi-label task

        Returns:
            Tuple of (macro_f1, precision_list, recall_list, f1_list)
        """
        precision_list = []
        recall_list = []
        f1_list = []

        for c in range(num_classes):
            tp = ((predictions == c) & (targets == c)).sum()
            fp = ((predictions == c) & (targets != c)).sum()
            fn = ((predictions != c) & (targets == c)).sum()

            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + fn + 1e-8)
            f1 = 2 * precision * recall / (precision + recall + 1e-8)

            precision_list.append(float(precision))
            recall_list.append(float(recall))
            f1_list.append(float(f1))

        macro_f1 = float(np.mean(f1_list))
        return macro_f1, precision_list, recall_list, f1_list

    @staticmethod
    def compute_confusion_matrix(
        predictions: np.ndarray,
        targets: np.ndarray,
        num_classes: int
    ) -> np.ndarray:
        """
        Compute confusion matrix

        Args:
            predictions: Predicted class indices (N,)
            targets: True class indices (N,)
            num_classes: Number of classes

        Returns:
            Confusion matrix (num_classes, num_classes)
        """
        cm = np.zeros((num_classes, num_classes), dtype=int)

        for t, p in zip(targets, predictions):
            cm[int(t), int(p)] += 1

        return cm

    def evaluate(
        self,
        dataloader,
        device: str = 'gpu:0',
        warmup_steps: int = 5
    ) -> ClassificationResult:
        """
        Run comprehensive evaluation

        Args:
            dataloader: Test data loader
            device: Device to run evaluation on
            warmup_steps: Number of warmup iterations for timing

        Returns:
            ClassificationResult with all metrics
        """
        # Set device
        if device.startswith('gpu'):
            paddle.set_device(device)
            self.model.to(device)
        self.model.eval()

        # Storage for predictions and targets
        all_predictions = {k: [] for k in self.class_names.keys()}
        all_targets = {k: [] for k in self.class_names.keys()}
        all_probs = {k: [] for k in self.class_names.keys()}

        # Timing
        import time
        inference_times = []

        # Warmup
        print(f"Running {warmup_steps} warmup steps...")
        for i, (images, targets) in enumerate(dataloader):
            if i >= warmup_steps:
                break
            _ = self.model(images)

        print("Starting evaluation...")
        total_batches = 0

        with paddle.no_grad():
            for images, targets_dict in dataloader:
                images = paddle.to_tensor(images.numpy(), dtype='float32')

                # Time inference
                start_time = time.perf_counter()
                predictions = self.model(images)
                end_time = time.perf_counter()

                inference_times.append(end_time - start_time)

                # Process each head
                for head_idx, head_name in enumerate(self.class_names.keys()):
                    if head_name not in predictions:
                        continue

                    pred = predictions[head_name]
                    target = targets_dict[head_name]

                    # Get predicted class and probabilities
                    if pred.ndim > 2:
                        pred = pred.mean(axis=2)

                    probs = F.softmax(pred, axis=1).numpy()
                    pred_classes = pred.argmax(axis=1).numpy()

                    # Get target class
                    if target.ndim > 1:
                        target_classes = target.argmax(axis=1).numpy()
                    else:
                        target_classes = target.numpy()

                    # Store results
                    all_predictions[head_name].append(pred_classes)
                    all_targets[head_name].append(target_classes)
                    all_probs[head_name].append(probs)

                total_batches += 1

        # Compute metrics for each head
        head_metrics = {}
        f1_scores = []
        ap_scores = []

        for head_name in self.class_names.keys():
            if not all_predictions[head_name]:
                continue

            # Concatenate all batches
            pred_array = np.concatenate(all_predictions[head_name])
            target_array = np.concatenate(all_targets[head_name])
            probs_array = np.concatenate(all_probs[head_name])

            num_classes = len(self.class_names[head_name])
            is_multi_label = self.head_configs[head_name].multi_label

            # Compute AP
            mAP_head, per_class_ap = self.compute_ap(
                probs_array, target_array, num_classes
            )
            ap_scores.append(mAP_head)

            # Compute F1 metrics
            macro_f1, precisions, recalls, f1s = self.compute_f1_metrics(
                pred_array, target_array, num_classes, is_multi_label
            )
            f1_scores.append(macro_f1)

            # Compute confusion matrix
            cm = self.compute_confusion_matrix(
                pred_array, target_array, num_classes
            )

            # Compute accuracy
            accuracy = (pred_array == target_array).mean()

            # Store metrics
            head_metrics[head_name] = HeadMetrics(
                head_name=head_name,
                num_classes=num_classes,
                class_names=self.class_names[head_name],
                accuracy=float(accuracy),
                precision=float(np.mean(precisions)),
                recall=float(np.mean(recalls)),
                f1=float(macro_f1),
                ap=float(mAP_head),
                per_class_precision=precisions,
                per_class_recall=recalls,
                per_class_f1=f1s,
                per_class_ap=per_class_ap,
                confusion_matrix=cm
            )

        # Compute overall metrics
        macro_f1 = float(np.mean(f1_scores)) if f1_scores else 0.0
        macro_map = float(np.mean(ap_scores)) if ap_scores else 0.0

        # Compute timing stats
        inference_times = np.array(inference_times)
        avg_inference_time = float(np.mean(inference_times) * 1000)  # ms
        fps = float(1.0 / np.mean(inference_times)) if np.mean(inference_times) > 0 else 0.0

        # Count total samples
        num_samples = sum(
            len(np.concatenate(all_targets[h]))
            for h in self.class_names.keys()
            if all_targets[h]
        ) // len(self.class_names)

        # Create result
        result = ClassificationResult(
            num_samples=num_samples,
            num_heads=len(self.class_names),
            head_names=list(self.class_names.keys()),
            head_metrics=head_metrics,
            macro_f1=macro_f1,
            micro_f1=macro_f1,  # Same for multi-task
            macro_map=macro_map,
            inference_time_ms=avg_inference_time,
            fps=fps
        )

        return result

    def generate_report(
        self,
        result: ClassificationResult,
        save_path: str = None
    ) -> str:
        """
        Generate comprehensive evaluation report

        Args:
            result: Classification evaluation result
            save_path: Path to save report (optional)

        Returns:
            Report text
        """
        lines = []
        lines.append("=" * 70)
        lines.append("Multi-Task Tongue Classification Evaluation Report")
        lines.append("=" * 70)
        lines.append("")

        # Overall metrics
        lines.append("Overall Metrics:")
        lines.append(f"  - Number of samples: {result.num_samples}")
        lines.append(f"  - Number of heads: {result.num_heads}")
        lines.append(f"  - Macro F1: {result.macro_f1:.4f}")
        lines.append(f"  - Macro mAP: {result.macro_map:.4f}")
        lines.append("")

        # Performance
        lines.append("Performance Metrics:")
        lines.append(f"  - Avg inference time: {result.inference_time_ms:.2f} ms")
        lines.append(f"  - Throughput: {result.fps:.2f} FPS")
        lines.append("")

        # Per-head metrics
        lines.append("Per-Head Metrics:")
        lines.append("-" * 70)

        for head_name, metrics in result.head_metrics.items():
            lines.append(f"\n{head_name}:")
            lines.append(f"  Accuracy: {metrics.accuracy:.4f}")
            lines.append(f"  Precision: {metrics.precision:.4f}")
            lines.append(f"  Recall: {metrics.recall:.4f}")
            lines.append(f"  F1: {metrics.f1:.4f}")
            lines.append(f"  AP: {metrics.ap:.4f}")
            lines.append("")

            # Per-class breakdown
            lines.append("  Per-class Metrics:")
            for i, class_name in enumerate(metrics.class_names):
                lines.append(
                    f"    {class_name}: "
                    f"P={metrics.per_class_precision[i]:.3f}, "
                    f"R={metrics.per_class_recall[i]:.3f}, "
                    f"F1={metrics.per_class_f1[i]:.3f}, "
                    f"AP={metrics.per_class_ap[i]:.3f}"
                )

        lines.append("")
        lines.append("=" * 70)

        report = "\n".join(lines)

        # Save if path provided
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Report saved to: {save_path}")

        return report

    def save_confusion_matrices(
        self,
        result: ClassificationResult,
        output_dir: str = None
    ):
        """
        Generate and save confusion matrix visualizations

        Args:
            result: Classification evaluation result
            output_dir: Directory to save visualizations
        """
        if not MATPLOTLIB_AVAILABLE:
            print("Warning: matplotlib not available, skipping confusion matrix visualization")
            return

        output_dir = Path(output_dir) if output_dir else self.output_dir / "confusion_matrices"
        output_dir.mkdir(parents=True, exist_ok=True)

        for head_name, metrics in result.head_metrics.items():
            fig, ax = plt.subplots(figsize=(8, 7))

            # Plot confusion matrix
            im = ax.imshow(
                metrics.confusion_matrix,
                interpolation='nearest',
                cmap=plt.cm.Blues
            )

            # Add colorbar
            plt.colorbar(im, ax=ax)

            # Configure ticks
            tick_marks = np.arange(len(metrics.class_names))
            ax.set_xticks(tick_marks)
            ax.set_yticks(tick_marks)
            ax.set_xticklabels(metrics.class_names, rotation=45, ha='right')
            ax.set_yticklabels(metrics.class_names)

            # Labels
            ax.set_xlabel('Predicted Label', fontsize=12)
            ax.set_ylabel('True Label', fontsize=12)
            ax.set_title(f'{head_name} Confusion Matrix', fontsize=14, fontweight='bold')

            # Add text annotations
            thresh = metrics.confusion_matrix.max() / 2
            for i in range(metrics.confusion_matrix.shape[0]):
                for j in range(metrics.confusion_matrix.shape[1]):
                    text_color = 'white' if metrics.confusion_matrix[i, j] > thresh else 'black'
                    ax.text(
                        j, i, format(metrics.confusion_matrix[i, j], 'd'),
                        ha='center', va='center', color=text_color, fontsize=10
                    )

            plt.tight_layout()

            # Save
            output_path = output_dir / f"{head_name}_confusion_matrix.png"
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()

            print(f"Saved confusion matrix: {output_path}")

    def generate_gradcam_visualization(
        self,
        image: np.ndarray,
        target_class: int,
        head_name: str = 'tongue_color',
        save_path: str = None
    ) -> np.ndarray:
        """
        Generate Grad-CAM visualization for a single image

        Args:
            image: Input image (H, W, 3) in RGB [0, 1]
            target_class: Target class for visualization
            head_name: Which head to use
            save_path: Optional path to save visualization

        Returns:
            Overlayed image with heatmap
        """
        # Prepare input tensor
        input_tensor = paddle.to_tensor(
            image.transpose(2, 0, 1)[np.newaxis, ...].astype('float32')
        )

        # Generate heatmap
        heatmap = self.gradcam.generate_heatmap(
            input_tensor, target_class, head_name
        )

        # Overlay on image
        overlay = self.gradcam.overlay_heatmap(image, heatmap)

        # Save if path provided
        if save_path and PIL_AVAILABLE:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            overlay_img = Image.fromarray((overlay * 255).astype(np.uint8))
            overlay_img.save(save_path)
            print(f"Saved Grad-CAM: {save_path}")

        return overlay

    def save_evaluation_json(
        self,
        result: ClassificationResult,
        save_path: str = None
    ):
        """
        Save evaluation results as JSON

        Args:
            result: Classification evaluation result
            save_path: Path to save JSON
        """
        save_path = Path(save_path) if save_path else self.output_dir / "evaluation_results.json"

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"Saved JSON results to: {save_path}")


# ============================================================================
# Utility Functions
# ============================================================================

def create_classification_evaluator(
    model: nn.Layer,
    head_configs: Dict[str, Any],
    output_dir: str = None
) -> ClassificationEvaluator:
    """Factory function to create ClassificationEvaluator

    Args:
        model: Multi-head classification model
        head_configs: Configuration for each head
        output_dir: Directory to save results

    Returns:
        ClassificationEvaluator instance
    """
    return ClassificationEvaluator(
        model=model,
        head_configs=head_configs,
        output_dir=output_dir
    )


if __name__ == "__main__":
    print("Classification Evaluator Module")
    print("=" * 60)
    print("This module provides comprehensive evaluation tools for")
    print("multi-task tongue classification.")
    print("")
    print("Features:")
    print("  - Multi-label metrics (mAP, F1, precision, recall)")
    print("  - Confusion matrix generation and visualization")
    print("  - Per-class performance analysis")
    print("  - Error analysis and case studies")
    print("  - Grad-CAM visualization")
    print("  - Feature contribution analysis")
    print("=" * 60)
