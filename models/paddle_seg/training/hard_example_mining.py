#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hard Example Mining for Tongue Segmentation

Implements online hard example mining (OHEM) strategy:
- Selects top 10% samples with highest loss each epoch
- Adds them to the next epoch for retraining
- Supports progressive training (detail branch first, then joint)

task-2-4: 难例挖掘与重训练

Usage:
    from models.paddle_seg.training.hard_example_mining import HardExampleMiner, HardExampleDataset

    # Create miner
    miner = HardExampleMiner(top_k_percent=0.1)

    # During training, collect losses
    for batch_idx, (images, masks, indices) in enumerate(train_loader):
        outputs = model(images)
        loss_dict = criterion(outputs, masks)
        miner.record_batch_loss(indices, loss_dict['loss'])

    # Get hard examples after epoch
    hard_indices = miner.get_hard_examples()

    # Create augmented dataset with hard examples
    hard_dataset = HardExampleDataset(base_dataset, hard_indices, augment_factor=3)
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import json
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# Hard Example Miner
# ============================================================

class HardExampleMiner:
    """
    Online Hard Example Mining (OHEM) for segmentation.

    Tracks sample losses per epoch and selects hard examples for retraining.
    """

    def __init__(
        self,
        top_k_percent: float = 0.1,
        min_hard_samples: int = 50,
        max_hard_samples: int = 500,
        smoothing_window: int = 3,
        output_dir: str = "models/paddle_seg/output/hard_mining"
    ):
        """
        Initialize hard example miner.

        Args:
            top_k_percent: Percentage of samples to select as hard examples
            min_hard_samples: Minimum number of hard samples to select
            max_hard_samples: Maximum number of hard samples to select
            smoothing_window: Window for moving average of sample losses
            output_dir: Directory to save hard example information
        """
        self.top_k_percent = top_k_percent
        self.min_hard_samples = min_hard_samples
        self.max_hard_samples = max_hard_samples
        self.smoothing_window = smoothing_window
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Tracking data
        self.current_epoch = 0
        self.sample_losses = {}  # {sample_idx: deque of losses}
        self.epoch_hard_examples = {}  # {epoch: [indices]}
        self.sample_consistency = {}  # {sample_idx: times_selected}

        # Statistics
        self.mining_stats = {
            'epochs_processed': 0,
            'total_hard_samples_selected': 0,
            'avg_hard_samples_per_epoch': 0,
            'most_common_hard_samples': [],
        }

    def reset_epoch(self, epoch: int):
        """Reset for new epoch."""
        self.current_epoch = epoch
        logger.info(f"HardExampleMiner: Starting epoch {epoch}")

    def record_batch_loss(self, sample_indices: List[int], batch_loss: Any):
        """
        Record loss for a batch of samples.

        Args:
            sample_indices: List of dataset indices for samples in batch
            batch_loss: Loss tensor or float for the batch
        """
        import paddle

        # Convert to float if tensor
        if hasattr(batch_loss, 'numpy'):
            loss_value = float(batch_loss.numpy())
        elif hasattr(batch_loss, 'item'):
            loss_value = float(batch_loss.item())
        else:
            loss_value = float(batch_loss)

        # Record loss for each sample in the batch
        for idx in sample_indices:
            if idx not in self.sample_losses:
                self.sample_losses[idx] = deque(maxlen=self.smoothing_window)

            self.sample_losses[idx].append(loss_value)

    def get_smoothed_losses(self) -> Dict[int, float]:
        """Get smoothed average loss for each tracked sample."""
        smoothed = {}
        for idx, loss_deque in self.sample_losses.items():
            if len(loss_deque) > 0:
                smoothed[idx] = np.mean(list(loss_deque))
            else:
                smoothed[idx] = 0.0
        return smoothed

    def get_hard_examples(self, num_total_samples: int) -> List[int]:
        """
        Get hard example indices for the current epoch.

        Args:
            num_total_samples: Total number of samples in the dataset

        Returns:
            List of hard example indices
        """
        smoothed_losses = self.get_smoothed_losses()

        if len(smoothed_losses) == 0:
            logger.warning("No loss data collected yet. Returning empty list.")
            return []

        # Sort by loss (descending)
        sorted_indices = sorted(
            smoothed_losses.keys(),
            key=lambda idx: smoothed_losses[idx],
            reverse=True
        )

        # Calculate number of hard examples to select
        num_hard = int(len(sorted_indices) * self.top_k_percent)
        num_hard = max(self.min_hard_samples, min(num_hard, self.max_hard_samples))

        # Select top-k hard examples
        hard_indices = sorted_indices[:num_hard]

        # Store for this epoch
        self.epoch_hard_examples[self.current_epoch] = hard_indices

        # Update consistency tracking
        for idx in hard_indices:
            self.sample_consistency[idx] = self.sample_consistency.get(idx, 0) + 1

        # Log statistics
        avg_loss = np.mean([smoothed_losses[idx] for idx in hard_indices])
        logger.info(f"Epoch {self.current_epoch}: Selected {len(hard_indices)} hard examples")
        logger.info(f"  Average hard loss: {avg_loss:.4f}")
        logger.info(f"  Top 5 hardest samples: {hard_indices[:5]}")

        return hard_indices

    def get_persistent_hard_examples(self, min_occurrences: int = 2) -> List[int]:
        """
        Get samples that are consistently selected as hard examples.

        Args:
            min_occurrences: Minimum number of times a sample must be selected

        Returns:
            List of persistent hard example indices
        """
        persistent = [
            idx for idx, count in self.sample_consistency.items()
            if count >= min_occurrences
        ]
        return sorted(persistent, key=lambda idx: self.sample_consistency[idx], reverse=True)

    def get_sample_loss_history(self, sample_idx: int) -> List[float]:
        """Get loss history for a specific sample."""
        if sample_idx in self.sample_losses:
            return list(self.sample_losses[sample_idx])
        return []

    def update_statistics(self):
        """Update mining statistics."""
        self.mining_stats['epochs_processed'] = self.current_epoch

        if len(self.sample_consistency) > 0:
            self.mining_stats['total_hard_samples_selected'] = len(self.sample_consistency)
            self.mining_stats['avg_hard_samples_per_epoch'] = (
                sum(len(v) for v in self.epoch_hard_examples.values()) /
                max(1, len(self.epoch_hard_examples))
            )

            # Get most common hard samples
            sorted_by_consistency = sorted(
                self.sample_consistency.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self.mining_stats['most_common_hard_samples'] = [
                {'index': int(idx), 'times_selected': int(count)}
                for idx, count in sorted_by_consistency[:20]
            ]

    def save_hard_examples(self, epoch: int, hard_indices: List[int]):
        """
        Save hard example information to disk.

        Args:
            epoch: Current epoch number
            hard_indices: List of hard example indices
        """
        # Save hard example indices
        hard_file = self.output_dir / f"hard_examples_epoch_{epoch}.json"
        with open(hard_file, 'w') as f:
            json.dump({
                'epoch': epoch,
                'num_hard_examples': len(hard_indices),
                'hard_indices': hard_indices,
            }, f, indent=2)

        logger.info(f"Saved hard examples to {hard_file}")

    def load_hard_examples(self, epoch: int) -> List[int]:
        """Load hard example indices from disk."""
        hard_file = self.output_dir / f"hard_examples_epoch_{epoch}.json"
        if hard_file.exists():
            with open(hard_file, 'r') as f:
                data = json.load(f)
                return data['hard_indices']
        return []

    def save_statistics(self):
        """Save mining statistics to disk."""
        self.update_statistics()
        stats_file = self.output_dir / "mining_statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(self.mining_stats, f, indent=2)
        logger.info(f"Saved mining statistics to {stats_file}")

    def generate_report(self) -> str:
        """Generate a text report of hard example mining results."""
        self.update_statistics()

        report_lines = [
            "=" * 70,
            "Hard Example Mining Report",
            "=" * 70,
            "",
            f"Epochs Processed: {self.mining_stats['epochs_processed']}",
            f"Total Unique Hard Samples: {self.mining_stats['total_hard_samples_selected']}",
            f"Average Hard Samples per Epoch: {self.mining_stats['avg_hard_samples_per_epoch']:.1f}",
            "",
            "-" * 70,
            "Top 20 Most Persistent Hard Examples:",
            "-" * 70,
        ]

        for item in self.mining_stats['most_common_hard_samples'][:20]:
            idx = item['index']
            count = item['times_selected']
            loss_history = self.get_sample_loss_history(idx)
            avg_loss = np.mean(loss_history) if loss_history else 0
            report_lines.append(f"  Sample {idx:4d}: Selected {count:2d} times, Avg Loss: {avg_loss:.4f}")

        report_lines.extend([
            "",
            "-" * 70,
            "Hard Examples by Epoch:",
            "-" * 70,
        ])

        for epoch in sorted(self.epoch_hard_examples.keys()):
            hard_indices = self.epoch_hard_examples[epoch]
            report_lines.append(f"  Epoch {epoch:3d}: {len(hard_indices):3d} samples")

        report_lines.append("")
        report_lines.append("=" * 70)

        return "\n".join(report_lines)


# ============================================================
# Hard Example Dataset
# ============================================================

class HardExampleDataset:
    """
    Dataset wrapper that adds hard examples with augmentation.

    Creates an augmented dataset by:
    1. Including all base dataset samples
    2. Adding multiple augmented versions of hard examples
    """

    def __init__(
        self,
        base_dataset,
        hard_indices: List[int],
        augment_factor: int = 3,
        hard_sample_weight: float = 2.0
    ):
        """
        Initialize hard example dataset.

        Args:
            base_dataset: Original dataset to wrap
            hard_indices: List of hard example indices from base dataset
            augment_factor: Number of augmented copies per hard example
            hard_sample_weight: Sampling weight for hard examples
        """
        self.base_dataset = base_dataset
        self.hard_indices = set(hard_indices)
        self.augment_factor = augment_factor
        self.hard_sample_weight = hard_sample_weight

        # Dataset structure:
        # - First, all original samples
        # - Then, augmented versions of hard examples
        self.num_base_samples = len(base_dataset)
        self.num_hard_samples = len(hard_indices)
        self.num_augmented_hard = self.num_hard_samples * augment_factor
        self.total_samples = self.num_base_samples + self.num_augmented_hard

        # Create index mapping
        self.index_mapping = self._create_index_mapping()

        logger.info(f"HardExampleDataset: {self.num_base_samples} base + "
                   f"{self.num_augmented_hard} augmented hard = {self.total_samples} total")

    def _create_index_mapping(self) -> List[Tuple[int, int, int]]:
        """
        Create mapping from dataset index to (base_idx, aug_idx, is_hard).

        Returns:
            List of (base_index, augment_index, is_hard_flag) tuples
        """
        mapping = []

        # Add all base samples first
        for i in range(self.num_base_samples):
            is_hard = i in self.hard_indices
            mapping.append((i, 0, is_hard))

        # Add augmented hard examples
        for hard_idx in self.hard_indices:
            for aug_idx in range(1, self.augment_factor + 1):
                mapping.append((hard_idx, aug_idx, True))

        return mapping

    def __len__(self):
        return self.total_samples

    def __getitem__(self, idx):
        base_idx, aug_idx, is_hard = self.index_mapping[idx]

        # Get sample from base dataset
        image, mask = self.base_dataset[base_idx]

        # Apply augmentation for hard examples
        if aug_idx > 0:
            image, mask = self._augment_hard_sample(image, mask, aug_idx)

        return image, mask

    def _augment_hard_sample(self, image, mask, aug_idx: int):
        """
        Apply aggressive augmentation to hard examples.

        Args:
            image: Input image tensor/array
            mask: Input mask tensor/array
            aug_idx: Augmentation index (1-based)

        Returns:
            Augmented (image, mask) tuple
        """
        import numpy as np

        # Convert to numpy if tensor
        if hasattr(image, 'numpy'):
            image = image.numpy()
        if hasattr(mask, 'numpy'):
            mask = mask.numpy()

        # Ensure image is (H, W, C) for augmentation
        is_channel_first = image.shape[0] == 3 or image.shape[0] == 1
        if is_channel_first:
            image = np.transpose(image, (1, 2, 0))

        # Apply different augmentations based on aug_idx
        np.random.seed(42 + aug_idx)  # Deterministic augmentations

        if aug_idx == 1:
            # Geometric: Random flip + rotate
            if np.random.rand() > 0.5:
                image = np.fliplr(image).copy()
                mask = np.fliplr(mask).copy()

            # Small rotation
            angle = np.random.uniform(-15, 15)
            image = self._rotate_image(image, angle)
            mask = self._rotate_image(mask, angle)

        elif aug_idx == 2:
            # Color jitter (for image only)
            image = self._color_jitter(image, brightness=0.3, contrast=0.3)

            # Elastic-like distortion
            if np.random.rand() > 0.5:
                image = self._elastic_distortion(image, alpha=10, sigma=3)
                mask = self._elastic_distortion(mask, alpha=10, sigma=3)

        elif aug_idx == 3:
            # Crop and resize
            image, mask = self._random_crop_resize(image, mask, scale=0.8)

            # Gaussian noise
            if np.random.rand() > 0.5:
                noise = np.random.normal(0, 0.02, image.shape).astype(np.float32)
                image = np.clip(image + noise, 0, 1)

        # Convert back to original format
        if is_channel_first:
            image = np.transpose(image, (2, 0, 1))

        return image, mask

    @staticmethod
    def _rotate_image(image, angle):
        """Rotate image by angle."""
        from scipy.ndimage import rotate
        if len(image.shape) == 3:
            rotated = np.zeros_like(image)
            for c in range(image.shape[2]):
                rotated[:, :, c] = rotate(image[:, :, c], angle, reshape=False,
                                          mode='constant', order=1)
            return rotated
        else:
            return rotate(image, angle, reshape=False, mode='constant', order=0)

    @staticmethod
    def _color_jitter(image, brightness=0.2, contrast=0.2):
        """Apply color jittering to image."""
        # Brightness
        if brightness > 0:
            factor = 1.0 + np.random.uniform(-brightness, brightness)
            image = np.clip(image * factor, 0, 1)

        # Contrast
        if contrast > 0:
            mean = image.mean()
            factor = 1.0 + np.random.uniform(-contrast, contrast)
            image = np.clip((image - mean) * factor + mean, 0, 1)

        return image

    @staticmethod
    def _elastic_distortion(image, alpha=10, sigma=3):
        """Apply elastic distortion."""
        from scipy.ndimage import gaussian_filter
        shape = image.shape[:2]

        dx = gaussian_filter(np.random.randn(*shape), sigma, mode="constant") * alpha
        dy = gaussian_filter(np.random.randn(*shape), sigma, mode="constant") * alpha

        x, y = np.meshgrid(np.arange(shape[1]), np.arange(shape[0]))
        indices = np.reshape(y + dy, (-1, 1)), np.reshape(x + dx, (-1, 1))

        from scipy.ndimage import map_coordinates
        if len(image.shape) == 3:
            distorted = np.zeros_like(image)
            for c in range(image.shape[2]):
                distorted[:, :, c] = map_coordinates(
                    image[:, :, c], indices, order=1, mode='constant'
                ).reshape(shape)
            return distorted
        else:
            return map_coordinates(image, indices, order=0, mode='constant').reshape(shape)

    @staticmethod
    def _random_crop_resize(image, mask, scale=0.8):
        """Random crop and resize back to original size."""
        h, w = image.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)

        # Random crop position
        top = np.random.randint(0, h - new_h + 1)
        left = np.random.randint(0, w - new_w + 1)

        # Crop
        if len(image.shape) == 3:
            cropped = image[top:top+new_h, left:left+new_w, :]
        else:
            cropped = image[top:top+new_h, left:left+new_w]

        if len(mask.shape) == 3:
            mask_cropped = mask[top:top+new_h, left:left+new_w, :]
        else:
            mask_cropped = mask[top:top+new_h, left:left+new_w]

        # Resize back
        from PIL import Image
        if len(image.shape) == 3:
            image_resized = np.array(Image.fromarray((cropped * 255).astype(np.uint8)).resize(
                (w, h), Image.BILINEAR)) / 255.0
        else:
            image_resized = np.array(Image.fromarray((cropped * 255).astype(np.uint8)).resize(
                (w, h), Image.NEAREST)) / 255.0

        if len(mask.shape) == 3:
            mask_resized = np.array(Image.fromarray(mask_cropped.astype(np.uint8)).resize(
                (w, h), Image.NEAREST))
        else:
            mask_resized = np.array(Image.fromarray(mask_cropped.astype(np.uint8)).resize(
                (w, h), Image.NEAREST))

        return image_resized, mask_resized

    def get_sample_weights(self) -> List[float]:
        """
        Get sampling weights for DataLoader WeightedRandomSampler.

        Hard examples get higher weights.
        """
        weights = []
        for base_idx, aug_idx, is_hard in self.index_mapping:
            if is_hard:
                weights.append(self.hard_sample_weight)
            else:
                weights.append(1.0)
        return weights


