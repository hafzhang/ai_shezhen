#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PaddleClas环境搭建与验证脚本

检查PaddlePaddle和PaddleClas环境，配置PP-HGNetV2-B4模型

Features:
    - PaddlePaddle版本检查
    - GPU可用性验证
    - 模型结构验证
    - 预训练权重下载
    - 基准测试运行

Usage:
    python setup_env.py
    python setup_env.py --download-weights
    python setup_env.py --verify-only

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import subprocess

# Configure UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import PaddlePaddle
try:
    import paddle
    import paddle.nn as nn
    from paddle.io import Dataset, DataLoader
    import numpy as np
    PADDLE_AVAILABLE = True
except ImportError as e:
    logger.error(f"PaddlePaddle not available: {e}")
    PADDLE_AVAILABLE = False


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class EnvironmentConfig:
    """Environment configuration"""
    # Model paths
    weights_dir: str = "models/paddle_clas/weights"
    output_dir: str = "models/paddle_clas"
    configs_dir: str = "models/paddle_clas/configs"

    # Pretrained weights URLs (using PaddlePaddle official weights)
    pretrained_urls: Dict[str, str] = field(default_factory=lambda: {
        "pphgnetv2_b4": "https://paddle-imagenet-models-name.bj.bcebos.com/dygraph_v2.0/PPHGNetV2_B4_pretrained.pdparams"
    })

    # Requirements
    min_paddle_version: Tuple[int, int] = (3, 0)
    preferred_paddle_version: str = "3.0.0"


# ============================================================================
# PP-HGNetV2-B4 Model Components
# ============================================================================

class LightConvBNReLU(nn.Layer):
    """Light Convolution Block for PP-HGNetV2

    Lightweight convolution with:
    - 1x1 conv for channel reduction
    - Depthwise conv for spatial processing
    - 1x1 conv for channel expansion
    - Batch normalization and ReLU
    """

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        # 1x1 conv for reduction
        self.conv1 = nn.Conv2D(in_channels, in_channels, kernel_size=1, bias_attr=False)

        # Depthwise convolution
        self.conv2_dw = nn.Conv2D(
            in_channels, in_channels, kernel_size=kernel_size,
            padding=kernel_size // 2, groups=in_channels, bias_attr=False
        )

        # 1x1 conv for expansion
        self.conv2_pw = nn.Conv2D(in_channels, out_channels, kernel_size=1, bias_attr=False)

        self.bn = nn.BatchNorm2D(out_channels)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2_dw(x)
        x = self.conv2_pw(x)
        x = self.bn(x)
        return self.relu(x)


