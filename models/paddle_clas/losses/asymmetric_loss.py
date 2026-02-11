#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Asymmetric Loss Implementation for PaddlePaddle

Asymmetric Loss: Optimized for multi-label classification with:
- Different gamma for positive (gamma_pos) and negative (gamma_neg) examples
- Probabilistic margin to prevent overwhelming negative gradients

Reference:
Ben-Baruch et al. "Asymmetric Loss For Multi-Label Classification" (ICCV 2021)

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from typing import Optional


class AsymmetricLoss(nn.Layer):
    """Asymmetric Loss for multi-label classification

    Handles positive and negative examples asymmetrically:
    - Positive examples: focused with gamma_pos
    - Negative examples: down-weighted with gamma_neg
    - Probabilistic margin to limit negative gradients

    Args:
        gamma_pos (float): Focusing parameter for positive examples. Default: 0.0
            - 0.0 means no focusing on positives
            - Higher values increase focus on hard positives
        gamma_neg (float): Focusing parameter for negative examples. Default: 4.0
            - Higher values down-weight easy negatives more strongly
        clip (float): Margin for probabilistic clipping. Default: 0.05
            - Prevents overwhelming negative gradients
            - Values closer to 0 give more weight to negatives
        reduction (str): Reduction method: 'none', 'mean', 'sum'. Default: 'sum'
        disable_torch_grad_focal_loss (bool): Disable gradients for focal loss part. Default: False
    """

    def __init__(
        self,
        gamma_pos: float = 0.0,
        gamma_neg: float = 4.0,
        clip: float = 0.05,
        reduction: str = 'sum',
        disable_torch_grad_focal_loss: bool = False
    ):
        super().__init__()

        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg
        self.clip = clip
        self.reduction = reduction
        self.disable_torch_grad_focal_loss = disable_torch_grad_focal_loss

        # Validate parameters
        if gamma_pos < 0:
            raise ValueError(f"gamma_pos must be >= 0, got {gamma_pos}")
        if gamma_neg < 0:
            raise ValueError(f"gamma_neg must be >= 0, got {gamma_neg}")
        if not 0 <= clip <= 1:
            raise ValueError(f"clip must be in [0, 1], got {clip}")

    def forward(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor
    ) -> paddle.Tensor:
        """
        Compute asymmetric loss

        Args:
            pred: Predicted logits (N, C) - raw scores, not probabilities
            target: Ground truth (N, C) with values in {0, 1}

        Returns:
            Computed asymmetric loss
        """
        # Get probabilities using sigmoid
        xs = pred
        pt = F.sigmoid(xs)

        # Clip probabilities to prevent division issues
        pt = pt.clip(min=self.clip, max=1 - self.clip)

        # Separate positive and negative losses
        # For positive targets: -log(pt) * (1 - pt)^gamma_pos
        # For negative targets: -log(1 - pt) * pt^gamma_neg

        # Prevent log(0)
        epsilon = 1e-8

        # Loss for positive targets
        loss_pos = -target * paddle.log(pt + epsilon)
        if self.gamma_pos > 0:
            loss_pos = loss_pos * (1 - pt) ** self.gamma_pos

        # Loss for negative targets
        loss_neg = -(1 - target) * paddle.log(1 - pt + epsilon)
        if self.gamma_neg > 0:
            loss_neg = loss_neg * pt ** self.gamma_neg

        # Combine losses
        loss = loss_pos + loss_neg

        # Apply reduction
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else:
            return loss


class ASLSingleLabel(nn.Layer):
    """Asymmetric Loss adapted for single-label classification

    Uses asymmetric loss principles for single-label tasks by
    treating the true class as positive and others as negative.

    Args:
        gamma_pos (float): Focusing parameter for positive examples. Default: 0.0
        gamma_neg (float): Focusing parameter for negative examples. Default: 4.0
        clip (float): Margin for probabilistic clipping. Default: 0.05
        reduction (str): Reduction method. Default: 'mean'
    """

    def __init__(
        self,
        gamma_pos: float = 0.0,
        gamma_neg: float = 4.0,
        clip: float = 0.05,
        reduction: str = 'mean'
    ):
        super().__init__()

        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg
        self.clip = clip
        self.reduction = reduction

    def forward(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor
    ) -> paddle.Tensor:
        """
        Compute asymmetric loss for single-label classification

        Args:
            pred: Predicted logits (N, C)
            target: Ground truth class indices (N,)

        Returns:
            Computed asymmetric loss
        """
        num_classes = pred.shape[-1]

        # Convert target to one-hot
        if target.ndim == 1:
            target_one_hot = F.one_hot(target, num_classes=num_classes).astype('float32')
        else:
            target_one_hot = target.astype('float32')

        # Compute probabilities
        pt = F.softmax(pred, axis=-1)
        pt = pt.clip(min=self.clip, max=1 - self.clip)

        # Compute loss
        epsilon = 1e-8

        # Positive loss (true class)
        loss_pos = -target_one_hot * paddle.log(pt + epsilon)
        if self.gamma_pos > 0:
            loss_pos = loss_pos * (1 - pt) ** self.gamma_pos

        # Negative loss (other classes)
        loss_neg = -(1 - target_one_hot) * paddle.log(1 - pt + epsilon)
        if self.gamma_neg > 0:
            loss_neg = loss_neg * pt ** self.gamma_neg

        loss = loss_pos + loss_neg

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