# ============================================================
# Progressive Training Strategy
# ============================================================

class ProgressiveTrainingStrategy:
    """
    Progressive training strategy for BiSeNetV2.

    Strategy:
    - First 30 epochs: Train detail branch only (fine-grained features)
    - Remaining epochs: Joint training (full model)
    """

    def __init__(
        self,
        detail_epochs: int = 30,
        total_epochs: int = 80,
        detail_modules: Optional[List[str]] = None
    ):
        """
        Initialize progressive training strategy.

        Args:
            detail_epochs: Number of epochs to train detail branch only
            total_epochs: Total number of training epochs
            detail_modules: List of module names to freeze during joint training
        """
        self.detail_epochs = detail_epochs
        self.total_epochs = total_epochs
        self.detail_modules = detail_modules or [
            'detail_path', 'detail_head', 'conv1', 'conv2', 'conv3'
        ]

        self.current_phase = 'detail'  # 'detail' or 'joint'
        self.phase_history = []

    def get_phase(self, epoch: int) -> str:
        """
        Get current training phase.

        Args:
            epoch: Current epoch number

        Returns:
            'detail' or 'joint'
        """
        if epoch <= self.detail_epochs:
            return 'detail'
        else:
            return 'joint'

    def should_transition(self, epoch: int) -> bool:
        """Check if we should transition between phases."""
        current_phase = self.get_phase(epoch)
        return current_phase != self.current_phase

    def transition_phase(self, epoch: int, model):
        """
        Transition training phase.

        Args:
            epoch: Current epoch number
            model: Model to freeze/unfreeze parameters
        """
        new_phase = self.get_phase(epoch)

        if new_phase != self.current_phase:
            logger.info(f"Transitioning from {self.current_phase} to {new_phase} phase at epoch {epoch}")

            if new_phase == 'detail':
                self._freeze_for_detail_training(model)
            elif new_phase == 'joint':
                self._unfreeze_for_joint_training(model)

            self.phase_history.append({
                'epoch': epoch,
                'from': self.current_phase,
                'to': new_phase
            })

            self.current_phase = new_phase

    def _freeze_for_detail_training(self, model):
        """Freeze context path and fusion layers for detail training."""
        frozen_params = []
        for name, param in model.named_parameters():
            # Freeze context path and fusion modules
            if any(module in name for module in ['context', 'fusion', 'bottleneck']):
                param.trainable = False
                frozen_params.append(name)

        logger.info(f"Frozen {len(frozen_params)} parameters for detail training")
        logger.debug(f"Frozen: {frozen_params[:5]}...")

    def _unfreeze_for_joint_training(self, model):
        """Unfreeze all parameters for joint training."""
        for name, param in model.named_parameters():
            param.trainable = True

        logger.info("Unfroze all parameters for joint training")

    def get_learning_rate_multiplier(self, epoch: int) -> float:
        """
        Get learning rate multiplier for current phase.

        Detail phase uses lower LR, joint phase uses normal LR.
        """
        phase = self.get_phase(epoch)
        if phase == 'detail':
            return 0.5  # Lower LR for detail training
        else:
            return 1.0  # Normal LR for joint training


