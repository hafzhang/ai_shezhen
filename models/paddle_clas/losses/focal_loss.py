#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Focal Loss Implementation for PaddlePaddle

Focal Loss: FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)

Helps focus training on hard examples by down-weighting easy examples.
Particularly useful for imbalanced datasets.

Reference:
Lin et al. "Focal Loss for Dense Object Detection" (ICCV 2017)

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from typing import Optional, Union


class FocalLoss(nn.Layer):
    """Focal Loss for addressing class imbalance

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)

    Args:
        alpha (float): Weighting factor in range (0, 1). Default: 0.25
            - Balances positive/negative examples
            - Higher alpha gives more weight to positive class
        gamma (float): Focusing parameter. Default: 2.0
            - gamma >= 0 reduces relative loss for well-classified examples
            - gamma = 0: equivalent to cross-entropy
            - Higher gamma increases focus on hard examples
        reduction (str): Reduction method: 'none', 'mean', 'sum'. Default: 'mean'
        class_weights (paddle.Tensor): Per-class weights (C,). Default: None
        ignore_index (int): Target value to ignore. Default: -100
    """

    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = 'mean',
        class_weights: Optional[paddle.Tensor] = None,
        ignore_index: int = -100
    ):
        super().__init__()

        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        self.class_weights = class_weights
        self.ignore_index = ignore_index

        # Validate parameters
        if not 0 < alpha < 1:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if gamma < 0:
            raise ValueError(f"gamma must be >= 0, got {gamma}")
        if reduction not in ['none', 'mean', 'sum']:
            raise ValueError(f"reduction must be 'none', 'mean', or 'sum', got {reduction}")

    def forward(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor
    ) -> paddle.Tensor:
        """
        Compute focal loss

        Args:
            pred: Predicted logits (N, C) or (N, C, H, W)
            target: Ground truth labels (N,) or (N, H, W) with class indices
                   or (N, C) or (N, C, H, W) with one-hot encoding

        Returns:
            Computed focal loss
        """
        # Handle different input shapes
        if pred.ndim == 4:  # (N, C, H, W)
            # Flatten spatial dimensions
            pred = pred.transpose([0, 2, 3, 1])  # (N, H, W, C)
            pred = pred.reshape([-1, pred.shape[-1]])  # (N*H*W, C)

            if target.ndim == 3:  # (N, H, W) class indices
                target = target.reshape([-1])
            elif target.ndim == 4:  # (N, C, H, W) one-hot
                target = target.transpose([0, 2, 3, 1])
                target = target.reshape([-1, target.shape[-1]])

        # Ensure target is class indices (not one-hot)
        if target.ndim == pred.ndim:
            # Target is one-hot, convert to indices
            target = target.argmax(axis=-1)

        # Get number of classes
        num_classes = pred.shape[-1]

        # Convert to one-hot for probability calculation
        # Ignore mask
        mask = target != self.ignore_index

        # Filter out ignored indices
        if mask.any():
            pred = pred[mask]
            target = target[mask]
        else:
            # All samples are ignored
            return paddle.to_tensor(0.0, dtype=pred.dtype)

        # Compute softmax probabilities
        probs = F.softmax(pred, axis=-1)

        # Get probabilities for true class
        target_one_hot = F.one_hot(target, num_classes=num_classes)
        p_t = (probs * target_one_hot).sum(axis=-1)

        # Compute focal weight: (1 - p_t)^gamma
        focal_weight = (1 - p_t) ** self.gamma

        # Compute log likelihood
        log_p_t = paddle.log(p_t.clip(min=1e-8))

        # Compute focal loss for each sample
        loss = -self.alpha * focal_weight * log_p_t

        # Apply class weights if provided
        if self.class_weights is not None:
            # Get weights for each target
            weights = self.class_weights[target]
            loss = loss * weights

        # Apply reduction
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else:
            return loss


