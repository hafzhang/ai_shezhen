#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi-Task Loss Function for Tongue Diagnosis Classification

Combines losses from all 6 diagnostic heads with proper weighting:
- Head 1: 舌色 (Tongue Color) - 4 classes
- Head 2: 苔色 (Coating Color) - 4 classes
- Head 3: 舌形 (Tongue Shape) - 3 classes
- Head 4: 苔质 (Coating Quality) - 3 classes
- Head 5: 特征 (Special Features) - 4 classes (multi-label)
- Head 6: 健康状态 (Health Status) - 2 classes

Loss types:
- FocalLoss: For single-label classification with class imbalance
- AsymmetricLoss: For multi-label classification (features head)
- CrossEntropyLoss: Standard baseline

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
import json

from .focal_loss import FocalLoss, FocalLossBinary
from .asymmetric_loss import AsymmetricLoss


# ============================================================================
# Configuration Data Classes
# ============================================================================

@dataclass
class HeadLossConfig:
    """Configuration for loss computation of a single head"""
    head_name: str
    num_classes: int
    multi_label: bool
    task_weight: float  # Weight for this task in multi-task loss
    loss_type: str  # "focal", "asymmetric", "ce"
    focal_alpha: float = 0.25
    focal_gamma: float = 2.0
    asymmetric_gamma_pos: float = 0.0
    asymmetric_gamma_neg: float = 4.0
    asymmetric_clip: float = 0.05
    class_weights: Optional[paddle.Tensor] = None


# Default task weights from PRD
# Head1: 0.4 (舌色)
# Head2: 0.35 (苔色)
# Head3: 0.25 (舌形)
DEFAULT_TASK_WEIGHTS = {
    "tongue_color": 0.25,
    "coating_color": 0.20,
    "tongue_shape": 0.15,
    "coating_quality": 0.15,
    "features": 0.15,
    "health": 0.10
}


# ============================================================================
# Multi-Task Loss Implementation
# ============================================================================