# ============================================================
# Utility Functions
# ============================================================

def visualize_hard_examples(
    dataset,
    hard_indices: List[int],
    output_path: str,
    num_samples: int = 20,
    predictions: Optional[List[np.ndarray]] = None
):
    """
    Visualize hard examples with predictions.

    Args:
        dataset: Dataset to get samples from
        hard_indices: List of hard example indices
        output_path: Path to save visualization
        num_samples: Number of samples to visualize
        predictions: Optional list of prediction masks
    """
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    num_viz = min(num_samples, len(hard_indices))

    fig = plt.figure(figsize=(20, 4 * num_viz))
    gs = GridSpec(num_viz, 5, figure=fig)

    for i, idx in enumerate(hard_indices[:num_viz]):
        image, mask = dataset[idx]

        # Convert to numpy if tensor
        if hasattr(image, 'numpy'):
            image = image.numpy()
        if hasattr(mask, 'numpy'):
            mask = mask.numpy()

        # Denormalize image if needed
        if image.max() <= 1.0 and image.min() >= 0:
            image_display = (image * 255).astype(np.uint8)
        else:
            image_display = image.astype(np.uint8)

        # Handle channel-first format
        if image_display.shape[0] == 3:
            image_display = np.transpose(image_display, (1, 2, 0))

        # Original image
        ax = fig.add_subplot(gs[i, 0])
        ax.imshow(image_display)
        ax.set_title(f"Sample {idx}")
        ax.axis('off')

        # Ground truth mask
        ax = fig.add_subplot(gs[i, 1])
        ax.imshow(mask, cmap='gray')
        ax.set_title("Ground Truth")
        ax.axis('off')

        # Overlay
        ax = fig.add_subplot(gs[i, 2])
        ax.imshow(image_display)
        ax.imshow(mask, cmap='jet', alpha=0.3)
        ax.set_title("GT Overlay")
        ax.axis('off')

        # Prediction (if available)
        if predictions and i < len(predictions):
            pred = predictions[i]
            ax = fig.add_subplot(gs[i, 3])
            ax.imshow(pred, cmap='gray')
            ax.set_title("Prediction")
            ax.axis('off')

            # Error overlay
            ax = fig.add_subplot(gs[i, 4])
            error = (pred != mask).astype(np.uint8) * 255
            ax.imshow(error, cmap='Reds')
            ax.set_title("Error Map")
            ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=100, bbox_inches='tight')
    plt.close()

    logger.info(f"Saved hard example visualization to {output_path}")