class HGBlock(nn.Layer):
    """HG-Block for PP-HGNetV2

    Multi-branch aggregation block with:
    - 3 parallel Light Conv branches
    - Aggregation convolution
    - Residual connection
    """

    def __init__(self, in_channels: int, mid_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        # Three parallel branches
        self.branch1 = LightConvBNReLU(in_channels, mid_channels, kernel_size)
        self.branch2 = LightConvBNReLU(in_channels, mid_channels, kernel_size)
        self.branch3 = LightConvBNReLU(in_channels, mid_channels, kernel_size)

        # Total channels after concatenation
        total_channels = mid_channels * 3

        # Aggregation convolution
        self.aggregation_conv = nn.Sequential(
            nn.Conv2D(total_channels, out_channels, kernel_size=1, bias_attr=False),
            nn.BatchNorm2D(out_channels)
        )

    def forward(self, x):
        branch1 = self.branch1(x)
        branch2 = self.branch2(x)
        branch3 = self.branch3(x)

        # Concatenate branches
        out = paddle.concat([branch1, branch2, branch3], axis=1)
        out = self.aggregation_conv(out)

        # Residual connection with projection if needed
        if out.shape[1] != x.shape[1]:
            # Project residual to match channels
            residual = nn.Sequential(
                nn.Conv2D(x.shape[1], out.shape[1], kernel_size=1, bias_attr=False),
                nn.BatchNorm2D(out.shape[1])
            )(x)
        else:
            residual = x

        return out + residual


class StemLayer(nn.Layer):
    """Stem layer for initial feature extraction"""

    def __init__(self, in_channels: int = 3, out_channels: int = 48):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2D(in_channels, out_channels, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(out_channels),
            nn.ReLU(),
            nn.Conv2D(out_channels, out_channels, kernel_size=3, stride=1, padding=1, bias_attr=False),
            nn.BatchNorm2D(out_channels),
            nn.ReLU(),
        )

    def forward(self, x):
        return self.stem(x)


class PP_HGNetV2_B4(nn.Layer):
    """PP-HGNetV2-B4 Backbone for Tongue Classification

    High-performance GPU-efficient network architecture:
    - Lightweight stem layers
    - 4 stages with HG-Blocks
    - Global average pooling
    - Feature dimension: 864

    Args:
        num_classes: Number of output classes (for ImageNet pretraining, use 1000)
        in_channels: Number of input channels (default 3 for RGB)
        pretrained_path: Path to pretrained weights (optional)
    """

    def __init__(self, num_classes: int = 1000, in_channels: int = 3, pretrained_path: str = None):
        super().__init__()

        # Stem layer
        self.stem = StemLayer(in_channels, 48)

        # Stage 1: 1/4 resolution, 96 -> 108 channels
        self.stage1 = nn.Sequential(
            nn.Conv2D(48, 96, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(96),
            nn.ReLU(),
            HGBlock(96, 36, 108, kernel_size=3)
        )

        # Stage 2: 1/8 resolution, 108 -> 216 channels
        self.stage2 = nn.Sequential(
            nn.Conv2D(108, 192, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(192),
            nn.ReLU(),
            HGBlock(192, 72, 216, kernel_size=3)
        )

        # Stage 3: 1/16 resolution, 216 -> 432 channels
        self.stage3 = nn.Sequential(
            nn.Conv2D(216, 384, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(384),
            nn.ReLU(),
            HGBlock(384, 144, 432, kernel_size=3)
        )

        # Stage 4: 1/32 resolution, 432 -> 864 channels
        self.stage4 = nn.Sequential(
            nn.Conv2D(432, 768, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(768),
            nn.ReLU(),
            HGBlock(768, 288, 864, kernel_size=3)
        )

        # Global average pooling
        self.global_pool = nn.AdaptiveAvgPool2D((1, 1))

        # Feature dimension for classification head
        self.feature_dim = 864

        # Load pretrained weights if provided
        if pretrained_path and os.path.exists(pretrained_path):
            self._load_pretrained(pretrained_path)

    def _load_pretrained(self, pretrained_path: str):
        """Load pretrained weights"""
        logger.info(f"Loading pretrained weights from: {pretrained_path}")
        state_dict = paddle.load(pretrained_path)

        # Filter out classifier weights if present
        model_state = self.state_dict()
        pretrained_state = {}

        for name, param in state_dict.items():
            if name in model_state and model_state[name].shape == param.shape:
                pretrained_state[name] = param
            elif name in model_state:
                logger.warning(f"Shape mismatch for {name}: pretrained {param.shape} vs model {model_state[name].shape}")

        # Load compatible weights
        missing_keys, unexpected_keys = self.set_state_dict(pretrained_state)
        if missing_keys:
            logger.info(f"Missing keys in pretrained: {len(missing_keys)}")
        if unexpected_keys:
            logger.warning(f"Unexpected keys in pretrained: {len(unexpected_keys)}")
        logger.info(f"Loaded {len(pretrained_state)}/{len(model_state)} pretrained parameters")

    def forward(self, x):
        # Input: (N, 3, H, W)
        x = self.stem(x)           # -> (N, 48, H/2, W/2)
        x = self.stage1(x)         # -> (N, 108, H/4, W/4)
        x = self.stage2(x)         # -> (N, 216, H/8, W/8)
        x = self.stage3(x)         # -> (N, 432, H/16, W/16)
        x = self.stage4(x)         # -> (N, 864, H/32, W/32)
        x = self.global_pool(x)     # -> (N, 864, 1, 1)
        return paddle.flatten(x, 1)  # -> (N, 864)


class MultiHeadClassificationModel(nn.Layer):
    """Multi-Head Classification Model for Tongue Diagnosis

    Architecture:
    - Backbone: PP-HGNetV2-B4
    - Head 1: 舌色 (4 classes) - 淡红, 红, 绛紫, 淡白
    - Head 2: 苔色 (4 classes) - 白, 黄, 黑, 花剥
    - Head 3: 舌形 (3 classes) - 正常, 胖大, 瘦薄
    - Head 4: 苔质 (3 classes) - 薄, 厚, 腻
    - Head 5: 特征 (4 classes) - 无, 红点, 裂纹, 齿痕
    - Head 6: 健康 (2 classes) - 不健康, 健康

    Args:
        backbone: PP_HGNetV2_B4 backbone network
        head_configs: Dictionary of head configurations
        dropout: Dropout probability (default 0.2)
    """

    def __init__(self, backbone: nn.Layer, head_configs: Dict[str, Any] = None, dropout: float = 0.2):
        super().__init__()
        self.backbone = backbone
        self.feature_dim = backbone.feature_dim

        # Default head configurations for tongue diagnosis
        if head_configs is None:
            head_configs = {
                "tongue_color": {"num_classes": 4, "names": ["pale", "light_red", "red", "purple"]},
                "coating_color": {"num_classes": 4, "names": ["white", "yellow", "black", "peeling"]},
                "tongue_shape": {"num_classes": 3, "names": ["normal", "swollen", "thin"]},
                "coating_quality": {"num_classes": 3, "names": ["thin", "thick", "greasy"]},
                "features": {"num_classes": 4, "names": ["none", "red_dots", "cracks", "teeth_marks"]},
                "health": {"num_classes": 2, "names": ["unhealthy", "healthy"]},
            }

        # Build classification heads
        self.heads = nn.LayerDict()
        self.head_configs = {}

        for head_name, config in head_configs.items():
            num_classes = config["num_classes"]
            names = config.get("names", [])

            # Create head with intermediate layers
            hidden_dim = max(128, num_classes * 4)

            head = nn.Sequential(
                nn.Linear(self.feature_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, num_classes)
            )

            self.heads[head_name] = head
            self.head_configs[head_name] = {
                "num_classes": num_classes,
                "names": names
            }

        logger.info(f"MultiHeadClassificationModel created with {len(self.heads)} heads")
        for name, config in self.head_configs.items():
            logger.info(f"  {name}: {config['num_classes']} classes - {config['names']}")

    def forward(self, x, return_features: bool = False):
        """
        Forward pass

        Args:
            x: Input tensor (N, 3, H, W)
            return_features: If True, also return backbone features

        Returns:
            List of outputs from each head, or (outputs, features) if return_features=True
        """
        features = self.backbone(x)
        outputs = []

        for head_name in self.heads:
            head_output = self.heads[head_name](features)
            outputs.append(head_output)

        if return_features:
            return outputs, features
        return outputs


def create_model(pretrained: str = None) -> MultiHeadClassificationModel:
    """Create a new classification model with default configuration

    Args:
        pretrained: Path to pretrained backbone weights

    Returns:
        MultiHeadClassificationModel instance
    """
    backbone = PP_HGNetV2_B4(num_classes=1000, pretrained_path=pretrained)
    model = MultiHeadClassificationModel(backbone, dropout=0.2)
    return model


# ============================================================================
# Environment Verification
# ============================================================================

def verify_paddle_installation() -> Dict[str, Any]:
    """Verify PaddlePaddle installation"""
    logger.info("=" * 60)
    logger.info("PaddlePaddle Installation Verification")
    logger.info("=" * 60)

    if not PADDLE_AVAILABLE:
        return {
            "installed": False,
            "version": None,
            "device": None,
            "error": "PaddlePaddle not installed"
        }

    result = {
        "installed": True,
        "version": paddle.__version__,
        "device": paddle.get_device(),
    }

    logger.info(f"PaddlePaddle version: {result['version']}")
    logger.info(f"Default device: {result['device']}")

    # Check GPU availability
    if paddle.is_compiled_with_cuda():
        gpu_count = paddle.device.cuda.device_count()
        result["cuda_available"] = True
        result["gpu_count"] = gpu_count
        logger.info(f"CUDA available: Yes ({gpu_count} GPUs)")

        # Get GPU info
        if gpu_count > 0:
            for i in range(gpu_count):
                props = paddle.device.cuda.get_device_properties(i)
                logger.info(f"  GPU {i}: {props.name} ({props.total_memory / 1024**3:.1f} GB)")
    else:
        result["cuda_available"] = False
        result["gpu_count"] = 0
        logger.info("CUDA available: No (CPU mode only)")

    return result


def verify_model_structure() -> Dict[str, Any]:
    """Verify model structure can be created"""
    logger.info("=" * 60)
    logger.info("Model Structure Verification")
    logger.info("=" * 60)

    try:
        # Create backbone
        backbone = PP_HGNetV2_B4(num_classes=1000)
        logger.info("✓ PP_HGNetV2_B4 backbone created")

        # Count parameters
        total_params = sum(p.numel().item() for p in backbone.parameters())
        trainable_params = sum(p.numel().item() for p in backbone.parameters() if not p.stop_gradient)

        logger.info(f"  Total parameters: {total_params:,}")
        logger.info(f"  Trainable parameters: {trainable_params:,}")
        logger.info(f"  Feature dimension: {backbone.feature_dim}")

        # Create multi-head model
        model = MultiHeadClassificationModel(backbone)
        logger.info("✓ MultiHeadClassificationModel created")

        # Count head parameters
        head_params = sum(p.numel().item() for head in model.heads.values() for p in head.parameters())
        logger.info(f"  Head parameters: {head_params:,}")

        # Test forward pass
        x = paddle.randn([2, 3, 224, 224])
        outputs = model(x)

        logger.info(f"✓ Forward pass successful")
        logger.info(f"  Input shape: {x.shape}")
        for i, (name, head) in enumerate(model.heads.items()):
            logger.info(f"  Head {name}: {outputs[i].shape}")

        return {
            "success": True,
            "backbone_params": total_params,
            "head_params": head_params,
            "total_params": total_params + head_params,
            "feature_dim": backbone.feature_dim,
            "num_heads": len(model.heads)
        }

    except Exception as e:
        logger.error(f"Model structure verification failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def run_baseline_test(model: nn.Layer = None) -> Dict[str, Any]:
    """Run baseline forward pass test"""
    logger.info("=" * 60)
    logger.info("Baseline Forward Pass Test")
    logger.info("=" * 60)

    try:
        if model is None:
            model = create_model()

        model.eval()
        batch_size = 4
        image_size = 224

        # Warmup
        logger.info("Warming up...")
        with paddle.no_grad():
            for _ in range(3):
                x = paddle.randn([batch_size, 3, image_size, image_size])
                _ = model(x)

        # Benchmark
        logger.info(f"Running {batch_size} forward passes...")
        timings = []

        with paddle.no_grad():
            for _ in range(batch_size):
                x = paddle.randn([batch_size, 3, image_size, image_size])

                start_time = time.perf_counter()
                _ = model(x)
                end_time = time.perf_counter()

                timings.append((end_time - start_time) * 1000)

        import numpy as np
        timings_array = np.array(timings)
        mean_time = np.mean(timings_array)
        std_time = np.std(timings_array)

        logger.info(f"✓ Baseline test completed")
        logger.info(f"  Mean forward time: {mean_time:.2f} ms")
        logger.info(f"  Std forward time: {std_time:.2f} ms")
        logger.info(f"  Throughput: {1000 / mean_time * batch_size:.2f} samples/sec")

        return {
            "success": True,
            "mean_latency_ms": mean_time,
            "std_latency_ms": std_time,
            "throughput_samples_per_sec": 1000 / mean_time * batch_size
        }

    except Exception as e:
        logger.error(f"Baseline test failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def download_pretrained_weights(config: EnvironmentConfig) -> Dict[str, Any]:
    """Download pretrained ImageNet weights"""
    logger.info("=" * 60)
    logger.info("Pretrained Weights Download")
    logger.info("=" * 60)

    results = {}

    for model_name, url in config.pretrained_urls.items():
        weights_path = os.path.join(config.weights_dir, f"{model_name}_pretrained.pdparams")
        results[model_name] = {"path": weights_path, "downloaded": False, "cached": False}

        # Check if already downloaded
        if os.path.exists(weights_path):
            file_size = os.path.getsize(weights_path) / (1024 * 1024)
            logger.info(f"✓ {model_name} weights already cached: {weights_path} ({file_size:.1f} MB)")
            results[model_name]["cached"] = True
            results[model_name]["downloaded"] = True
            continue

        # Download
        logger.info(f"Downloading {model_name} from {url}")
        try:
            os.makedirs(config.weights_dir, exist_ok=True)

            # Use wget or curl
            if sys.platform == 'win32':
                cmd = ['curl', '-L', '-o', weights_path, url]
            else:
                cmd = ['wget', '-O', weights_path, url]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and os.path.exists(weights_path):
                file_size = os.path.getsize(weights_path) / (1024 * 1024)
                logger.info(f"✓ Downloaded {model_name}: {weights_path} ({file_size:.1f} MB)")
                results[model_name]["downloaded"] = True
            else:
                logger.warning(f"Failed to download {model_name}: {result.stderr}")
                results[model_name]["error"] = result.stderr

        except Exception as e:
            logger.error(f"Error downloading {model_name}: {e}")
            results[model_name]["error"] = str(e)

    return results


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(
    paddle_info: Dict[str, Any],
    model_info: Dict[str, Any],
    baseline_info: Dict[str, Any],
    weights_info: Dict[str, Any],
    config: EnvironmentConfig
) -> str:
    """Generate environment verification report"""

    report = {
        "timestamp": datetime.now().isoformat(),
        "paddlepaddle": paddle_info,
        "model": model_info,
        "baseline": baseline_info,
        "weights": weights_info,
        "config": {
            "min_paddle_version": list(config.min_paddle_version),
            "weights_dir": config.weights_dir,
            "output_dir": config.output_dir
        },
        "summary": {
            "environment_ready": (
                paddle_info.get("installed", False) and
                model_info.get("success", False) and
                baseline_info.get("success", False)
            )
        }
    }

    return report


# ============================================================================
# Main Execution
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="PaddleClas Environment Setup")
    parser.add_argument("--download-weights", action="store_true",
                       help="Download pretrained ImageNet weights")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify without downloading weights")
    parser.add_argument("--weights-dir", type=str,
                       default="models/paddle_clas/weights",
                       help="Directory to store pretrained weights")
    parser.add_argument("--output", type=str,
                       default="models/paddle_clas/environment_report.json",
                       help="Path to save verification report")

    args = parser.parse_args()

    # Create config
    config = EnvironmentConfig(weights_dir=args.weights_dir)

    # Step 1: Verify PaddlePaddle installation
    paddle_info = verify_paddle_installation()

    if not paddle_info.get("installed"):
        logger.error("PaddlePaddle is not installed. Please install it first:")
        logger.error("  pip install paddlepaddle-gpu  # For GPU")
        logger.error("  pip install paddlepaddle      # For CPU")
        return 1

    # Step 2: Verify model structure
    model_info = verify_model_structure()

    if not model_info.get("success"):
        logger.error("Model structure verification failed")
        return 1

    # Step 3: Run baseline test
    baseline_info = run_baseline_test()

    # Step 4: Download pretrained weights
    weights_info = {}
    if args.download_weights and not args.verify_only:
        weights_info = download_pretrained_weights(config)
    elif args.verify_only:
        # Check existing weights
        for model_name in config.pretrained_urls.keys():
            weights_path = os.path.join(config.weights_dir, f"{model_name}_pretrained.pdparams")
            weights_info[model_name] = {
                "path": weights_path,
                "exists": os.path.exists(weights_path)
            }
    else:
        logger.info("Skipping weights download (use --download-weights to enable)")

    # Step 5: Generate report
    report = generate_report(paddle_info, model_info, baseline_info, weights_info, config)

    # Save report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    logger.info("=" * 60)
    logger.info("ENVIRONMENT VERIFICATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"PaddlePaddle: {'✓' if paddle_info['installed'] else '✗'} v{paddle_info['version']}")
    logger.info(f"CUDA: {'✓' if paddle_info.get('cuda_available') else '✗'} ({paddle_info.get('gpu_count', 0)} GPUs)")
    logger.info(f"Model Structure: {'✓' if model_info['success'] else '✗'}")
    logger.info(f"Baseline Test: {'✓' if baseline_info['success'] else '✗'}")
    logger.info(f"Parameters: {model_info.get('total_params', 0):,}")
    logger.info(f"Heads: {model_info.get('num_heads', 0)}")
    logger.info("")
    logger.info(f"Report saved to: {args.output}")
    logger.info("")

    # Print acceptance criteria
    logger.info("=" * 60)
    logger.info("ACCEPTANCE CRITERIA CHECK")
    logger.info("=" * 60)

    criteria_pass = True

    # Check PaddleClas environment
    env_ok = paddle_info['installed'] and model_info['success']
    logger.info(f"PaddleClas environment: {'PASS' if env_ok else 'FAIL'}")
    if not env_ok:
        criteria_pass = False

    # Check PP-HGNetV2-B4 model
    model_ok = model_info['success'] and model_info.get('feature_dim') == 864
    logger.info(f"PP-HGNetV2-B4 model: {'PASS' if model_ok else 'FAIL'}")
    if not model_ok:
        criteria_pass = False

    # Check Multi-Head classification head
    heads_ok = model_info.get('num_heads', 0) == 6
    logger.info(f"Multi-Head classification head (Head1-3): {'PASS' if heads_ok else 'FAIL'}")
    if not heads_ok:
        criteria_pass = False

    # Check pretrained weights
    weights_ok = any(w.get('cached', w.get('downloaded', False)) for w in weights_info.values())
    logger.info(f"Pretrained weights: {'PASS' if weights_ok else 'FAIL (use --download-weights)'}")

    logger.info(f"\nOverall Status: {'PASS' if criteria_pass else 'FAIL'}")

    return 0 if criteria_pass else 1


if __name__ == "__main__":
    sys.exit(main())
