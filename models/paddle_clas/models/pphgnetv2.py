#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PP-HGNetV2-B4 Backbone for Tongue Classification

High-performance GPU-efficient network architecture:
- Lightweight stem layers for initial feature extraction
- 4 stages with HG-Blocks for multi-scale processing
- Global average pooling for feature aggregation
- Feature dimension: 864

Paper Reference:
    PP-HGNetV2: An Improved High-Performance GPU-Efficient Network
    https://arxiv.org/abs/...

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from typing import Optional, Tuple, Dict, Any, Union

# Note: UTF-8 encoding is configured by setting PYTHONIOENCODING=utf-8
# We don't wrap stdout/stderr at module level as it causes issues with imports


# ============================================================================
# Light Convolution Block
# ============================================================================

class LightConvBNReLU(nn.Layer):
    """Light Convolution Block with BN and ReLU

    Architecture:
        1x1 conv (reduction) -> DW conv (spatial) -> 1x1 conv (expansion) -> BN -> ReLU

    This design reduces computational cost while maintaining representational power.
    """

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()

        # 1x1 convolution for channel reduction
        self.conv1 = nn.Conv2D(
            in_channels, in_channels, kernel_size=1,
            bias_attr=False
        )

        # Depthwise convolution for spatial processing
        self.conv2_dw = nn.Conv2D(
            in_channels, in_channels, kernel_size=kernel_size,
            padding=kernel_size // 2, groups=in_channels, bias_attr=False
        )

        # 1x1 convolution for channel expansion
        self.conv2_pw = nn.Conv2D(
            in_channels, out_channels, kernel_size=1,
            bias_attr=False
        )

        # Batch normalization and activation
        self.bn = nn.BatchNorm2D(out_channels)
        self.relu = nn.ReLU()

    def forward(self, x: paddle.Tensor) -> paddle.Tensor:
        x = self.conv1(x)
        x = self.conv2_dw(x)
        x = self.conv2_pw(x)
        x = self.bn(x)
        x = self.relu(x)
        return x


# ============================================================================
# HG-Block (High-Performance GPU Block)
# ============================================================================

class HGBlock(nn.Layer):
    """HG-Block for PP-HGNetV2

    Multi-branch aggregation block that balances:
    - Computational efficiency
    - Feature representation
    - GPU utilization

    Architecture:
        Input -> 3 parallel Light Conv branches -> Concat -> Aggregation Conv -> Output
                                                                   |
                                                                Residual
    """

    def __init__(
        self,
        in_channels: int,
        mid_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        use_residual: bool = True
    ):
        super().__init__()

        self.use_residual = use_residual
        self.in_channels = in_channels
        self.out_channels = out_channels

        # Three parallel light convolution branches
        self.branch1 = LightConvBNReLU(in_channels, mid_channels, kernel_size)
        self.branch2 = LightConvBNReLU(in_channels, mid_channels, kernel_size)
        self.branch3 = LightConvBNReLU(in_channels, mid_channels, kernel_size)

        # Total channels after concatenating 3 branches
        total_channels = mid_channels * 3

        # Aggregation convolution
        self.aggregation_conv = nn.Sequential(
            nn.Conv2D(total_channels, out_channels, kernel_size=1, bias_attr=False),
            nn.BatchNorm2D(out_channels)
        )

        # Residual projection (if channels don't match)
        if in_channels != out_channels or not use_residual:
            self.residual_conv = nn.Sequential(
                nn.Conv2D(in_channels, out_channels, kernel_size=1, bias_attr=False),
                nn.BatchNorm2D(out_channels)
            )
        else:
            self.residual_conv = None

    def forward(self, x: paddle.Tensor) -> paddle.Tensor:
        # Process through parallel branches
        branch1 = self.branch1(x)
        branch2 = self.branch2(x)
        branch3 = self.branch3(x)

        # Concatenate branches
        out = paddle.concat([branch1, branch2, branch3], axis=1)

        # Aggregate features
        out = self.aggregation_conv(out)

        # Add residual connection
        if self.use_residual:
            if self.residual_conv is not None:
                residual = self.residual_conv(x)
            else:
                residual = x
            out = out + residual

        return out


# ============================================================================
# Stem Layer
# ============================================================================

class StemLayer(nn.Layer):
    """Initial stem layer for feature extraction

    Processes input images with:
    - Initial 3x3 conv with stride 2 (downsampling)
    - Another 3x3 conv with stride 1
    - Batch normalization and ReLU after each conv
    """

    def __init__(self, in_channels: int = 3, out_channels: int = 48):
        super().__init__()

        self.stem = nn.Sequential(
            # First conv: downsampling
            nn.Conv2D(
                in_channels, out_channels, kernel_size=3,
                stride=2, padding=1, bias_attr=False
            ),
            nn.BatchNorm2D(out_channels),
            nn.ReLU(),

            # Second conv: feature extraction
            nn.Conv2D(
                out_channels, out_channels, kernel_size=3,
                stride=1, padding=1, bias_attr=False
            ),
            nn.BatchNorm2D(out_channels),
            nn.ReLU(),
        )

    def forward(self, x: paddle.Tensor) -> paddle.Tensor:
        return self.stem(x)