def compute_hard_example_metrics(
    hard_indices: List[int],
    losses: Dict[int, float],
    predictions: Optional[List[np.ndarray]] = None,
    ground_truths: Optional[List[np.ndarray]] = None
) -> Dict[str, Any]:
    """
    Compute metrics for hard examples.

    Args:
        hard_indices: List of hard example indices
        losses: Dictionary of sample indices to loss values
        predictions: Optional list of prediction masks
        ground_truths: Optional list of ground truth masks

    Returns:
        Dictionary of metrics
    """
    metrics = {
        'num_hard_samples': len(hard_indices),
        'hard_loss_mean': np.mean([losses.get(idx, 0) for idx in hard_indices]),
        'hard_loss_std': np.std([losses.get(idx, 0) for idx in hard_indices]),
        'hard_loss_max': np.max([losses.get(idx, 0) for idx in hard_indices]),
        'hard_loss_min': np.min([losses.get(idx, 0) for idx in hard_indices]),
    }

    if predictions and ground_truths:
        # Compute pixel-wise accuracy for hard examples
        accuracies = []
        ious = []

        for i, idx in enumerate(hard_indices):
            if i < len(predictions) and i < len(ground_truths):
                pred = predictions[i]
                gt = ground_truths[i]

                # Accuracy
                acc = (pred == gt).mean()
                accuracies.append(acc)

                # IoU for tongue class (assuming binary)
                intersection = np.logical_and(pred == 1, gt == 1).sum()
                union = np.logical_or(pred == 1, gt == 1).sum()
                iou = intersection / max(union, 1)
                ious.append(iou)

        metrics['hard_accuracy_mean'] = np.mean(accuracies)
        metrics['hard_iou_mean'] = np.mean(ious)
        metrics['hard_accuracy_min'] = np.min(accuracies)
        metrics['hard_iou_min'] = np.min(ious)

    return metrics


if __name__ == "__main__":
    # Quick test of the hard example miner
    print("Testing HardExampleMiner...")

    miner = HardExampleMiner(top_k_percent=0.1, max_hard_samples=100)

    # Simulate training for 5 epochs
    num_samples = 1000
    for epoch in range(1, 6):
        miner.reset_epoch(epoch)

        # Simulate batch losses
        for batch_start in range(0, num_samples, 32):
            batch_indices = list(range(batch_start, min(batch_start + 32, num_samples)))
            # Simulate random losses
            batch_loss = np.random.uniform(0.1, 1.0)

            miner.record_batch_loss(batch_indices, batch_loss)

        # Get hard examples for this epoch
        hard_indices = miner.get_hard_examples(num_samples)
        print(f"Epoch {epoch}: {len(hard_indices)} hard examples")

    # Generate and print report
    report = miner.generate_report()
    print("\n" + report)

    # Save statistics
    miner.save_statistics()
    print("\nHard example mining test completed!")