class MultiTaskLoss(nn.Layer):
    """Multi-task loss for tongue diagnosis classification

    Combines losses from all 6 diagnostic heads with configurable:
    - Task weights (relative importance of each head)
    - Loss types (Focal, Asymmetric, or CrossEntropy)
    - Class weights (for handling imbalance)
    - Focal/Asymmetric loss parameters

    Args:
        head_configs: List of HeadLossConfig for each head
        loss_aggregation: How to combine task losses ('weighted_sum', 'sum', 'mean')
        focal_alpha: Default alpha for FocalLoss. Default: 0.25
        focal_gamma: Default gamma for FocalLoss. Default: 2.0
        asymmetric_gamma_pos: Default gamma_pos for AsymmetricLoss. Default: 0.0
        asymmetric_gamma_neg: Default gamma_neg for AsymmetricLoss. Default: 4.0
        asymmetric_clip: Default clip for AsymmetricLoss. Default: 0.05
    """

    def __init__(
        self,
        head_configs: List[HeadLossConfig],
        loss_aggregation: str = 'weighted_sum',
        focal_alpha: float = 0.25,
        focal_gamma: float = 2.0,
        asymmetric_gamma_pos: float = 0.0,
        asymmetric_gamma_neg: float = 4.0,
        asymmetric_clip: float = 0.05
    ):
        super().__init__()

        self.head_configs = {cfg.head_name: cfg for cfg in head_configs}
        self.loss_aggregation = loss_aggregation

        # Store default parameters
        self.focal_alpha = focal_alpha
        self.focal_gamma = focal_gamma
        self.asymmetric_gamma_pos = asymmetric_gamma_pos
        self.asymmetric_gamma_neg = asymmetric_gamma_neg
        self.asymmetric_clip = asymmetric_clip

        # Build loss functions for each head
        self.loss_functions = nn.LayerDict()
        self._build_loss_functions()

        # Compute total task weight for normalization
        total_weight = sum(cfg.task_weight for cfg in head_configs)
        self.total_task_weight = total_weight

    def _build_loss_functions(self):
        """Build loss function for each head based on its configuration"""
        for head_name, cfg in self.head_configs.items():
            if cfg.multi_label:
                # Multi-label task: use AsymmetricLoss or Binary Focal
                if cfg.loss_type == "asymmetric":
                    loss_fn = AsymmetricLoss(
                        gamma_pos=cfg.asymmetric_gamma_pos,
                        gamma_neg=cfg.asymmetric_gamma_neg,
                        clip=cfg.asymmetric_clip,
                        reduction='mean'
                    )
                elif cfg.loss_type == "focal":
                    loss_fn = FocalLossBinary(
                        alpha=cfg.focal_alpha,
                        gamma=cfg.focal_gamma,
                        reduction='mean'
                    )
                else:
                    # Default to BCE
                    loss_fn = nn.BCEWithLogitsLoss(reduction='mean')
            else:
                # Single-label task: use FocalLoss or CE
                if cfg.loss_type == "focal":
                    loss_fn = FocalLoss(
                        alpha=cfg.focal_alpha,
                        gamma=cfg.focal_gamma,
                        reduction='mean',
                        class_weights=cfg.class_weights
                    )
                else:
                    # Default to CE
                    loss_fn = nn.CrossEntropyLoss(
                        weight=cfg.class_weights,
                        reduction='mean'
                    )

            self.loss_functions[head_name] = loss_fn

    def forward(
        self,
        predictions: Dict[str, paddle.Tensor],
        targets: Dict[str, paddle.Tensor],
        head_names: Optional[List[str]] = None
    ) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor]]:
        """
        Compute multi-task loss

        Args:
            predictions: Dictionary mapping head_name -> prediction tensor
            targets: Dictionary mapping head_name -> target tensor
            head_names: List of heads to compute (None = all)

        Returns:
            Tuple of (total_loss, per_head_losses)
        """
        if head_names is None:
            head_names = list(self.head_configs.keys())

        per_head_losses = {}
        weighted_losses = []

        for head_name in head_names:
            if head_name not in predictions or head_name not in targets:
                continue

            pred = predictions[head_name]
            target = targets[head_name]
            cfg = self.head_configs[head_name]

            # Compute loss for this head
            loss_fn = self.loss_functions[head_name]

            # Handle target format for multi-label
            if cfg.multi_label:
                # Ensure target is float for BCE/AsymmetricLoss
                if target.dtype != paddle.float32:
                    target = target.astype('float32')
                head_loss = loss_fn(pred, target)
            else:
                # For single-label, ensure target is class indices
                if target.ndim > 1:
                    target = target.argmax(axis=-1)
                if target.dtype != paddle.int64:
                    target = target.astype('int64')
                head_loss = loss_fn(pred, target)

            per_head_losses[head_name] = head_loss

            # Apply task weight
            weighted_loss = cfg.task_weight * head_loss
            weighted_losses.append(weighted_loss)

        # Aggregate losses
        if self.loss_aggregation == 'weighted_sum':
            total_loss = paddle.stack(weighted_losses).sum()
        elif self.loss_aggregation == 'sum':
            total_loss = sum(per_head_losses.values())
        elif self.loss_aggregation == 'mean':
            total_loss = paddle.stack(list(per_head_losses.values())).mean()
        else:
            raise ValueError(f"Unknown aggregation: {self.loss_aggregation}")

        return total_loss, per_head_losses

    def get_task_weights(self) -> Dict[str, float]:
        """Get task weights for all heads"""
        return {name: cfg.task_weight for name, cfg in self.head_configs.items()}

    def set_task_weight(self, head_name: str, weight: float):
        """Update task weight for a specific head"""
        if head_name in self.head_configs:
            self.head_configs[head_name].task_weight = weight

    def get_loss_info(self) -> Dict[str, any]:
        """Get information about loss configuration"""
        return {
            "num_heads": len(self.head_configs),
            "loss_aggregation": self.loss_aggregation,
            "total_task_weight": self.total_task_weight,
            "heads": {
                name: {
                    "loss_type": cfg.loss_type,
                    "task_weight": cfg.task_weight,
                    "multi_label": cfg.multi_label,
                    "num_classes": cfg.num_classes
                }
                for name, cfg in self.head_configs.items()
            }
        }


# ============================================================================
# Factory Functions
# ============================================================================

def create_multi_task_loss_from_config(
    config_path: str = None,
    class_weights_path: str = None
) -> MultiTaskLoss:
    """Create MultiTaskLoss from configuration files

    Args:
        config_path: Path to model config YAML (uses default if None)
        class_weights_path: Path to class weights JSON

    Returns:
        Configured MultiTaskLoss instance
    """
    # Load class weights if provided
    class_weights = None
    if class_weights_path and os.path.exists(class_weights_path):
        with open(class_weights_path, 'r', encoding='utf-8') as f:
            weights_dict = json.load(f)

        # Organize by head
        class_weights = {}
        for key, value in weights_dict['weights'].items():
            parts = key.split('_')
            head_name = '_'.join(parts[:-1])
            if head_name not in class_weights:
                class_weights[head_name] = []
            class_weights[head_name].append(value)

        # Convert to tensors
        for head_name in class_weights:
            class_weights[head_name] = paddle.to_tensor(class_weights[head_name])

    # Default head configurations
    head_configs = [
        HeadLossConfig(
            head_name="tongue_color",
            num_classes=4,
            multi_label=False,
            task_weight=DEFAULT_TASK_WEIGHTS["tongue_color"],
            loss_type="focal",
            focal_alpha=0.25,
            focal_gamma=2.0,
            class_weights=class_weights.get("tongue_color") if class_weights else None
        ),
        HeadLossConfig(
            head_name="coating_color",
            num_classes=4,
            multi_label=False,
            task_weight=DEFAULT_TASK_WEIGHTS["coating_color"],
            loss_type="focal",
            focal_alpha=0.25,
            focal_gamma=2.0,
            class_weights=class_weights.get("coating_color") if class_weights else None
        ),
        HeadLossConfig(
            head_name="tongue_shape",
            num_classes=3,
            multi_label=False,
            task_weight=DEFAULT_TASK_WEIGHTS["tongue_shape"],
            loss_type="focal",
            focal_alpha=0.25,
            focal_gamma=2.0,
            class_weights=class_weights.get("tongue_shape") if class_weights else None
        ),
        HeadLossConfig(
            head_name="coating_quality",
            num_classes=3,
            multi_label=False,
            task_weight=DEFAULT_TASK_WEIGHTS["coating_quality"],
            loss_type="focal",
            focal_alpha=0.25,
            focal_gamma=2.0,
            class_weights=class_weights.get("coating_quality") if class_weights else None
        ),
        HeadLossConfig(
            head_name="features",
            num_classes=4,
            multi_label=True,
            task_weight=DEFAULT_TASK_WEIGHTS["features"],
            loss_type="asymmetric",
            asymmetric_gamma_pos=0.0,
            asymmetric_gamma_neg=4.0,
            asymmetric_clip=0.05
        ),
        HeadLossConfig(
            head_name="health",
            num_classes=2,
            multi_label=False,
            task_weight=DEFAULT_TASK_WEIGHTS["health"],
            loss_type="focal",
            focal_alpha=0.25,
            focal_gamma=2.0,
            class_weights=class_weights.get("health") if class_weights else None
        ),
    ]

    return MultiTaskLoss(
        head_configs=head_configs,
        loss_aggregation='weighted_sum',
        focal_alpha=0.25,
        focal_gamma=2.0,
        asymmetric_gamma_pos=0.0,
        asymmetric_gamma_neg=4.0,
        asymmetric_clip=0.05
    )