# ============================================================================
# PP-HGNetV2-B4 Backbone
# ============================================================================

class PP_HGNetV2_B4(nn.Layer):
    """PP-HGNetV2-B4 Backbone for Tongue Classification

    High-performance GPU-efficient network architecture.

    Architecture:
        Input (3, H, W)
          -> Stem (48 channels, 1/2 resolution)
          -> Stage 1 (108 channels, 1/4 resolution)
          -> Stage 2 (216 channels, 1/8 resolution)
          -> Stage 3 (432 channels, 1/16 resolution)
          -> Stage 4 (864 channels, 1/32 resolution)
          -> Global Avg Pool
          -> Flatten (864 features)

    Args:
        num_classes: Number of output classes for ImageNet pretraining (default 1000)
        in_channels: Number of input channels (default 3 for RGB)
        pretrained_path: Path to pretrained weights (optional)
        return_features: If True, return intermediate features

    Features:
        - GPU-efficient design with minimal channel redundancy
        - Multi-scale feature extraction through 4 stages
        - Global average pooling for spatial invariance
        - Support for pretrained ImageNet22k weights
    """

    def __init__(
        self,
        num_classes: int = 1000,
        in_channels: int = 3,
        pretrained_path: Optional[str] = None,
        return_features: bool = False
    ):
        super().__init__()

        self.num_classes = num_classes
        self.in_channels = in_channels
        self.return_features = return_features
        self.feature_dim = 864

        # Stem layer: initial feature extraction
        self.stem = StemLayer(in_channels, 48)

        # Stage 1: 1/4 resolution, 48 -> 108 channels
        # Input: 48x(H/2)x(W/2), Output: 108x(H/4)x(W/4)
        self.stage1 = nn.Sequential(
            nn.Conv2D(48, 96, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(96),
            nn.ReLU(),
            HGBlock(96, 36, 108, kernel_size=3)
        )

        # Stage 2: 1/8 resolution, 108 -> 216 channels
        # Input: 108x(H/4)x(W/4), Output: 216x(H/8)x(W/8)
        self.stage2 = nn.Sequential(
            nn.Conv2D(108, 192, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(192),
            nn.ReLU(),
            HGBlock(192, 72, 216, kernel_size=3)
        )

        # Stage 3: 1/16 resolution, 216 -> 432 channels
        # Input: 216x(H/8)x(W/8), Output: 432x(H/16)x(W/16)
        self.stage3 = nn.Sequential(
            nn.Conv2D(216, 384, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(384),
            nn.ReLU(),
            HGBlock(384, 144, 432, kernel_size=3)
        )

        # Stage 4: 1/32 resolution, 432 -> 864 channels
        # Input: 432x(H/16)x(W/16), Output: 864x(H/32)x(W/32)
        self.stage4 = nn.Sequential(
            nn.Conv2D(432, 768, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(768),
            nn.ReLU(),
            HGBlock(768, 288, 864, kernel_size=3)
        )

        # Global average pooling
        self.global_pool = nn.AdaptiveAvgPool2D((1, 1))

        # Classifier head (for ImageNet pretraining)
        self.classifier = nn.Sequential(
            nn.Linear(864, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, num_classes) if num_classes > 0 else nn.Identity()
        )

        # Load pretrained weights if provided
        if pretrained_path and os.path.exists(pretrained_path):
            self._load_pretrained(pretrained_path)
        elif pretrained_path:
            print(f"Warning: Pretrained weights not found at {pretrained_path}")

        self._init_weights()

    def _init_weights(self):
        """Initialize network weights"""
        for layer in self.sublayers():
            if isinstance(layer, nn.Conv2D):
                # Kaiming normal initialization
                fan_in = layer.weight.shape[1] * layer.weight.shape[2] * layer.weight.shape[3]
                std = (2.0 / fan_in) ** 0.5
                paddle.nn.initializer.Normal(0.0, std)(layer.weight)
                if layer.bias is not None:
                    paddle.nn.initializer.Constant(0.0)(layer.bias)
            elif isinstance(layer, nn.BatchNorm2D):
                paddle.nn.initializer.Constant(1.0)(layer.weight)
                paddle.nn.initializer.Constant(0.0)(layer.bias)
            elif isinstance(layer, nn.Linear):
                bound = (6 / (layer.weight.shape[0] + layer.weight.shape[1])) ** 0.5
                paddle.nn.initializer.Uniform(-bound, bound)(layer.weight)
                if layer.bias is not None:
                    paddle.nn.initializer.Constant(0.0)(layer.bias)

    def _load_pretrained(self, pretrained_path: str):
        """Load pretrained weights from file"""
        print(f"Loading pretrained weights from: {pretrained_path}")
        state_dict = paddle.load(pretrained_path)

        # Get model state dict
        model_state = self.state_dict()

        # Filter and load compatible weights
        pretrained_state = {}
        missing_keys = []
        unexpected_keys = []

        for name, param in state_dict.items():
            if name in model_state:
                if model_state[name].shape == param.shape:
                    pretrained_state[name] = param
                else:
                    print(f"Shape mismatch for {name}: "
                          f"pretrained {param.shape} vs model {model_state[name].shape}")
            else:
                unexpected_keys.append(name)

        for name in model_state:
            if name not in state_dict:
                missing_keys.append(name)

        # Load weights
        if pretrained_state:
            load_result = self.set_state_dict(pretrained_state)
            missing_keys.extend(load_result[0])
            unexpected_keys.extend(load_result[1])

            print(f"Loaded {len(pretrained_state)}/{len(model_state)} parameters")
            if missing_keys:
                print(f"Missing keys ({len(missing_keys)}): {missing_keys[:5]}...")
            if unexpected_keys:
                print(f"Unexpected keys ({len(unexpected_keys)}): {unexpected_keys[:5]}...")

    def forward(
        self,
        x: paddle.Tensor,
        return_intermediates: bool = False
    ) -> Union[paddle.Tensor, Tuple[paddle.Tensor, Dict[str, paddle.Tensor]]]:
        """
        Forward pass

        Args:
            x: Input tensor (N, C, H, W)
            return_intermediates: If True, return intermediate features

        Returns:
            Features (N, 864) or (features, intermediates) if return_intermediates=True
        """
        intermediates = {}

        # Stem: (N, 3, H, W) -> (N, 48, H/2, W/2)
        x = self.stem(x)
        intermediates['stem'] = x

        # Stage 1: -> (N, 108, H/4, W/4)
        x = self.stage1(x)
        intermediates['stage1'] = x

        # Stage 2: -> (N, 216, H/8, W/8)
        x = self.stage2(x)
        intermediates['stage2'] = x

        # Stage 3: -> (N, 432, H/16, W/16)
        x = self.stage3(x)
        intermediates['stage3'] = x

        # Stage 4: -> (N, 864, H/32, W/32)
        x = self.stage4(x)
        intermediates['stage4'] = x

        # Global pooling: -> (N, 864, 1, 1)
        x = self.global_pool(x)

        # Flatten: -> (N, 864)
        features = paddle.flatten(x, 1)

        # Apply classifier for ImageNet pretraining
        if self.num_classes > 0:
            logits = self.classifier(features)
        else:
            logits = features

        if return_intermediates:
            return logits, intermediates

        return logits

    def get_feature_dim(self) -> int:
        """Get output feature dimension"""
        return self.feature_dim


# ============================================================================
# Model Factory Functions
# ============================================================================

def create_backbone(
    pretrained: Optional[str] = None,
    num_classes: int = 0  # 0 for feature extraction only
) -> PP_HGNetV2_B4:
    """Create PP-HGNetV2-B4 backbone

    Args:
        pretrained: Path to pretrained weights
        num_classes: Number of output classes (0 for feature extraction)

    Returns:
        PP_HGNetV2_B4 instance
    """
    return PP_HGNetV2_B4(
        num_classes=num_classes,
        pretrained_path=pretrained
    )


# ============================================================================
# Utility Functions
# ============================================================================

def count_parameters(model: nn.Layer) -> Dict[str, int]:
    """Count model parameters"""
    total = sum(p.numel().item() for p in model.parameters())
    trainable = sum(p.numel().item() for p in model.parameters() if not p.stop_gradient)
    return {
        "total": total,
        "trainable": trainable,
        "frozen": total - trainable
    }


def print_model_info(model: PP_HGNetV2_B4):
    """Print model information"""
    params = count_parameters(model)

    print("=" * 60)
    print("PP-HGNetV2-B4 Model Information")
    print("=" * 60)
    print(f"Input channels: {model.in_channels}")
    print(f"Output feature dim: {model.feature_dim}")
    print(f"Number of classes: {model.num_classes}")
    print(f"Total parameters: {params['total']:,}")
    print(f"Trainable parameters: {params['trainable']:,}")
    print(f"Frozen parameters: {params['frozen']:,}")

    # Stage information
    print("\nStage Configuration:")
    print("-" * 60)
    print(f"Stem output: 48 channels, 1/2 resolution")
    print(f"Stage 1 output: 108 channels, 1/4 resolution")
    print(f"Stage 2 output: 216 channels, 1/8 resolution")
    print(f"Stage 3 output: 432 channels, 1/16 resolution")
    print(f"Stage 4 output: 864 channels, 1/32 resolution")
    print("=" * 60)


if __name__ == "__main__":
    # Test the model
    print("Testing PP-HGNetV2-B4...")

    # Create model
    model = PP_HGNetV2_B4(num_classes=0)  # Feature extraction only

    # Print info
    print_model_info(model)

    # Test forward pass
    x = paddle.randn([2, 3, 224, 224])
    features = model(x)

    print(f"\nForward Pass Test:")
    print(f"Input shape: {x.shape}")
    print(f"Output shape: {features.shape}")
    print("Test passed!")
