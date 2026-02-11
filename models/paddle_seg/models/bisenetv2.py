#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BiSeNetV2: Bilateral Segmentation Network for Real-time Semantic Segmentation

Simplified implementation for tongue segmentation.

Reference:
    - "BiSeNet V2: Bilateral Segmentation Network for Real-time Semantic Segmentation"
      https://arxiv.org/abs/2004.02193
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import paddle
import paddle.nn as nn
import paddle.nn.functional as F
import logging

logger = logging.getLogger(__name__)


# ============================================================
# STDC Building Blocks (Simplified)
# ============================================================

class STDCBlock(nn.Layer):
    """
    Simplified STDC Block for multi-scale feature extraction.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        stride: int = 1,
        downsample: bool = False
    ):
        super().__init__()
        self.downsample = downsample
        self.stride = stride

        # Main convolutions with different dilation rates
        self.conv1 = nn.Sequential(
            nn.Conv2D(in_channels, out_channels // 2, kernel_size=1, stride=1, padding=0),
            nn.BatchNorm2D(out_channels // 2),
            nn.ReLU()
        )

        # For stride=2, we downsample in conv2
        self.conv2 = nn.Sequential(
            nn.Conv2D(out_channels // 2, out_channels // 2, kernel_size=3, stride=stride, padding=1),
            nn.BatchNorm2D(out_channels // 2),
            nn.ReLU()
        )

        self.conv3 = nn.Sequential(
            nn.Conv2D(out_channels // 2, out_channels // 2, kernel_size=3, stride=1, padding=2, dilation=2),
            nn.BatchNorm2D(out_channels // 2),
            nn.ReLU()
        )

        self.conv4 = nn.Sequential(
            nn.Conv2D(out_channels // 2, out_channels // 2, kernel_size=3, stride=1, padding=3, dilation=3),
            nn.BatchNorm2D(out_channels // 2),
            nn.ReLU()
        )

        # Fusion conv - adjusts based on concat channels
        # When downsample=False: concat x1, x2, x3, x4 = 4 * (out//2) = 2*out
        # When downsample=True: concat x1_up, x2, x3 = 3 * (out//2) = 1.5*out
        fusion_in_channels = (3 if downsample else 4) * (out_channels // 2)
        self.fusion = nn.Sequential(
            nn.Conv2D(fusion_in_channels, out_channels, kernel_size=1, stride=1, padding=0),
            nn.BatchNorm2D(out_channels),
            nn.ReLU()
        )

        # Downsample for residual
        if downsample:
            self.downsample_conv = nn.Sequential(
                nn.Conv2D(in_channels, out_channels, kernel_size=3, stride=stride, padding=1),
                nn.BatchNorm2D(out_channels)
            )
        else:
            self.downsample_conv = None

    def forward(self, x):
        identity = x

        x1 = self.conv1(x)

        if self.downsample:
            # conv2 does stride=2, so x2 is half the spatial size of x1
            x2 = self.conv2(x1)
            # x1 and x2 have different spatial sizes now
            # Don't use x1 in concat - use x2 and x3 only
            # But we need 3 inputs, so we skip conv4
            x3 = self.conv3(x2)
            # concat x2 + x3: each is out//2 channels, so concat = out
            # Add x1 upsampled to match x2's size
            x1_up = F.interpolate(x1, scale_factor=0.5, mode='bilinear')
            concat_features = paddle.concat([x1_up, x2, x3], axis=1)
        else:
            x2 = self.conv2(x1)
            x3 = self.conv3(x2)
            x4 = self.conv4(x3)
            concat_features = paddle.concat([x1, x2, x3, x4], axis=1)

        # Fusion
        out = self.fusion(concat_features)

        # Residual
        if self.downsample_conv is not None:
            identity = self.downsample_conv(identity)

        out = out + identity

        return out


# ============================================================
# Attention Modules
# ============================================================

class AttentionRefinementModule(nn.Layer):
    """Attention Refinement Module."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()

        self.conv = nn.Sequential(
            nn.Conv2D(in_channels, out_channels, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2D(out_channels),
            nn.ReLU()
        )

        self.attention = nn.Sequential(
            nn.AdaptiveAvgPool2D(1),
            nn.Conv2D(out_channels, out_channels, kernel_size=1, stride=1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.conv(x)
        attention = self.attention(x)
        return x * attention


# ============================================================
# Context Path
# ============================================================

class ContextPath(nn.Layer):
    """Context Path for semantic features."""

    def __init__(self, in_channels=3, out_channels=128):
        super().__init__()

        # Initial stem
        self.stem = nn.Sequential(
            nn.Conv2D(in_channels, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2D(32),
            nn.ReLU(),
            nn.Conv2D(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU(),
        )

        # STDC blocks with increasing channels
        self.stage1 = nn.Sequential(
            STDCBlock(64, 64, stride=1, downsample=False),
        )

        self.stage2 = nn.Sequential(
            STDCBlock(64, 128, stride=2, downsample=True),
            STDCBlock(128, 128, stride=1, downsample=False),
        )

        self.stage3 = nn.Sequential(
            STDCBlock(128, 256, stride=2, downsample=True),
            STDCBlock(256, 256, stride=1, downsample=False),
            STDCBlock(256, 256, stride=1, downsample=False),
        )

        self.stage4 = nn.Sequential(
            STDCBlock(256, 512, stride=2, downsample=True),
            STDCBlock(512, 512, stride=1, downsample=False),
            STDCBlock(512, 512, stride=1, downsample=False),
        )

        # ARM
        self.arm16 = AttentionRefinementModule(256, 128)
        self.arm32 = AttentionRefinementModule(512, 128)

        # Global pooling
        self.global_pool = nn.Sequential(
            nn.AdaptiveAvgPool2D(1),
            nn.Conv2D(512, 128, kernel_size=1, stride=1)
        )

    def forward(self, x):
        # Stem (1/4 resolution after 2 stride-2 convs)
        x = self.stem(x)

        # Stage 1 (1/4)
        feat4 = self.stage1(x)

        # Stage 2 (1/8)
        feat8 = self.stage2(feat4)

        # Stage 3 (1/16)
        feat16 = self.stage3(feat8)

        # Stage 4 (1/32)
        feat32 = self.stage4(feat16)

        # Apply ARM
        feat16_arm = self.arm16(feat16)
        feat32_arm = self.arm32(feat32)

        # Add global context to feat32
        global_feat = self.global_pool(feat32)
        global_feat = F.interpolate(global_feat, size=feat32_arm.shape[-2:], mode='bilinear')
        feat32_arm = feat32_arm + global_feat

        # Upsample for fusion
        feat16_up = F.interpolate(feat32_arm, size=feat16_arm.shape[-2:], mode='bilinear')
        feat16_out = feat16_arm + feat16_up

        feat8_up = F.interpolate(feat16_out, size=feat8.shape[-2:], mode='bilinear')

        return feat8_up, feat16_out, feat32_arm


# ============================================================
# Detail Path
# ============================================================

class DetailPath(nn.Layer):
    """Detail Path for fine spatial details."""

    def __init__(self, in_channels=3):
        super().__init__()

        self.conv1 = nn.Sequential(
            nn.Conv2D(in_channels, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2D(32),
            nn.ReLU()
        )

        self.conv2 = nn.Sequential(
            nn.Conv2D(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU()
        )

        self.conv3 = nn.Sequential(
            nn.Conv2D(64, 128, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU()
        )

    def forward(self, x):
        conv1 = self.conv1(x)
        conv2 = self.conv2(conv1)
        conv3 = self.conv3(conv2)

        return conv1, conv2, conv3


# ============================================================
# BiSeNetV2 Model
# ============================================================

class BiSeNetV2(nn.Layer):
    """
    BiSeNetV2: Fast and Accurate Semantic Segmentation.

    Args:
        num_classes: Number of output classes
        in_channels: Number of input channels (default: 3 for RGB)
        attention: Whether to use attention modules
        pretrained_path: Path to pretrained weights
    """

    def __init__(
        self,
        num_classes: int = 2,
        in_channels: int = 3,
        attention: bool = True,
        pretrained_path: str = None
    ):
        super().__init__()

        self.num_classes = num_classes
        self.in_channels = in_channels
        self.attention = attention

        # Context Path
        self.context_path = ContextPath(in_channels=in_channels)

        # Detail Path
        self.detail_path = DetailPath(in_channels=in_channels)

        # Bilateral Fusion
        # At 1/16 resolution: detail (128) + context (128) = 256 -> 128
        self.bf_head16 = nn.Sequential(
            nn.Conv2D(128 + 128, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU()
        )

        # At 1/8 resolution: detail (64) + context (128) = 192 -> 128
        self.bf_head8 = nn.Sequential(
            nn.Conv2D(64 + 128, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU()
        )

        # Segmentation Heads
        self.seg_head8 = nn.Conv2D(128, num_classes, kernel_size=3, stride=1, padding=1)
        self.seg_head16 = nn.Conv2D(128, num_classes, kernel_size=3, stride=1, padding=1)
        self.seg_head32 = nn.Conv2D(128, num_classes, kernel_size=3, stride=1, padding=1)

        logger.info(f"BiSeNetV2 initialized: num_classes={num_classes}, "
                   f"in_channels={in_channels}, attention={attention}")

    def forward(self, x):
        input_size = x.shape[-2:]

        # Context Path returns: (feat8 @ 1/8, feat16 @ 1/16, feat32 @ 1/32)
        feat8_ctx, feat16_ctx, feat32_ctx = self.context_path(x)

        # Detail Path returns: (conv1 @ 1/4, conv2 @ 1/8, conv3 @ 1/16)
        # conv1: 32-ch, conv2: 64-ch, conv3: 128-ch
        conv1_det, conv2_det, conv3_det = self.detail_path(x)

        # feat8_det needs to be at 1/8: use conv2 (64-ch @ 1/8)
        feat8_det = conv2_det

        # feat16_det needs to be at 1/16: use conv3 (128-ch @ 1/16)
        feat16_det = conv3_det

        # Bilateral Fusion
        feat16_fused = self.bf_head16(paddle.concat([feat16_det, feat16_ctx], axis=1))
        feat8_fused = self.bf_head8(paddle.concat([feat8_det, feat8_ctx], axis=1))

        # Upsample to input resolution
        feat8_up = F.interpolate(feat8_fused, size=input_size, mode='bilinear')
        feat16_up = F.interpolate(feat16_fused, size=input_size, mode='bilinear')
        feat32_up = F.interpolate(feat32_ctx, size=input_size, mode='bilinear')

        # Segmentation heads
        output8 = self.seg_head8(feat8_up)
        output16 = self.seg_head16(feat16_up)
        output32 = self.seg_head32(feat32_up)

        # Combine outputs
        output = output8 + output16 + output32

        return output

    def get_aux_outputs(self, x):
        """Get auxiliary outputs for training."""
        input_size = x.shape[-2:]

        # Context Path returns: (feat8 @ 1/8, feat16 @ 1/16, feat32 @ 1/32)
        feat8_ctx, feat16_ctx, feat32_ctx = self.context_path(x)

        # Detail Path returns: (conv1 @ 1/4, conv2 @ 1/8, conv3 @ 1/16)
        conv1_det, conv2_det, conv3_det = self.detail_path(x)

        # feat8_det: conv2 (64-ch @ 1/8)
        # feat16_det: conv3 (128-ch @ 1/16)
        feat8_det = conv2_det
        feat16_det = conv3_det

        # Bilateral Fusion
        feat16_fused = self.bf_head16(paddle.concat([feat16_det, feat16_ctx], axis=1))
        feat8_fused = self.bf_head8(paddle.concat([feat8_det, feat8_ctx], axis=1))

        # Aux heads at lower resolution
        aux16 = self.seg_head16(feat16_fused)
        aux32 = self.seg_head32(feat32_ctx)

        # Main output at full resolution
        feat8_up = F.interpolate(feat8_fused, size=input_size, mode='bilinear')
        feat16_up = F.interpolate(feat16_fused, size=input_size, mode='bilinear')
        feat32_up = F.interpolate(feat32_ctx, size=input_size, mode='bilinear')

        output8 = self.seg_head8(feat8_up)
        output16 = self.seg_head16(feat16_up)
        output32 = self.seg_head32(feat32_up)

        output = output8 + output16 + output32

        # Upsample aux outputs
        aux16_up = F.interpolate(aux16, size=input_size, mode='bilinear')
        aux32_up = F.interpolate(aux32, size=input_size, mode='bilinear')

        return output, aux16_up, aux32_up


# Test model
if __name__ == "__main__":
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 60)
    logger.info("Testing BiSeNetV2 Model")
    logger.info("=" * 60)

    model = BiSeNetV2(num_classes=2, in_channels=3, attention=True)

    batch_size = 2
    input_tensor = paddle.randn([batch_size, 3, 512, 512])

    logger.info(f"Input shape: {input_tensor.shape}")

    output = model(input_tensor)

    logger.info(f"Output shape: {output.shape}")

    total_params = sum(p.numel().item() for p in model.parameters())
    logger.info(f"Total parameters: {total_params:,}")

    logger.info("\n" + "=" * 60)
    logger.info("BiSeNetV2 test completed successfully!")
    logger.info("=" * 60)