class FocalLossBinary(nn.Layer):
    """Binary Focal Loss for multi-label tasks

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
              - (1 - alpha_t) * p_t^gamma * log(1 - p_t)

    Args:
        alpha (float): Weighting factor for positive class. Default: 0.25
        gamma (float): Focusing parameter. Default: 2.0
        reduction (str): Reduction method: 'none', 'mean', 'sum'. Default: 'mean'
        pos_weight (float): Positive class weight. Default: 1.0
    """

    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = 'mean',
        pos_weight: float = 1.0
    ):
        super().__init__()

        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        self.pos_weight = pos_weight

    def forward(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor
    ) -> paddle.Tensor:
        """
        Compute binary focal loss

        Args:
            pred: Predicted logits (N, C) - raw scores, not probabilities
            target: Ground truth (N, C) with values in {0, 1}

        Returns:
            Computed binary focal loss
        """
        # Compute sigmoid probabilities
        bce_loss = F.binary_cross_entropy_with_logits(
            pred, target, reduction='none'
        )

        # Compute probabilities
        p_t = paddle.sigmoid(pred)

        # Separate positive and negative examples
        p_t = target * p_t + (1 - target) * (1 - p_t)

        # Compute focal weight
        focal_weight = (1 - p_t) ** self.gamma

        # Combine with BCE loss
        focal_loss = focal_weight * bce_loss

        # Apply positive weight
        focal_loss = focal_loss * (target * self.pos_weight + (1 - target))

        # Apply reduction
        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss


class AdaptiveFocalLoss(nn.Layer):
    """Adaptive Focal Loss with dynamic alpha

    Adjusts alpha based on class frequency to handle
    varying levels of class imbalance.

    Args:
        gamma (float): Focusing parameter. Default: 2.0
        reduction (str): Reduction method. Default: 'mean'
        class_counts (paddle.Tensor): Number of samples per class
    """

    def __init__(
        self,
        gamma: float = 2.0,
        reduction: str = 'mean',
        class_counts: Optional[paddle.Tensor] = None
    ):
        super().__init__()

        self.gamma = gamma
        self.reduction = reduction

        # Compute adaptive alpha from class counts
        if class_counts is not None:
            total = class_counts.sum()
            # Inverse frequency weighting
            self.alpha = (1 / class_counts) / (1 / class_counts).sum()
            self.register_buffer('class_weights', self.alpha)
        else:
            self.register_buffer('class_weights', None)

    def forward(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor
    ) -> paddle.Tensor:
        """Compute adaptive focal loss"""
        # Use standard focal loss with adaptive alpha
        num_classes = pred.shape[-1]

        if target.ndim == pred.ndim:
            target = target.argmax(axis=-1)

        probs = F.softmax(pred, axis=-1)
        target_one_hot = F.one_hot(target, num_classes=num_classes)
        p_t = (probs * target_one_hot).sum(axis=-1)

        focal_weight = (1 - p_t) ** self.gamma
        log_p_t = paddle.log(p_t.clip(min=1e-8))

        loss = -focal_weight * log_p_t

        # Apply adaptive class weights
        if self.class_weights is not None:
            weights = self.class_weights[target]
            loss = loss * weights

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


if __name__ == "__main__":
    # Test focal loss
    print("Testing Focal Loss Implementation...")

    # Create sample data
    batch_size = 4
    num_classes = 4

    pred = paddle.randn([batch_size, num_classes])
    target = paddle.randint(0, num_classes, [batch_size])

    # Test standard focal loss
    focal_loss = FocalLoss(alpha=0.25, gamma=2.0)
    loss = focal_loss(pred, target)
    print(f"Standard Focal Loss: {loss.item():.4f}")

    # Test binary focal loss
    pred_binary = paddle.randn([batch_size, num_classes])
    target_binary = paddle.randint(0, 2, [batch_size, num_classes]).astype('float32')

    focal_binary = FocalLossBinary(alpha=0.25, gamma=2.0)
    loss_binary = focal_binary(pred_binary, target_binary)
    print(f"Binary Focal Loss: {loss_binary.item():.4f}")

    # Test with class weights
    class_weights = paddle.to_tensor([0.5, 1.0, 2.0, 3.0])
    focal_weighted = FocalLoss(alpha=0.25, gamma=2.0, class_weights=class_weights)
    loss_weighted = focal_weighted(pred, target)
    print(f"Weighted Focal Loss: {loss_weighted.item():.4f}")

    print("\nFocal Loss implementation test completed!")
