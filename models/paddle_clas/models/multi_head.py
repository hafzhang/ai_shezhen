#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi-Head Classification Module for Tongue Diagnosis

Implements multi-task learning with 6 diagnostic heads:
- Head 1: 舌色 (Tongue Color) - 4 classes
- Head 2: 苔色 (Coating Color) - 4 classes
- Head 3: 舌形 (Tongue Shape) - 3 classes
- Head 4: 苔质 (Coating Quality) - 3 classes
- Head 5: 特征 (Special Features) - 4 classes
- Head 6: 健康 (Health Status) - 2 classes

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass

# Configure UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ============================================================================
# Multi-Head Configuration
# ============================================================================

@dataclass
class HeadConfig:
    """Configuration for a single classification head"""
    name: str
    num_classes: int
    class_names: List[str]
    loss_weight: float = 1.0
    multi_label: bool = False
    description: str = ""


# Default head configurations for tongue diagnosis
DEFAULT_HEAD_CONFIGS = {
    "tongue_color": HeadConfig(
        name="tongue_color",
        num_classes=4,
        class_names=["淡红舌", "红舌", "绛紫舌", "淡白舌"],
        loss_weight=0.25,
        multi_label=False,
        description="舌体颜色分类"
    ),
    "coating_color": HeadConfig(
        name="coating_color",
        num_classes=4,
        class_names=["白苔", "黄苔", "黑苔", "花剥苔"],
        loss_weight=0.20,
        multi_label=False,
        description="舌苔颜色分类"
    ),
    "tongue_shape": HeadConfig(
        name="tongue_shape",
        num_classes=3,
        class_names=["正常", "胖大舌", "瘦薄舌"],
        loss_weight=0.15,
        multi_label=False,
        description="舌体形态分类"
    ),
    "coating_quality": HeadConfig(
        name="coating_quality",
        num_classes=3,
        class_names=["薄苔", "厚苔", "腐苔"],
        loss_weight=0.15,
        multi_label=False,
        description="舌苔质地分类"
    ),
    "features": HeadConfig(
        name="features",
        num_classes=4,
        class_names=["无", "红点", "裂纹", "齿痕"],
        loss_weight=0.15,
        multi_label=True,  # Can have multiple features
        description="舌体特殊特征（可多选）"
    ),
    "health": HeadConfig(
        name="health",
        num_classes=2,
        class_names=["不健康", "健康舌"],
        loss_weight=0.10,
        multi_label=False,
        description="整体健康状态评估"
    ),
}


# ============================================================================
# Classification Head Components
# ============================================================================

