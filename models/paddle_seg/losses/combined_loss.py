#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Combined Loss Function for Tongue Segmentation

Combines CrossEntropy, Dice, and Boundary losses for improved segmentation.
Particularly effective for medical image segmentation with class imbalance.

task-2-2: 分割损失函数配置与优化

Loss Components:
- CrossEntropy Loss (0.5): Pixel-wise classification with class weights
- Dice Loss (0.3): Overlap-based loss for better boundary handling
- Boundary Loss (0.2): Edge-aware loss for sharper tongue boundaries

Usage:
    from models.paddle_seg.losses.combined_loss import CombinedLoss

    criterion = CombinedLoss(
        num_classes=2,
        ce_weight=0.5,
        dice_weight=0.3,
        boundary_weight=0.2,
        class_weights=None,  # Will be calculated from dataset
        ignore_index=255
    )

    loss = criterion(logits, target)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import paddle
import paddle.nn as nn
import paddle.nn.functional as F
import numpy as np
import logging

logger = logging.getLogger(__name__)


class DiceLoss(nn.Layer):
    """
    Dice Loss for segmentation tasks.

    Dice Loss = 1 - (2 * |X ∩ Y| + smooth) / (|X| + |Y| + smooth)

    Where:
    - X is the predicted segmentation
    - Y is the ground truth
    - smooth is a smoothing constant to avoid division by zero

    Reference:
        Sudre et al. "Generalised Dice overlap as a deep learning loss
        function for imbalanced segmentations." MICCAI 2017.
    """

    def __init__(self, ignore_index=255, smooth=1e-5):
        """
        Initialize Dice Loss.

        Args:
            ignore_index: Index to ignore in loss calculation
            smooth: Smoothing constant for numerical stability
        """
        super().__init__()
        self.ignore_index = ignore_index
        self.smooth = smooth

    def forward(self, logits, target, class_weights=None):
        """
        Calculate Dice loss.

        Args:
            logits: Model output of shape (N, C, H, W)
            target: Ground truth of shape (N, H, W) with values in [0, C-1]
            class_weights: Optional class weights of shape (C,)

        Returns:
            Dice loss value
        """
        # Get probabilities
        probs = F.softmax(logits, axis=1)

        # Handle ignore index BEFORE one_hot encoding
        # Create a mask for valid pixels (not ignore_index)
        mask = (target != self.ignore_index)
        mask = mask.unsqueeze(1).astype('float32')  # (N, 1, H, W)

        # Replace ignore_index with 0 (or any valid class) for one_hot
        # These will be masked out later anyway
        target_clean = target.clone()
        target_clean = paddle.where(mask.squeeze(1).astype('bool'),
                                   target_clean,
                                   paddle.zeros_like(target_clean))

        # Convert target to one-hot encoding
        num_classes = logits.shape[1]
        target_one_hot = F.one_hot(target_clean, num_classes=num_classes)
        # Transpose to match logits shape: (N, H, W, C) -> (N, C, H, W)
        target_one_hot = target_one_hot.transpose([0, 3, 1, 2])

        # Calculate intersection and union
        intersection = (probs * target_one_hot * mask).sum(axis=[0, 2, 3])  # (C,)
        pred_sum = (probs * mask).sum(axis=[0, 2, 3])  # (C,)
        target_sum = (target_one_hot * mask).sum(axis=[0, 2, 3])  # (C,)

        # Calculate Dice coefficient for each class
        dice = (2.0 * intersection + self.smooth) / (
            pred_sum + target_sum + self.smooth
        )

        # Handle classes with no samples
        valid_classes = target_sum > 0
        dice = dice * valid_classes.astype(dice.dtype)

        # Apply class weights if provided
        if class_weights is not None:
            class_weights = paddle.to_tensor(class_weights, dtype='float32')
            dice = dice * class_weights
            weighted_dice = dice.sum() / class_weights.sum()
        else:
            weighted_dice = dice.sum() / valid_classes.astype('float32').sum().clip(min=1)

        return 1.0 - weighted_dice