def load_class_weights_for_head(
    head_name: str,
    class_weights_path: str
) -> Optional[paddle.Tensor]:
    """Load class weights for a specific head

    Args:
        head_name: Name of the head (e.g., "tongue_color")
        class_weights_path: Path to class weights JSON

    Returns:
        Tensor of class weights or None
    """
    if not os.path.exists(class_weights_path):
        return None

    with open(class_weights_path, 'r', encoding='utf-8') as f:
        weights_dict = json.load(f)

    # Extract weights for this head
    weights = []
    for key, value in weights_dict['weights'].items():
        if key.startswith(head_name):
            weights.append(value)

    if weights:
        return paddle.to_tensor(weights)
    return None


# ============================================================================
# Test Functions
# ============================================================================

if __name__ == "__main__":
    print("Testing Multi-Task Loss Implementation...")

    # Create sample predictions and targets
    batch_size = 4

    predictions = {
        "tongue_color": paddle.randn([batch_size, 4]),
        "coating_color": paddle.randn([batch_size, 4]),
        "tongue_shape": paddle.randn([batch_size, 3]),
        "coating_quality": paddle.randn([batch_size, 3]),
        "features": paddle.randn([batch_size, 4]),
        "health": paddle.randn([batch_size, 2]),
    }

    targets = {
        "tongue_color": paddle.randint(0, 4, [batch_size]),
        "coating_color": paddle.randint(0, 4, [batch_size]),
        "tongue_shape": paddle.randint(0, 3, [batch_size]),
        "coating_quality": paddle.randint(0, 3, [batch_size]),
        "features": paddle.randint(0, 2, [batch_size, 4]).astype('float32'),
        "health": paddle.randint(0, 2, [batch_size]),
    }

    # Create multi-task loss
    multi_task_loss = create_multi_task_loss_from_config(
        class_weights_path="datasets/processed/clas_v1/class_weights.json"
    )

    # Print loss info
    info = multi_task_loss.get_loss_info()
    print("\n" + "=" * 60)
    print("Multi-Task Loss Configuration")
    print("=" * 60)
    print(f"Number of heads: {info['num_heads']}")
    print(f"Loss aggregation: {info['loss_aggregation']}")
    print(f"Total task weight: {info['total_task_weight']:.2f}")
    print("\nHead configurations:")
    for head_name, head_info in info['heads'].items():
        print(f"\n{head_name}:")
        print(f"  Loss type: {head_info['loss_type']}")
        print(f"  Task weight: {head_info['task_weight']:.2f}")
        print(f"  Multi-label: {head_info['multi_label']}")
        print(f"  Num classes: {head_info['num_classes']}")

    # Compute loss
    total_loss, per_head_losses = multi_task_loss(predictions, targets)

    print("\n" + "=" * 60)
    print("Loss Computation Results")
    print("=" * 60)
    print(f"Total loss: {total_loss.item():.4f}")
    print("\nPer-head losses:")
    for head_name, loss_value in per_head_losses.items():
        task_weight = multi_task_loss.head_configs[head_name].task_weight
        weighted = loss_value.item() * task_weight
        print(f"  {head_name}: {loss_value.item():.4f} (weight: {task_weight:.2f}, weighted: {weighted:.4f})")

    print("\n" + "=" * 60)
    print("Multi-Task Loss implementation test completed!")
    print("=" * 60)
