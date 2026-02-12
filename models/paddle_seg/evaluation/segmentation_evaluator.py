#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Segmentation Model Evaluation Module

Comprehensive evaluation for tongue segmentation models including:
- Standard metrics (mIoU, Dice, Accuracy)
- Boundary F1 score
- Confusion matrix generation
- Error case analysis
- Visual report generation

task-2-7: 分割模型评估报告

Usage:
    from models.paddle_seg.evaluation.segmentation_evaluator import SegmentationEvaluator

    evaluator = SegmentationEvaluator(
        num_classes=2,
        output_dir='models/paddle_seg/evaluation'
    )
    results = evaluator.evaluate(model, test_loader)
    evaluator.generate_report(results)
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

import numpy as np
import paddle
import paddle.nn.functional as F
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class EvaluationResult:
    """Container for evaluation results."""
    # Standard metrics
    miou: float = 0.0
    dice: float = 0.0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Per-class metrics
    iou_per_class: List[float] = field(default_factory=list)
    dice_per_class: List[float] = field(default_factory=list)

    # Boundary metrics
    boundary_f1: float = 0.0
    boundary_precision: float = 0.0
    boundary_recall: float = 0.0

    # Confusion matrix
    confusion_matrix: np.ndarray = None

    # Inference time
    avg_inference_time_ms: float = 0.0
    p95_inference_time_ms: float = 0.0
    p99_inference_time_ms: float = 0.0

    # Error cases
    false_positive_cases: List[Dict] = field(default_factory=list)
    false_negative_cases: List[Dict] = field(default_factory=list)
    worst_cases: List[Dict] = field(default_factory=list)

    # Metadata
    num_samples: int = 0
    evaluation_date: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'miou': self.miou,
            'dice': self.dice,
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'iou_per_class': self.iou_per_class,
            'dice_per_class': self.dice_per_class,
            'boundary_f1': self.boundary_f1,
            'boundary_precision': self.boundary_precision,
            'boundary_recall': self.boundary_recall,
            'avg_inference_time_ms': self.avg_inference_time_ms,
            'p95_inference_time_ms': self.p95_inference_time_ms,
            'p99_inference_time_ms': self.p99_inference_time_ms,
            'num_samples': self.num_samples,
            'evaluation_date': self.evaluation_date,
        }


class BoundaryMetrics:
    """
    Boundary F1 metric for segmentation evaluation.

    Computes precision, recall, and F1 score on boundary pixels only.
    This is more sensitive to boundary accuracy than pixel-wise metrics.

    Reference:
        - Chamfer Distance for boundary matching
        - Boundary F1 in medical image segmentation
    """

    def __init__(self, boundary_threshold: int = 2, ignore_index: int = 255):
        """
        Initialize boundary metrics calculator.

        Args:
            boundary_threshold: Distance threshold (in pixels) for boundary matching
            ignore_index: Label index to ignore in evaluation
        """
        self.boundary_threshold = boundary_threshold
        self.ignore_index = ignore_index

    def _extract_boundaries(self, mask: np.ndarray) -> np.ndarray:
        """
        Extract boundary pixels from a segmentation mask.

        Uses morphological gradient to find boundary pixels.

        Args:
            mask: Segmentation mask of shape (H, W)

        Returns:
            Binary boundary map of shape (H, W)
        """
        # Create structuring element for morphological operations
        from scipy import ndimage

        # Dilate and erode to find boundaries
        struct_elem = np.ones((3, 3), dtype=np.uint8)

        # Handle ignore index
        valid_mask = (mask != self.ignore_index)
        mask_clean = np.where(valid_mask, mask, 0)

        # Dilated version
        dilated = ndimage.binary_dilation(mask_clean.astype(np.uint8), structure=struct_elem)
        # Eroded version
        eroded = ndimage.binary_erosion(mask_clean.astype(np.uint8), structure=struct_elem)

        # Boundary = dilated - eroded
        boundaries = (dilated.astype(np.int8) - eroded.astype(np.int8)).astype(np.uint8)

        # Apply validity mask
        boundaries = boundaries * valid_mask.astype(np.uint8)

        return boundaries

    def compute(
        self,
        pred: np.ndarray,
        target: np.ndarray
    ) -> Tuple[float, float, float]:
        """
        Compute boundary precision, recall, and F1.

        Args:
            pred: Predicted segmentation of shape (H, W)
            target: Ground truth of shape (H, W)

        Returns:
            Tuple of (precision, recall, f1)
        """
        # Extract boundaries
        pred_boundaries = self._extract_boundaries(pred)
        target_boundaries = self._extract_boundaries(target)

        # Count TP, FP, FN
        tp = np.sum((pred_boundaries == 1) & (target_boundaries == 1))
        fp = np.sum((pred_boundaries == 1) & (target_boundaries == 0))
        fn = np.sum((pred_boundaries == 0) & (target_boundaries == 1))

        # Compute metrics
        precision = tp / max(tp + fp, 1e-5)
        recall = tp / max(tp + fn, 1e-5)
        f1 = 2 * precision * recall / max(precision + recall, 1e-5)

        return float(precision), float(recall), float(f1)