class BoundaryLoss(nn.Layer):
    """
    Boundary Loss for sharpening segmentation boundaries.

    This loss focuses on the boundary regions of the segmentation,
    encouraging the model to produce more precise boundaries.

    Uses distance-weighted boundary loss with exponential decay.
    """

    def __init__(self, ignore_index=255, theta=3, smooth=1e-5):
        """
        Initialize Boundary Loss.

        Args:
            ignore_index: Index to ignore in loss calculation
            theta: Distance decay parameter (larger = wider boundary focus)
            smooth: Smoothing constant for numerical stability
        """
        super().__init__()
        self.ignore_index = ignore_index
        self.theta = theta
        self.smooth = smooth

        # Sobel filters for edge detection
        self.register_buffer(
            'sobel_x',
            paddle.to_tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]],
                           dtype='float32').reshape([1, 1, 3, 3])
        )
        self.register_buffer(
            'sobel_y',
            paddle.to_tensor([[-1, -2, -1], [0, 0, 0], [1, 2, 1]],
                           dtype='float32').reshape([1, 1, 3, 3])
        )

    def _compute_edges(self, mask):
        """
        Compute edges using Sobel filters.

        Args:
            mask: Binary mask of shape (N, 1, H, W) or (N, H, W)

        Returns:
            Edge map of shape (N, 1, H, W)
        """
        if mask.dim() == 3:
            mask = mask.unsqueeze(1)

        # Apply Sobel filters
        edges_x = F.conv2d(mask.astype('float32'), self.sobel_x, padding=1)
        edges_y = F.conv2d(mask.astype('float32'), self.sobel_y, padding=1)

        # Compute gradient magnitude
        edges = paddle.sqrt(edges_x ** 2 + edges_y ** 2 + self.smooth)

        return edges

    def forward(self, logits, target, class_weights=None):
        """
        Calculate Boundary loss.

        Args:
            logits: Model output of shape (N, C, H, W)
            target: Ground truth of shape (N, H, W) with values in [0, C-1]
            class_weights: Optional class weights (not used in boundary loss)

        Returns:
            Boundary loss value
        """
        # Get predictions
        probs = F.softmax(logits, axis=1)

        # Extract foreground class probability (tongue class)
        # Assuming binary segmentation: 0=background, 1=tongue
        pred_foreground = probs[:, 1:2, :, :]  # (N, 1, H, W)
        target_foreground = (target == 1).astype('float32').unsqueeze(1)  # (N, 1, H, W)

        # Handle ignore index
        mask = (target != self.ignore_index).astype('float32').unsqueeze(1)

        # Compute edges for both prediction and target
        pred_edges = self._compute_edges(pred_foreground)
        target_edges = self._compute_edges(target_foreground)

        # Boundary regions: edges in target
        boundary_mask = target_edges * mask

        # Loss on boundary regions
        # Penalize differences between predicted and target edges
        boundary_diff = paddle.abs(pred_edges - target_edges)

        # Apply boundary mask
        boundary_loss = (boundary_diff * boundary_mask).sum() / (boundary_mask.sum().clip(min=1) + self.smooth)

        # Normalize by theta
        boundary_loss = boundary_loss / self.theta

        return boundary_loss


class CombinedLoss(nn.Layer):
    """
    Combined Loss for tongue segmentation.

    Combines CrossEntropy, Dice, and Boundary losses with configurable weights.

    Loss = w_ce * CE_loss + w_dice * Dice_loss + w_boundary * Boundary_loss

    Benefits:
    - CrossEntropy: Pixel-wise classification with class weights for imbalance
    - Dice: Overlap-based loss, robust to class imbalance
    - Boundary: Sharpens tongue boundaries for precise segmentation

    Reference:
        - Taghanaki et al. "Boundary loss for highly unbalanced segmentation"
          MICCAI 2019.
    """

    def __init__(
        self,
        num_classes=2,
        ce_weight=0.5,
        dice_weight=0.3,
        boundary_weight=0.2,
        class_weights=None,
        ignore_index=255,
        boundary_theta=3
    ):
        """
        Initialize Combined Loss.

        Args:
            num_classes: Number of segmentation classes
            ce_weight: Weight for CrossEntropy loss
            dice_weight: Weight for Dice loss
            boundary_weight: Weight for Boundary loss
            class_weights: Class weights for CrossEntropy (shape: num_classes,)
                          If None, will be set based on dataset statistics
            ignore_index: Index to ignore in loss calculation
            boundary_theta: Theta parameter for Boundary loss
        """
        super().__init__()
        self.num_classes = num_classes
        self.ce_weight = ce_weight
        self.dice_weight = dice_weight
        self.boundary_weight = boundary_weight
        self.ignore_index = ignore_index

        # Initialize loss components
        # Note: Using functional API for CrossEntropy to support (N, C, H, W) input
        self.dice_loss = DiceLoss(ignore_index=ignore_index)
        self.boundary_loss = BoundaryLoss(
            ignore_index=ignore_index,
            theta=boundary_theta
        )

        # Store class weights for CrossEntropy
        self.class_weights = None
        if class_weights is not None:
            self.class_weights = paddle.to_tensor(
                class_weights, dtype='float32'
            )

        logger.info(f"CombinedLoss initialized:")
        logger.info(f"  - CrossEntropy weight: {ce_weight}")
        logger.info(f"  - Dice weight: {dice_weight}")
        logger.info(f"  - Boundary weight: {boundary_weight}")
        logger.info(f"  - Num classes: {num_classes}")
        logger.info(f"  - Class weights: {class_weights}")

    def set_class_weights(self, class_weights):
        """
        Set class weights dynamically (e.g., from dataset statistics).

        Args:
            class_weights: Class weights of shape (num_classes,)
        """
        self.class_weights = paddle.to_tensor(class_weights, dtype='float32')
        logger.info(f"Updated class weights: {class_weights}")

    def _cross_entropy_loss(self, logits, target):
        """
        Calculate CrossEntropy loss using functional API.

        This allows using (N, C, H, W) logits with (N, H, W) targets.

        Args:
            logits: Model output of shape (N, C, H, W)
            target: Ground truth of shape (N, H, W)

        Returns:
            CrossEntropy loss value
        """
        # Use functional API with axis=1 for (N, C, H, W) input
        return F.cross_entropy(
            logits,
            target,
            ignore_index=self.ignore_index if self.ignore_index is not None else -100,
            axis=1
        )

    def forward(self, logits, target):
        """
        Calculate combined loss.

        Args:
            logits: Model output of shape (N, C, H, W)
            target: Ground truth of shape (N, H, W) with values in [0, C-1]

        Returns:
            Combined loss value (dictionary with individual losses)
        """
        # Calculate individual losses
        ce = self._cross_entropy_loss(logits, target)
        dice = self.dice_loss(logits, target, self.class_weights)
        boundary = self.boundary_loss(logits, target)

        # Combined loss
        total_loss = (
            self.ce_weight * ce +
            self.dice_weight * dice +
            self.boundary_weight * boundary
        )

        # Return loss dictionary for logging
        return {
            'loss': total_loss,
            'ce_loss': ce,
            'dice_loss': dice,
            'boundary_loss': boundary
        }