class AsymmetricLossEnhanced(nn.Layer):
    """Enhanced Asymmetric Loss with additional features

    Adds label smoothing and class weighting capabilities.

    Args:
        gamma_pos (float): Focusing parameter for positives. Default: 0.0
        gamma_neg (float): Focusing parameter for negatives. Default: 4.0
        clip (float): Margin for clipping. Default: 0.05
        reduction (str): Reduction method. Default: 'sum'
        label_smoothing (float): Label smoothing factor. Default: 0.0
        class_weights (paddle.Tensor): Per-class weights. Default: None
    """

    def __init__(
        self,
        gamma_pos: float = 0.0,
        gamma_neg: float = 4.0,
        clip: float = 0.05,
        reduction: str = 'sum',
        label_smoothing: float = 0.0,
        class_weights: Optional[paddle.Tensor] = None
    ):
        super().__init__()

        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg
        self.clip = clip
        self.reduction = reduction
        self.label_smoothing = label_smoothing
        self.class_weights = class_weights

    def forward(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor
    ) -> paddle.Tensor:
        """Compute enhanced asymmetric loss"""
        # Apply label smoothing if enabled
        if self.label_smoothing > 0:
            target = target * (1 - self.label_smoothing) + \
                     (1 - target) * self.label_smoothing / (pred.shape[-1] - 1)

        # Get probabilities
        pt = F.sigmoid(pred)
        pt = pt.clip(min=self.clip, max=1 - self.clip)

        epsilon = 1e-8

        # Compute asymmetric loss
        loss_pos = -target * paddle.log(pt + epsilon)
        loss_neg = -(1 - target) * paddle.log(1 - pt + epsilon)

        if self.gamma_pos > 0:
            loss_pos = loss_pos * (1 - pt) ** self.gamma_pos
        if self.gamma_neg > 0:
            loss_neg = loss_neg * pt ** self.gamma_neg

        loss = loss_pos + loss_neg

        # Apply class weights if provided
        if self.class_weights is not None:
            # Weight by target labels
            loss = loss * self.class_weights

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        return loss


if __name__ == "__main__":
    # Test asymmetric loss
    print("Testing Asymmetric Loss Implementation...")

    # Create sample data (multi-label)
    batch_size = 4
    num_classes = 4

    pred = paddle.randn([batch_size, num_classes])
    target = paddle.randint(0, 2, [batch_size, num_classes]).astype('float32')

    # Test standard asymmetric loss
    asl_loss = AsymmetricLoss(gamma_pos=0.0, gamma_neg=4.0, clip=0.05)
    loss = asl_loss(pred, target)
    print(f"Standard Asymmetric Loss: {loss.item():.4f}")

    # Test single-label variant
    target_single = paddle.randint(0, num_classes, [batch_size])
    asl_single = ASLSingleLabel(gamma_pos=0.0, gamma_neg=4.0)
    loss_single = asl_single(pred, target_single)
    print(f"Single-Label Asymmetric Loss: {loss_single.item():.4f}")

    # Test enhanced version with label smoothing
    asl_enhanced = AsymmetricLossEnhanced(
        gamma_pos=0.0,
        gamma_neg=4.0,
        label_smoothing=0.1
    )
    loss_enhanced = asl_enhanced(pred, target)
    print(f"Enhanced Asymmetric Loss: {loss_enhanced.item():.4f}")

    # Test with class weights
    class_weights = paddle.to_tensor([0.5, 1.0, 2.0, 3.0])
    asl_weighted = AsymmetricLossEnhanced(
        gamma_pos=0.0,
        gamma_neg=4.0,
        class_weights=class_weights
    )
    loss_weighted = asl_weighted(pred, target)
    print(f"Weighted Asymmetric Loss: {loss_weighted.item():.4f}")

    print("\nAsymmetric Loss implementation test completed!")