class ClassificationHead(nn.Layer):
    """Single classification head with configurable depth

    Args:
        in_features: Input feature dimension
        num_classes: Number of output classes
        hidden_dim: Hidden layer dimension (optional)
        dropout: Dropout probability
        use_sigmoid: Apply sigmoid activation (for multi-label)
    """

    def __init__(
        self,
        in_features: int,
        num_classes: int,
        hidden_dim: Optional[int] = None,
        dropout: float = 0.1,
        use_sigmoid: bool = False
    ):
        super().__init__()

        self.num_classes = num_classes
        self.use_sigmoid = use_sigmoid

        if hidden_dim is not None:
            self.layers = nn.Sequential(
                nn.Linear(in_features, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, num_classes)
            )
        else:
            self.layers = nn.Linear(in_features, num_classes)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize layer weights"""
        for layer in self.sublayers():
            if isinstance(layer, nn.Linear):
                # Xavier uniform initialization
                bound = (6 / (layer.weight.shape[0] + layer.weight.shape[1])) ** 0.5
                paddle.nn.initializer.Uniform(-bound, bound)(layer.weight)
                if layer.bias is not None:
                    paddle.nn.initializer.Constant(0.0)(layer.bias)

    def forward(self, x: paddle.Tensor) -> paddle.Tensor:
        """
        Forward pass

        Args:
            x: Input features (N, in_features)

        Returns:
            Logits (N, num_classes)
        """
        x = self.layers(x)

        if self.use_sigmoid:
            x = F.sigmoid(x)

        return x


class MultiHeadClassifier(nn.Layer):
    """Multi-head classifier for tongue diagnosis

    Manages multiple classification heads with different configurations.

    Args:
        feature_dim: Input feature dimension from backbone
        head_configs: Dictionary of head name -> HeadConfig
        dropout: Dropout probability for heads
        hidden_dim_ratio: Ratio of hidden dim to feature dim (if None, no hidden layer)
    """

    def __init__(
        self,
        feature_dim: int,
        head_configs: Dict[str, HeadConfig] = None,
        dropout: float = 0.2,
        hidden_dim_ratio: Optional[float] = None
    ):
        super().__init__()

        if head_configs is None:
            head_configs = DEFAULT_HEAD_CONFIGS

        self.feature_dim = feature_dim
        self.head_configs = head_configs

        # Build heads
        self.heads = nn.LayerDict()
        self.head_mapping = {}  # Maps index to head name

        idx = 0
        for head_name, config in head_configs.items():
            hidden_dim = None
            if hidden_dim_ratio is not None:
                hidden_dim = max(128, int(feature_dim * hidden_dim_ratio))

            head = ClassificationHead(
                in_features=feature_dim,
                num_classes=config.num_classes,
                hidden_dim=hidden_dim,
                dropout=dropout,
                use_sigmoid=config.multi_label
            )

            self.heads[head_name] = head
            self.head_mapping[idx] = head_name
            idx += 1

        # Calculate loss weights for each head
        self.register_buffer(
            'loss_weights',
            paddle.to_tensor([config.loss_weight for config in head_configs.values()])
        )

    def forward(
        self,
        features: paddle.Tensor,
        return_features: bool = False,
        head_names: Optional[List[str]] = None
    ) -> Union[List[paddle.Tensor], Tuple[List[paddle.Tensor], paddle.Tensor]]:
        """
        Forward pass through selected or all heads

        Args:
            features: Input features (N, feature_dim)
            return_features: If True, return features along with outputs
            head_names: List of head names to compute (None = all heads)

        Returns:
            List of output tensors, or (outputs, features) if return_features=True
        """
        if head_names is None:
            head_names = list(self.heads.keys())

        outputs = []
        for head_name in head_names:
            if head_name in self.heads:
                head_output = self.heads[head_name](features)
                outputs.append(head_output)

        if return_features:
            return outputs, features
        return outputs

    def get_head_config(self, head_name: str) -> HeadConfig:
        """Get configuration for a specific head"""
        return self.head_configs.get(head_name)

    def get_num_classes(self, head_name: str = None) -> Union[int, Dict[str, int]]:
        """Get number of classes for head(s)"""
        if head_name is not None:
            return self.head_configs[head_name].num_classes
        return {name: cfg.num_classes for name, cfg in self.head_configs.items()}

    def get_class_names(self, head_name: str = None) -> Union[List[str], Dict[str, List[str]]]:
        """Get class names for head(s)"""
        if head_name is not None:
            return self.head_configs[head_name].class_names
        return {name: cfg.class_names for name, cfg in self.head_configs.items()}


# ============================================================================
# Multi-Task Loss Functions
# ============================================================================

class MultiTaskLoss(nn.Layer):
    """Multi-task loss combining losses from all heads

    Args:
        head_configs: Head configurations for loss weights
        loss_type: Type of loss ("ce", "focal", "asymmetric", "combined")
        class_weights: Optional per-class weights for each head
    """

    def __init__(
        self,
        head_configs: Dict[str, HeadConfig] = None,
        loss_type: str = "ce",
        class_weights: Dict[str, paddle.Tensor] = None
    ):
        super().__init__()

        if head_configs is None:
            head_configs = DEFAULT_HEAD_CONFIGS

        self.head_configs = head_configs
        self.loss_type = loss_type
        self.class_weights = class_weights or {}

        # Build per-head loss weights
        self.register_buffer(
            'task_weights',
            paddle.to_tensor([cfg.loss_weight for cfg in head_configs.values()])
        )

    def forward(
        self,
        predictions: List[paddle.Tensor],
        targets: List[paddle.Tensor],
        head_names: List[str] = None
    ) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor]]:
        """
        Compute multi-task loss

        Args:
            predictions: List of prediction tensors from each head
            targets: List of target tensors for each head
            head_names: Names of heads (for ordering)

        Returns:
            Total loss and dictionary of per-head losses
        """
        if head_names is None:
            head_names = list(self.head_configs.keys())

        per_head_losses = {}
        total_loss = 0.0

        for i, (pred, target, head_name) in enumerate(zip(predictions, targets, head_names)):
            config = self.head_configs[head_name]
            task_weight = config.loss_weight

            # Compute loss for this head
            head_loss = self._compute_head_loss(pred, target, config, head_name)

            per_head_losses[head_name] = head_loss
            total_loss = total_loss + task_weight * head_loss

        return total_loss, per_head_losses

    def _compute_head_loss(
        self,
        pred: paddle.Tensor,
        target: paddle.Tensor,
        config: HeadConfig,
        head_name: str
    ) -> paddle.Tensor:
        """Compute loss for a single head"""
        # Get class weights for this head
        weight = self.class_weights.get(head_name, None)

        if config.multi_label:
            # Binary cross-entropy for multi-label
            loss = F.binary_cross_entropy_with_logits(
                pred, target.float(), weight=weight, reduction='mean'
            )
        else:
            # Cross-entropy for single-label
            if target.dtype != paddle.int64:
                target = target.astype('int64')

            loss = F.cross_entropy(
                pred, target, weight=weight, reduction='mean'
            )

        return loss


# ============================================================================
# Complete Multi-Head Classification Model
# ============================================================================

class MultiHeadTongueModel(nn.Layer):
    """Complete multi-head model for tongue diagnosis

    Combines backbone and multi-head classifier.

    Args:
        backbone: Feature extraction network (PP_HGNetV2_B4)
        head_configs: Configuration for each head
        dropout: Dropout probability
        feature_dim: Expected feature dimension from backbone
    """

    def __init__(
        self,
        backbone: nn.Layer,
        head_configs: Dict[str, HeadConfig] = None,
        dropout: float = 0.2,
        feature_dim: int = 864
    ):
        super().__init__()

        self.backbone = backbone
        self.feature_dim = feature_dim

        # Check actual feature dimension from backbone
        if hasattr(backbone, 'feature_dim'):
            self.feature_dim = backbone.feature_dim

        # Multi-head classifier
        self.classifier = MultiHeadClassifier(
            feature_dim=self.feature_dim,
            head_configs=head_configs,
            dropout=dropout,
            hidden_dim_ratio=None  # Direct connection
        )

        self.head_configs = self.classifier.head_configs

    def forward(
        self,
        x: paddle.Tensor,
        return_features: bool = False,
        head_names: Optional[List[str]] = None
    ) -> Union[List[paddle.Tensor], Tuple[List[paddle.Tensor], paddle.Tensor]]:
        """
        Forward pass

        Args:
            x: Input images (N, 3, H, W)
            return_features: If True, return backbone features
            head_names: Specific heads to compute

        Returns:
            List of predictions, or (predictions, features) if return_features=True
        """
        # Extract features
        features = self.backbone(x)

        # Classify with multi-head
        outputs = self.classifier(features, return_features=return_features, head_names=head_names)

        return outputs

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        total_params = sum(p.numel().item() for p in self.parameters())
        backbone_params = sum(p.numel().item() for p in self.backbone.parameters())
        head_params = sum(p.numel().item() for p in self.classifier.parameters())

        head_info = {}
        for name, config in self.head_configs.items():
            head_info[name] = {
                "num_classes": config.num_classes,
                "class_names": config.class_names,
                "loss_weight": config.loss_weight,
                "multi_label": config.multi_label,
                "description": config.description
            }

        return {
            "total_parameters": total_params,
            "backbone_parameters": backbone_params,
            "head_parameters": head_params,
            "feature_dimension": self.feature_dim,
            "num_heads": len(self.head_configs),
            "heads": head_info
        }


# ============================================================================
# Model Factory Functions
# ============================================================================

def create_multi_head_model(
    backbone: nn.Layer = None,
    pretrained_backbone: str = None,
    head_configs: Dict[str, HeadConfig] = None,
    dropout: float = 0.2
) -> MultiHeadTongueModel:
    """Create a complete multi-head model

    Args:
        backbone: Backbone network (if None, creates PP_HGNetV2_B4)
        pretrained_backbone: Path to pretrained backbone weights
        head_configs: Configuration for each head
        dropout: Dropout probability

    Returns:
        MultiHeadTongueModel instance
    """
    if backbone is None:
        # Import here to avoid circular imports
        from models.paddle_clas.models.pphgnetv2 import PP_HGNetV2_B4
        backbone = PP_HGNetV2_B4(num_classes=1000, pretrained_path=pretrained_backbone)

    model = MultiHeadTongueModel(
        backbone=backbone,
        head_configs=head_configs,
        dropout=dropout
    )

    return model


def create_loss_fn(
    head_configs: Dict[str, HeadConfig] = None,
    loss_type: str = "ce",
    class_weights: Dict[str, paddle.Tensor] = None
) -> MultiTaskLoss:
    """Create multi-task loss function

    Args:
        head_configs: Configuration for each head
        loss_type: Type of loss
        class_weights: Per-class weights for each head

    Returns:
        MultiTaskLoss instance
    """
    return MultiTaskLoss(
        head_configs=head_configs,
        loss_type=loss_type,
        class_weights=class_weights
    )


# ============================================================================
# Utility Functions
# ============================================================================

def print_model_summary(model: MultiHeadTongueModel):
    """Print model summary"""
    info = model.get_model_info()

    print("=" * 60)
    print("Multi-Head Tongue Classification Model Summary")
    print("=" * 60)
    print(f"Total Parameters: {info['total_parameters']:,}")
    print(f"Backbone Parameters: {info['backbone_parameters']:,}")
    print(f"Head Parameters: {info['head_parameters']:,}")
    print(f"Feature Dimension: {info['feature_dimension']}")
    print(f"Number of Heads: {info['num_heads']}")
    print()

    print("Head Configurations:")
    print("-" * 60)
    for name, head_info in info['heads'].items():
        print(f"\n{name}:")
        print(f"  Classes: {head_info['num_classes']}")
        print(f"  Names: {', '.join(head_info['class_names'])}")
        print(f"  Loss Weight: {head_info['loss_weight']}")
        print(f"  Multi-label: {head_info['multi_label']}")
        print(f"  Description: {head_info['description']}")
    print("=" * 60)


if __name__ == "__main__":
    # Test the model
    print("Testing Multi-Head Classification Model...")

    # Create a simple backbone for testing
    class DummyBackbone(nn.Layer):
        def __init__(self):
            super().__init__()
            self.feature_dim = 864
            self.conv = nn.Sequential(
                nn.Conv2D(3, 64, 7, stride=2, padding=3),
                nn.ReLU(),
                nn.AdaptiveAvgPool2D((1, 1))
            )

        def forward(self, x):
            x = self.conv(x)
            return paddle.flatten(x, 1)

    # Create model
    backbone = DummyBackbone()
    model = create_multi_head_model(backbone=backbone)

    # Print summary
    print_model_summary(model)

    # Test forward pass
    x = paddle.randn([2, 3, 224, 224])
    outputs = model(x)

    print("\nForward Pass Test:")
    print(f"Input shape: {x.shape}")
    for i, output in enumerate(outputs):
        print(f"  Head {i} output: {output.shape}")