class ErrorAnalyzer:
    """
    Analyze segmentation errors and categorize failure modes.

    Error Categories:
    - False Positive: Model predicts tongue where there is none
    - False Negative: Model misses tongue regions
    - Boundary Error: Boundary offset but correct region
    - Small Object: Poor performance on small tongues
    - Large Object: Poor performance on large tongues
    """

    def __init__(self, num_classes: int = 2, ignore_index: int = 255):
        self.num_classes = num_classes
        self.ignore_index = ignore_index

    def analyze_batch(
        self,
        preds: np.ndarray,
        targets: np.ndarray,
        image_paths: List[str] = None,
        top_k: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        Analyze a batch of predictions for error patterns.

        Args:
            preds: Predictions of shape (N, H, W)
            targets: Ground truth of shape (N, H, W)
            image_paths: Optional list of image file paths
            top_k: Number of worst cases to return

        Returns:
            Dictionary with error case lists
        """
        fp_cases = []
        fn_cases = []
        worst_cases = []

        for i in range(len(preds)):
            pred = preds[i]
            target = targets[i]

            # Skip if all ignored
            valid_mask = (target != self.ignore_index)
            if valid_mask.sum() == 0:
                continue

            # Compute IoU for this sample
            iou = self._compute_sample_iou(pred, target)

            # Analyze error types
            fp_ratio = self._compute_false_positive_ratio(pred, target)
            fn_ratio = self._compute_false_negative_ratio(pred, target)

            case_info = {
                'index': i,
                'image_path': image_paths[i] if image_paths else f'sample_{i}',
                'iou': float(iou),
                'fp_ratio': float(fp_ratio),
                'fn_ratio': float(fn_ratio),
            }

            # Categorize errors
            if fp_ratio > 0.1:  # More than 10% FP
                case_info['error_type'] = 'false_positive'
                case_info['description'] = f'Over-segmentation (FP ratio: {fp_ratio:.2%})'
                fp_cases.append(case_info)

            if fn_ratio > 0.1:  # More than 10% FN
                case_info['error_type'] = 'false_negative'
                case_info['description'] = f'Under-segmentation (FN ratio: {fn_ratio:.2%})'
                fn_cases.append(case_info)

            worst_cases.append(case_info)

        # Sort by IoU (ascending)
        worst_cases.sort(key=lambda x: x['iou'])

        return {
            'false_positive_cases': fp_cases[:top_k],
            'false_negative_cases': fn_cases[:top_k],
            'worst_cases': worst_cases[:top_k],
        }

    def _compute_sample_iou(self, pred: np.ndarray, target: np.ndarray) -> float:
        """Compute IoU for a single sample."""
        valid_mask = (target != self.ignore_index)
        pred_valid = pred[valid_mask]
        target_valid = target[valid_mask]

        if len(target_valid) == 0:
            return 0.0

        iou = 0.0
        for cls in range(self.num_classes):
            pred_cls = (pred_valid == cls)
            target_cls = (target_valid == cls)

            intersection = (pred_cls & target_cls).sum()
            union = (pred_cls | target_cls).sum()

            if union > 0:
                iou += intersection / union

        return iou / self.num_classes

    def _compute_false_positive_ratio(self, pred: np.ndarray, target: np.ndarray) -> float:
        """Compute ratio of false positive pixels."""
        valid_mask = (target != self.ignore_index) & (target == 0)  # Background only
        if valid_mask.sum() == 0:
            return 0.0

        fp_pixels = (pred == 1) & (target == 0)
        return fp_pixels.sum() / valid_mask.sum()

    def _compute_false_negative_ratio(self, pred: np.ndarray, target: np.ndarray) -> float:
        """Compute ratio of false negative pixels."""
        valid_mask = (target != self.ignore_index) & (target == 1)  # Foreground only
        if valid_mask.sum() == 0:
            return 0.0

        fn_pixels = (pred == 0) & (target == 1)
        return fn_pixels.sum() / valid_mask.sum()


class SegmentationEvaluator:
    """
    Comprehensive segmentation evaluator.

    Generates complete evaluation reports including metrics,
    visualizations, and error analysis.
    """

    def __init__(
        self,
        num_classes: int = 2,
        ignore_index: int = 255,
        output_dir: str = None,
        class_names: List[str] = None
    ):
        """
        Initialize evaluator.

        Args:
            num_classes: Number of segmentation classes
            ignore_index: Label index to ignore
            output_dir: Directory to save reports
            class_names: Names of classes for visualization
        """
        self.num_classes = num_classes
        self.ignore_index = ignore_index
        self.output_dir = Path(output_dir) if output_dir else Path('models/paddle_seg/evaluation')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.class_names = class_names or [f'Class {i}' for i in range(num_classes)]

        # Initialize metric calculators
        self.boundary_calculator = BoundaryMetrics(ignore_index=ignore_index)
        self.error_analyzer = ErrorAnalyzer(num_classes=num_classes, ignore_index=ignore_index)

    def evaluate(
        self,
        model: paddle.nn.Layer,
        test_loader,
        device: str = None
    ) -> EvaluationResult:
        """
        Run complete evaluation on a test set.

        Args:
            model: Trained segmentation model
            test_loader: Test data loader
            device: Device to run inference ('cpu', 'gpu:0', or None for auto)

        Returns:
            EvaluationResult with all metrics
        """
        if device is None:
            device = 'gpu:0' if paddle.is_compiled_with_cuda() else 'cpu'

        model.eval()
        model.to(device)

        # Storage for predictions
        all_preds = []
        all_targets = []
        all_image_paths = []
        inference_times = []

        # Run inference
        with paddle.no_grad():
            for batch in tqdm(test_loader, desc="Evaluating"):
                if isinstance(batch, (tuple, list)):
                    if len(batch) >= 2:
                        data, target = batch[0], batch[1]
                        image_paths = batch[2] if len(batch) > 2 else None
                    else:
                        data = batch[0]
                        target = batch[1] if hasattr(batch[1], 'shape') else None
                        image_paths = None
                else:
                    data = batch[0]
                    target = batch[1] if len(batch) > 1 else None
                    image_paths = None

                # Move to device
                data = paddle.to_tensor(data)
                if target is not None:
                    target_np = target.numpy() if isinstance(target, paddle.Tensor) else target
                else:
                    target_np = None

                # Measure inference time
                import time
                start = time.perf_counter()
                output = model(data)
                if isinstance(output, dict):
                    logits = output['out']
                else:
                    logits = output
                end = time.perf_counter()

                inference_times.append((end - start) * 1000)  # Convert to ms

                # Get predictions
                pred = logits.argmax(axis=1).numpy()
                all_preds.append(pred)

                if target_np is not None:
                    all_targets.append(target_np)

                if image_paths is not None:
                    all_image_paths.extend(image_paths)

        # Concatenate results
        all_preds = np.concatenate(all_preds, axis=0)
        all_targets = np.concatenate(all_targets, axis=0) if all_targets else None

        # Compute all metrics
        result = EvaluationResult(num_samples=len(all_preds))

        # Standard metrics
        result.miou, result.dice, result.accuracy = self._compute_standard_metrics(
            all_preds, all_targets
        )

        # Boundary metrics
        result.boundary_precision, result.boundary_recall, result.boundary_f1 = \
            self._compute_boundary_metrics(all_preds, all_targets)

        # Confusion matrix
        result.confusion_matrix = self._compute_confusion_matrix(all_preds, all_targets)

        # Precision, Recall, F1
        result.precision, result.recall, result.f1_score = self._compute_prf(
            result.confusion_matrix
        )

        # Inference time statistics
        result.avg_inference_time_ms = np.mean(inference_times)
        result.p95_inference_time_ms = np.percentile(inference_times, 95)
        result.p99_inference_time_ms = np.percentile(inference_times, 99)

        # Error analysis
        error_results = self.error_analyzer.analyze_batch(
            all_preds, all_targets, all_image_paths, top_k=20
        )
        result.false_positive_cases = error_results['false_positive_cases']
        result.false_negative_cases = error_results['false_negative_cases']
        result.worst_cases = error_results['worst_cases']

        return result

    def _compute_standard_metrics(
        self,
        pred: np.ndarray,
        target: np.ndarray
    ) -> Tuple[float, float, float]:
        """Compute mIoU, Dice, and Accuracy."""
        intersection = np.zeros(self.num_classes, dtype=np.float64)
        union = np.zeros(self.num_classes, dtype=np.float64)

        valid_mask = (target != self.ignore_index)
        pred_valid = pred[valid_mask]
        target_valid = target[valid_mask]

        for cls in range(self.num_classes):
            pred_cls = (pred_valid == cls)
            target_cls = (target_valid == cls)

            intersection[cls] = (pred_cls & target_cls).sum()
            union[cls] = (pred_cls | target_cls).sum()

        # mIoU
        iou_per_class = np.divide(
            intersection,
            np.where(union > 0, union, 1),
            out=np.zeros_like(intersection, dtype=float),
            where=union > 0
        )
        miou = float(np.mean(iou_per_class))

        # Dice
        dice_per_class = 2 * intersection / (union + intersection + 1e-5)
        dice = float(np.mean(dice_per_class))

        # Accuracy
        accuracy = float((pred_valid == target_valid).sum() / max(len(pred_valid), 1))

        return miou, dice, accuracy

    def _compute_boundary_metrics(
        self,
        pred: np.ndarray,
        target: np.ndarray
    ) -> Tuple[float, float, float]:
        """Compute aggregate boundary metrics across all samples."""
        precisions = []
        recalls = []
        f1s = []

        for i in range(len(pred)):
            p, r, f = self.boundary_calculator.compute(pred[i], target[i])
            precisions.append(p)
            recalls.append(r)
            f1s.append(f)

        return float(np.mean(precisions)), float(np.mean(recalls)), float(np.mean(f1s))

    def _compute_confusion_matrix(
        self,
        pred: np.ndarray,
        target: np.ndarray
    ) -> np.ndarray:
        """Compute confusion matrix."""
        valid_mask = (target != self.ignore_index)
        pred_valid = pred[valid_mask]
        target_valid = target[valid_mask]

        cm = np.zeros((self.num_classes, self.num_classes), dtype=np.int64)
        for i in range(self.num_classes):
            for j in range(self.num_classes):
                cm[i, j] = ((target_valid == i) & (pred_valid == j)).sum()

        return cm

    def _compute_prf(self, cm: np.ndarray) -> Tuple[float, float, float]:
        """Compute macro precision, recall, and F1 from confusion matrix."""
        precisions = []
        recalls = []
        f1s = []

        for i in range(self.num_classes):
            tp = cm[i, i]
            fp = cm[:, i].sum() - tp
            fn = cm[i, :].sum() - tp

            precision = tp / max(tp + fp, 1e-5)
            recall = tp / max(tp + fn, 1e-5)
            f1 = 2 * precision * recall / max(precision + recall, 1e-5)

            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)

        return float(np.mean(precisions)), float(np.mean(recalls)), float(np.mean(f1s))

    def generate_report(self, result: EvaluationResult) -> str:
        """
        Generate comprehensive evaluation report.

        Args:
            result: EvaluationResult from evaluate()

        Returns:
            Path to generated report JSON
        """
        # Save JSON report
        report_path = self.output_dir / 'evaluation_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        # Generate visualizations
        self._plot_confusion_matrix(result)
        self._plot_metrics_summary(result)
        self._plot_error_cases(result)

        # Generate text summary
        summary_path = self._generate_text_summary(result)

        print(f"\n{'='*60}")
        print("SEGMENTATION EVALUATION REPORT")
        print(f"{'='*60}")
        print(f"Samples evaluated: {result.num_samples}")
        print(f"Date: {result.evaluation_date}")
        print(f"\n--- Metrics ---")
        print(f"mIoU:          {result.miou:.4f} (target: >0.92)")
        print(f"Dice:          {result.dice:.4f} (target: >0.95)")
        print(f"Accuracy:       {result.accuracy:.4f}")
        print(f"Boundary F1:    {result.boundary_f1:.4f} (target: >0.88)")
        print(f"\n--- Inference Time ---")
        print(f"Average:        {result.avg_inference_time_ms:.2f} ms")
        print(f"P95:            {result.p95_inference_time_ms:.2f} ms")
        print(f"P99:            {result.p99_inference_time_ms:.2f} ms")
        print(f"\n--- Error Cases ---")
        print(f"False Positives:     {len(result.false_positive_cases)}")
        print(f"False Negatives:     {len(result.false_negative_cases)}")
        print(f"\nReports saved to: {self.output_dir}")

        return str(report_path)

    def _plot_confusion_matrix(self, result: EvaluationResult):
        """Generate confusion matrix visualization."""
        fig, ax = plt.subplots(figsize=(8, 6))

        cm_normalized = result.confusion_matrix.astype(float) / \
            (result.confusion_matrix.sum(axis=1, keepdims=True) + 1e-5)

        sns.heatmap(
            cm_normalized,
            annot=result.confusion_matrix,
            fmt='d',
            cmap='Blues',
            xticklabels=self.class_names,
            yticklabels=self.class_names,
            ax=ax
        )
        ax.set_xlabel('Predicted')
        ax.set_ylabel('Ground Truth')
        ax.set_title('Confusion Matrix (Normalized)')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'confusion_matrix.png', dpi=150)
        plt.close()

    def _plot_metrics_summary(self, result: EvaluationResult):
        """Generate metrics summary visualization."""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Metrics comparison
        metrics = ['mIoU', 'Dice', 'Accuracy', 'Boundary F1']
        values = [result.miou, result.dice, result.accuracy, result.boundary_f1]
        targets = [0.92, 0.95, 0.95, 0.88]

        x = np.arange(len(metrics))
        width = 0.35

        axes[0].bar(x - width/2, values, width, label='Actual', color='steelblue')
        axes[0].bar(x + width/2, targets, width, label='Target', color='lightcoral')
        axes[0].set_ylabel('Score')
        axes[0].set_title('Metrics vs Targets')
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(metrics, rotation=45)
        axes[0].legend()
        axes[0].set_ylim([0, 1])
        axes[0].grid(axis='y', alpha=0.3)

        # Per-class IoU
        if len(result.iou_per_class) == len(self.class_names):
            axes[1].bar(self.class_names, result.iou_per_class, color='steelblue')
            axes[1].set_ylabel('IoU')
            axes[1].set_title('Per-Class IoU')
            axes[1].set_ylim([0, 1])
            axes[1].grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'metrics_summary.png', dpi=150)
        plt.close()

    def _plot_error_cases(self, result: EvaluationResult):
        """Generate error cases visualization."""
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # Worst cases distribution
        if result.worst_cases:
            ious = [c['iou'] for c in result.worst_cases]
            axes[0].hist(ious, bins=20, color='lightcoral', alpha=0.7, edgecolor='black')
            axes[0].set_xlabel('IoU')
            axes[0].set_ylabel('Frequency')
            axes[0].set_title('Worst Cases IoU Distribution')
            axes[0].axvline(0.92, color='green', linestyle='--', label='Target (0.92)')
            axes[0].legend()
            axes[0].grid(axis='y', alpha=0.3)

        # Error type distribution
        error_types = ['False Positive', 'False Negative', 'Other']
        error_counts = [
            len(result.false_positive_cases),
            len(result.false_negative_cases),
            result.num_samples - len(result.false_positive_cases) - len(result.false_negative_cases)
        ]

        axes[1].bar(error_types, error_counts, color=['red', 'orange', 'green'])
        axes[1].set_ylabel('Count')
        axes[1].set_title('Error Type Distribution')
        axes[1].grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'error_analysis.png', dpi=150)
        plt.close()

    def _generate_text_summary(self, result: EvaluationResult) -> str:
        """Generate detailed text summary."""
        summary_path = self.output_dir / 'evaluation_summary.txt'

        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("TONGUE SEGMENTATION MODEL EVALUATION REPORT\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Evaluation Date: {result.evaluation_date}\n")
            f.write(f"Number of Samples: {result.num_samples}\n\n")

            f.write("-" * 60 + "\n")
            f.write("STANDARD METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"mIoU (Mean Intersection over Union): {result.miou:.4f}\n")
            f.write(f"  Target: > 0.92\n")
            f.write(f"  Status: {'✓ PASS' if result.miou > 0.92 else '✗ FAIL'}\n\n")

            f.write(f"Dice Coefficient: {result.dice:.4f}\n")
            f.write(f"  Target: > 0.95\n")
            f.write(f"  Status: {'✓ PASS' if result.dice > 0.95 else '✗ FAIL'}\n\n")

            f.write(f"Pixel Accuracy: {result.accuracy:.4f}\n")
            f.write(f"Precision (macro): {result.precision:.4f}\n")
            f.write(f"Recall (macro): {result.recall:.4f}\n")
            f.write(f"F1 Score (macro): {result.f1_score:.4f}\n\n")

            f.write("-" * 60 + "\n")
            f.write("BOUNDARY METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"Boundary F1: {result.boundary_f1:.4f}\n")
            f.write(f"  Target: > 0.88\n")
            f.write(f"  Status: {'✓ PASS' if result.boundary_f1 > 0.88 else '✗ FAIL'}\n\n")
            f.write(f"Boundary Precision: {result.boundary_precision:.4f}\n")
            f.write(f"Boundary Recall: {result.boundary_recall:.4f}\n\n")

            f.write("-" * 60 + "\n")
            f.write("INFERENCE PERFORMANCE\n")
            f.write("-" * 60 + "\n")
            f.write(f"Average Inference Time: {result.avg_inference_time_ms:.2f} ms\n")
            f.write(f"  Target: < 33 ms (P95)\n")
            f.write(f"  Status: {'✓ PASS' if result.p95_inference_time_ms < 33 else '✗ FAIL'}\n\n")
            f.write(f"P95 Inference Time: {result.p95_inference_time_ms:.2f} ms\n")
            f.write(f"P99 Inference Time: {result.p99_inference_time_ms:.2f} ms\n\n")

            f.write("-" * 60 + "\n")
            f.write("CONFUSION MATRIX\n")
            f.write("-" * 60 + "\n")
            f.write("                 Predicted\n")
            f.write("             Background  Tongue\n")
            f.write(f"Actual Background  {result.confusion_matrix[0, 0]:6d}     {result.confusion_matrix[0, 1]:6d}\n")
            f.write(f"       Tongue     {result.confusion_matrix[1, 0]:6d}     {result.confusion_matrix[1, 1]:6d}\n\n")

            f.write("-" * 60 + "\n")
            f.write("ERROR CASE ANALYSIS\n")
            f.write("-" * 60 + "\n")
            f.write(f"False Positive Cases (Over-segmentation): {len(result.false_positive_cases)}\n")
            f.write(f"False Negative Cases (Under-segmentation): {len(result.false_negative_cases)}\n\n")

            if result.worst_cases:
                f.write("Top 10 Worst Cases:\n")
                f.write("-" * 40 + "\n")
                for i, case in enumerate(result.worst_cases[:10], 1):
                    f.write(f"{i}. {case.get('image_path', 'N/A')}\n")
                    f.write(f"   IoU: {case['iou']:.4f} | FP: {case['fp_ratio']:.2%} | FN: {case['fn_ratio']:.2%}\n")
                    if 'error_type' in case:
                        f.write(f"   Type: {case['error_type']}\n")
                        f.write(f"   Description: {case.get('description', '')}\n")
                    f.write("\n")

            f.write("=" * 60 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 60 + "\n")

        return str(summary_path)


def compute_inference_time(
    model: paddle.nn.Layer,
    input_shape: Tuple[int, int, int, int],
    use_gpu: bool = True,
    num_runs: int = 100
) -> Dict[str, float]:
    """
    Measure model inference time.

    Args:
        model: Model to benchmark
        input_shape: Input shape (N, C, H, W)
        use_gpu: Whether to use GPU
        num_runs: Number of runs for averaging

    Returns:
        Dictionary with timing metrics
    """
    device = 'gpu:0' if use_gpu and paddle.is_compiled_with_cuda() else 'cpu'
    model.to(device)
    model.eval()

    # Warmup
    dummy_input = paddle.randn([1, *input_shape[1:]])
    for _ in range(10):
        with paddle.no_grad():
            _ = model(dummy_input)

    # Benchmark
    times = []
    with paddle.no_grad():
        for _ in range(num_runs):
            import time
            dummy_input = paddle.randn([1, *input_shape[1:]])

            start = time.perf_counter()
            output = model(dummy_input)
            if isinstance(output, dict):
                _ = output['out']
            end = time.perf_counter()

            times.append((end - start) * 1000)  # ms

    return {
        'avg_inference_time_ms': float(np.mean(times)),
        'p95_inference_time_ms': float(np.percentile(times, 95)),
        'p99_inference_time_ms': float(np.percentile(times, 99)),
        'min_inference_time_ms': float(np.min(times)),
        'max_inference_time_ms': float(np.max(times)),
        'std_inference_time_ms': float(np.std(times)),
        'fps': float(1000 / np.mean(times)),
    }


# Standalone evaluation script
if __name__ == "__main__":
    # Fix Windows console encoding
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    import argparse
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Segmentation Model Evaluation")
    parser.add_argument("--checkpoint", type=str, required=True,
                       help="Path to model checkpoint")
    parser.add_argument("--data-root", type=str, default="shezhenv3-coco/test",
                       help="Path to test data")
    parser.add_argument("--output-dir", type=str, default="models/paddle_seg/evaluation",
                       help="Output directory for reports")
    parser.add_argument("--batch-size", type=int, default=8,
                       help="Batch size for evaluation")
    parser.add_argument("--image-size", type=int, nargs=2, default=[512, 512],
                       help="Image size (H W)")

    args = parser.parse_args()

    logger.info("Loading model...")
    logger.info(f"Checkpoint: {args.checkpoint}")
    logger.info(f"Test data: {args.data_root}")

    # Note: This is a template script
    # In actual use, you would:
    # 1. Create model
    # 2. Load checkpoint
    # 3. Create test dataset
    # 4. Run evaluator.evaluate()

    logger.info("""
Usage Example:
    from models.paddle_seg.evaluation.segmentation_evaluator import SegmentationEvaluator

    evaluator = SegmentationEvaluator(num_classes=2, output_dir='models/paddle_seg/evaluation')

    # Load your model
    model = ...  # Your BiSeNetV2 model
    state_dict = paddle.load(args.checkpoint)
    model.set_state_dict(state_dict['model_state_dict'])

    # Load your test data
    test_loader = ...  # Your DataLoader

    # Run evaluation
    results = evaluator.evaluate(model, test_loader)
    evaluator.generate_report(results)
""")