def calculate_class_weights_from_dataset(dataset_root, num_classes=2):
    """
    Calculate class weights from dataset statistics for handling imbalance.

    Weight formula: w_i = total / (num_classes × count_i)

    Args:
        dataset_root: Path to dataset root directory
        num_classes: Number of classes

    Returns:
        List of class weights
    """
    from pathlib import Path
    from collections import Counter

    dataset_root = Path(dataset_root)
    masks_dir = dataset_root / "train" / "masks"

    if not masks_dir.exists():
        logger.warning(f"Masks directory not found: {masks_dir}")
        # Return equal weights
        return [1.0] * num_classes

    # Count pixels for each class
    class_counts = np.zeros(num_classes, dtype=np.int64)

    mask_files = list(masks_dir.glob("*.png"))
    logger.info(f"Analyzing {len(mask_files)} masks for class weights...")

    for mask_path in mask_files:
        try:
            from PIL import Image
            mask = Image.open(mask_path)
            mask_array = np.array(mask)

            # Count pixels for each class (assuming binary: 0 and 255)
            # Normalize to 0 and 1
            mask_normalized = (mask_array > 127).astype(np.int64)

            for i in range(num_classes):
                class_counts[i] += (mask_normalized == i).sum()

        except Exception as e:
            logger.warning(f"Error processing {mask_path}: {e}")
            continue

    # Calculate weights
    total_pixels = class_counts.sum()
    class_weights = []

    for i in range(num_classes):
        if class_counts[i] == 0:
            weight = 10.0  # High weight for unseen classes
        else:
            weight = total_pixels / (num_classes * class_counts[i])
        class_weights.append(weight)

    logger.info(f"Class pixel counts: {class_counts}")
    logger.info(f"Calculated class weights: {class_weights}")

    return class_weights


# Test the loss functions
if __name__ == "__main__":
    # Fix Windows console encoding
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 60)
    logger.info("Testing Combined Loss Function")
    logger.info("=" * 60)

    # Create dummy data
    batch_size = 4
    num_classes = 2
    height, width = 128, 128

    # Random logits and targets
    logits = paddle.randn([batch_size, num_classes, height, width])
    target = paddle.randint(0, num_classes, [batch_size, height, width])

    logger.info(f"Input shapes:")
    logger.info(f"  Logits: {logits.shape}")
    logger.info(f"  Target: {target.shape}")

    # Test CombinedLoss
    loss_fn = CombinedLoss(
        num_classes=num_classes,
        ce_weight=0.5,
        dice_weight=0.3,
        boundary_weight=0.2,
        ignore_index=255
    )

    losses = loss_fn(logits, target)

    logger.info(f"\nLoss values:")
    logger.info(f"  Total: {losses['loss'].item():.4f}")
    logger.info(f"  CrossEntropy: {losses['ce_loss'].item():.4f}")
    logger.info(f"  Dice: {losses['dice_loss'].item():.4f}")
    logger.info(f"  Boundary: {losses['boundary_loss'].item():.4f}")

    logger.info("\n" + "=" * 60)
    logger.info("Combined Loss test completed successfully!")
    logger.info("=" * 60)
