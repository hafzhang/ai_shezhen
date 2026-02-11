#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Inference Speed Testing Script for Tongue Diagnosis Models

Comprehensive performance testing for segmentation and classification models:
- CPU and GPU inference speed testing
- Batch size optimization
- Memory usage monitoring
- Latency percentiles (P50, P95, P99)
- FPS calculation
- Model comparison (FP32 vs FP16 vs INT8)

task-2-6: 推理速度测试与优化

Acceptance Criteria:
- CPU推理>30 FPS
- GPU推理>80 FPS
- 推理耗时P95 < 33ms
- 内存占用<2GB

Usage:
    # Test classification model
    python models/inference_speed_test.py --model-type classify --model-path models/paddle_clas/output/best_model/model.pdparams

    # Test segmentation model
    python models/inference_speed_test.py --model-type segment --model-path models/paddle_seg/output/best_model/model.pdparams

    # Test quantized models
    python models/inference_speed_test.py --model-type classify --model-path models/deploy/classify_fp16/model_fp16.pdparams --precision fp16

    # Comprehensive test with multiple batch sizes
    python models/inference_speed_test.py --model-type classify --model-path models/deploy/classify_fp16/model_fp16.pdparams --batch-sizes 1,4,8,16

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import json
import time
import psutil
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import gc

# Configure UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import numpy as np
from PIL import Image
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from paddle.io import Dataset, DataLoader
from tqdm import tqdm

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes for Test Results
# ============================================================================

@dataclass
class InferenceMetrics:
    """Inference performance metrics"""
    model_name: str
    model_path: str
    precision: str  # fp32, fp16, int8
    device: str  # cpu, gpu
    batch_size: int
    image_size: Tuple[int, int]  # (height, width)

    # Timing metrics (ms)
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    # Throughput metrics
    fps: float  # frames per second
    throughput_samples_per_sec: float

    # Memory metrics (MB)
    memory_before_mb: float
    memory_after_mb: float
    memory_peak_mb: float
    memory_used_mb: float

    # Additional info
    num_inferences: int
    warmup_runs: int
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OptimizationReport:
    """Optimization recommendations based on test results"""
    current_fps: float
    target_fps: float
    meets_target: bool
    recommendations: List[str]
    bottlenecks: List[str]


# ============================================================================
# Model Definitions
# ============================================================================

class SimpleUNet(nn.Layer):
    """Simplified U-Net for tongue segmentation"""

    def __init__(self, num_classes: int = 2):
        super().__init__()
        # Encoder
        self.enc1 = self._make_block(3, 64)
        self.enc2 = self._make_block(64, 128)
        self.enc3 = self._make_block(128, 256)
        self.enc4 = self._make_block(256, 512)

        # Decoder
        self.up3 = nn.Conv2DTranspose(512, 256, kernel_size=2, stride=2)
        self.dec3 = self._make_block(512, 256)
        self.up2 = nn.Conv2DTranspose(256, 128, kernel_size=2, stride=2)
        self.dec2 = self._make_block(256, 128)
        self.up1 = nn.Conv2DTranspose(128, 64, kernel_size=2, stride=2)
        self.dec1 = self._make_block(128, 64)

        # Output
        self.conv_last = nn.Conv2D(64, num_classes, kernel_size=1)

        # Pooling
        self.pool = nn.MaxPool2D(2, stride=2)

    def _make_block(self, in_ch, out_ch):
        return nn.Sequential(
            nn.Conv2D(in_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2D(out_ch),
            nn.ReLU(),
            nn.Conv2D(out_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2D(out_ch),
            nn.ReLU()
        )

    def forward(self, x):
        # Encoder
        e1 = self.enc1(x)
        p1 = self.pool(e1)
        e2 = self.enc2(p1)
        p2 = self.pool(e2)
        e3 = self.enc3(p2)
        p3 = self.pool(e3)
        e4 = self.enc4(p3)

        # Decoder
        d3 = self.up3(e4)
        d3 = paddle.concat([e3, d3], axis=1)
        d3 = self.dec3(d3)
        d2 = self.up2(d3)
        d2 = paddle.concat([e2, d2], axis=1)
        d2 = self.dec2(d2)
        d1 = self.up1(d2)
        d1 = paddle.concat([e1, d1], axis=1)
        d1 = self.dec1(d1)

        return self.conv_last(d1)


class LightConvBNReLU(nn.Layer):
    """Light Convolution Block for PP-HGNetV2"""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.conv1 = nn.Conv2D(in_channels, in_channels, kernel_size=1, bias_attr=False)
        self.conv2_dw = nn.Conv2D(
            in_channels, in_channels, kernel_size=kernel_size,
            padding=kernel_size // 2, groups=in_channels, bias_attr=False
        )
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
    """HG-Block for PP-HGNetV2"""

    def __init__(self, in_channels: int, mid_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.branch1 = LightConvBNReLU(in_channels, mid_channels, kernel_size)
        self.branch2 = LightConvBNReLU(in_channels, mid_channels, kernel_size)
        self.branch3 = LightConvBNReLU(in_channels, mid_channels, kernel_size)

        total_channels = mid_channels * 3
        self.aggregation_conv = nn.Sequential(
            nn.Conv2D(total_channels, out_channels, kernel_size=1, bias_attr=False),
            nn.BatchNorm2D(out_channels)
        )

    def forward(self, x):
        branch1 = self.branch1(x)
        branch2 = self.branch2(x)
        branch3 = self.branch3(x)

        out = paddle.concat([branch1, branch2, branch3], axis=1)
        out = self.aggregation_conv(out)

        if out.shape[1] != x.shape[1]:
            residual = nn.Sequential(
                nn.Conv2D(x.shape[1], out.shape[1], kernel_size=1, bias_attr=False),
                nn.BatchNorm2D(out.shape[1])
            )(x)
        else:
            residual = x

        return out + residual


class PP_HGNetV2_B4(nn.Layer):
    """PP-HGNetV2-B4 Backbone for Classification"""

    def __init__(self, num_classes: int = 18):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2D(3, 48, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(48),
            nn.ReLU(),
            nn.Conv2D(48, 48, kernel_size=3, stride=1, padding=1, bias_attr=False),
            nn.BatchNorm2D(48),
            nn.ReLU(),
        )

        self.stage1 = nn.Sequential(
            nn.Conv2D(48, 96, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(96),
            nn.ReLU(),
            HGBlock(96, 36, 108, kernel_size=3)
        )

        self.stage2 = nn.Sequential(
            nn.Conv2D(108, 192, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(192),
            nn.ReLU(),
            HGBlock(192, 72, 216, kernel_size=3)
        )

        self.stage3 = nn.Sequential(
            nn.Conv2D(216, 384, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(384),
            nn.ReLU(),
            HGBlock(384, 144, 432, kernel_size=3)
        )

        self.stage4 = nn.Sequential(
            nn.Conv2D(432, 768, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(768),
            nn.ReLU(),
            HGBlock(768, 288, 864, kernel_size=3)
        )

        self.global_pool = nn.AdaptiveAvgPool2D((1, 1))
        self.feature_dim = 864

    def forward(self, x):
        x = self.stem(x)
        x = self.stage1(x)
        x = self.stage2(x)
        x = self.stage3(x)
        x = self.stage4(x)
        x = self.global_pool(x)
        return paddle.flatten(x, 1)


class MultiHeadClassificationModel(nn.Layer):
    """Multi-Head Classification Model for Tongue Diagnosis"""

    def __init__(self, backbone: nn.Layer, num_classes: List[int] = [8, 6, 4]):
        super().__init__()
        self.backbone = backbone
        self.feature_dim = backbone.feature_dim

        self.head1 = nn.Sequential(
            nn.Linear(self.feature_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, num_classes[0])
        )

        self.head2 = nn.Sequential(
            nn.Linear(self.feature_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_classes[1])
        )

        self.head3 = nn.Sequential(
            nn.Linear(self.feature_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, num_classes[2])
        )

    def forward(self, x):
        features = self.backbone(x)
        return [self.head1(features), self.head2(features), self.head3(features)]


# ============================================================================
# Test Dataset
# ============================================================================

class InferenceTestDataset(Dataset):
    """Lightweight dataset for inference speed testing"""

    def __init__(self, data_root: str, split: str = 'test', max_samples: int = 100,
                 image_size: Tuple[int, int] = (224, 224)):
        self.data_root = Path(data_root)
        self.max_samples = max_samples
        self.image_size = image_size
        self.samples = []

        # Load test images - try multiple possible locations
        possible_paths = [
            self.data_root / split / "images",  # data_root/split/images
            self.data_root / "images",            # data_root/images
            self.data_root / split,                # data_root/split
            self.data_root,                        # data_root
        ]

        image_dir = None
        for path in possible_paths:
            if path.exists() and path.is_dir():
                jpg_files = list(path.glob("*.jpg"))
                if jpg_files:
                    image_dir = path
                    break

        if image_dir is None:
            # Use the first possible path anyway
            image_dir = possible_paths[0]

        for img_path in list(image_dir.glob("*.jpg"))[:max_samples]:
            self.samples.append(str(img_path))

        if len(self.samples) == 0:
            logger.warning(f"No images found in {image_dir}")
            # Create dummy data for testing
            self.dummy_mode = True
        else:
            self.dummy_mode = False

        logger.info(f"Loaded {len(self.samples)} samples from {image_dir}")

    def __len__(self):
        if self.dummy_mode:
            return self.max_samples  # Return max_samples for dummy mode
        return len(self.samples)

    def __getitem__(self, idx):
        if self.dummy_mode or idx >= len(self.samples):
            # Return dummy data
            img = Image.fromarray(np.random.randint(0, 255, (self.image_size[0], self.image_size[1], 3), dtype=np.uint8))
        else:
            img = Image.open(self.samples[idx]).convert('RGB')

        # Resize
        img = img.resize((self.image_size[1], self.image_size[0]))

        # Convert to tensor
        img = np.array(img).astype('float32').transpose(2, 0, 1) / 255.0

        return img


def collate_fn(batch):
    """Custom collate function for batching"""
    return paddle.to_tensor(np.stack(batch, axis=0))


# ============================================================================
# Inference Speed Tester
# ============================================================================

class InferenceSpeedTester:
    """Comprehensive inference speed testing for PaddlePaddle models"""

    def __init__(
        self,
        model_path: str,
        model_type: str = 'classify',
        precision: str = 'fp32',
        device: str = 'auto',
        image_size: Tuple[int, int] = (224, 224),
        num_warmup: int = 10,
        num_inferences: int = 100
    ):
        self.model_path = Path(model_path)
        self.model_type = model_type
        self.precision = precision
        self.image_size = image_size
        self.num_warmup = num_warmup
        self.num_inferences = num_inferences

        # Auto-detect device
        if device == 'auto':
            self.device = 'gpu' if paddle.is_compiled_with_cuda() else 'cpu'
        else:
            self.device = device

        # Set device
        if self.device == 'gpu':
            paddle.set_device('gpu')
        else:
            paddle.set_device('cpu')

        # Load model
        self.model = self._load_model()
        self.model.eval()

    def _load_model(self) -> nn.Layer:
        """Load model based on type"""
        logger.info(f"Loading {self.model_type} model from {self.model_path}")

        if self.model_type == 'classify':
            # Multi-head classification model
            backbone = PP_HGNetV2_B4()
            model = MultiHeadClassificationModel(backbone, num_classes=[8, 6, 4])
        elif self.model_type == 'segment':
            # Segmentation model
            model = SimpleUNet(num_classes=2)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        # Load weights
        if self.model_path.exists():
            state_dict = paddle.load(str(self.model_path))

            # Handle INT8/FP16 weights - convert to FP32 if needed
            needs_conversion = False
            convert_dtype = None

            for key, param in state_dict.items():
                if isinstance(param, paddle.Tensor):
                    if param.dtype == paddle.float16:
                        needs_conversion = True
                        convert_dtype = np.float32
                        break
                    elif param.dtype == paddle.int8 or param.dtype == paddle.uint8:
                        needs_conversion = True
                        convert_dtype = np.float32
                        break
                elif isinstance(param, np.ndarray):
                    if param.dtype == np.float16:
                        needs_conversion = True
                        convert_dtype = np.float32
                        break
                    elif param.dtype == np.int8 or param.dtype == np.uint8:
                        needs_conversion = True
                        convert_dtype = np.float32
                        break

            if needs_conversion:
                # Convert non-FP32 weights to FP32 for loading
                dtype_name = "FP16" if self.precision == 'fp16' else "INT8"
                logger.info(f"Converting {dtype_name} weights to FP32")
                fp32_state_dict = {}
                for key, param in state_dict.items():
                    if isinstance(param, paddle.Tensor):
                        fp32_state_dict[key] = param.cast(paddle.float32)
                    elif isinstance(param, np.ndarray):
                        fp32_state_dict[key] = paddle.to_tensor(param.astype(convert_dtype))
                    else:
                        fp32_state_dict[key] = param
                state_dict = fp32_state_dict

            model.set_state_dict(state_dict)
            logger.info("Model weights loaded successfully")
        else:
            logger.warning(f"Model file not found: {self.model_path}, using random weights")

        # Convert model to FP16 if needed for inference
        if self.precision == 'fp16':
            logger.info("Converting model to FP16 for inference")
            model = paddle.amp.decorate(models=model, level='O1')

        return model

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)

    def run_inference_test(
        self,
        batch_size: int = 1,
        data_root: str = None
    ) -> InferenceMetrics:
        """Run comprehensive inference speed test"""

        logger.info(f"\n{'='*60}")
        logger.info(f"Running inference test:")
        logger.info(f"  Model: {self.model_type}")
        logger.info(f"  Precision: {self.precision}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Image size: {self.image_size}")
        logger.info(f"{'='*60}\n")

        # Create dataset
        if data_root:
            dataset = InferenceTestDataset(data_root, max_samples=self.num_inferences, image_size=self.image_size)
        else:
            dataset = InferenceTestDataset(
                "datasets/processed/seg_v1",
                max_samples=self.num_inferences,
                image_size=self.image_size
            )

        dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            num_workers=0,
            drop_last=True
        )

        # Get memory before
        memory_before = self.get_memory_usage()
        memory_peak = memory_before

        # Warmup
        logger.info(f"Warming up with {self.num_warmup} iterations...")
        for i, batch in enumerate(dataloader):
            if i >= self.num_warmup:
                break
            with paddle.no_grad():
                _ = self.model(batch)

        logger.info("Warmup complete. Running benchmark...")

        # Benchmark
        latencies = []
        start_time = time.time()
        total_samples = 0

        with paddle.no_grad():
            for i, batch in enumerate(dataloader):
                if total_samples >= self.num_inferences:
                    break

                iter_start = time.time()
                _ = self.model(batch)
                iter_end = time.time()

                latencies.append((iter_end - iter_start) * 1000)  # Convert to ms
                total_samples += batch.shape[0]

                # Track peak memory
                memory_current = self.get_memory_usage()
                memory_peak = max(memory_peak, memory_current)

        total_time = time.time() - start_time

        # Get memory after
        memory_after = self.get_memory_usage()
        gc.collect()

        # Calculate metrics
        latencies_array = np.array(latencies)

        metrics = InferenceMetrics(
            model_name=f"{self.model_type}_{self.precision}",
            model_path=str(self.model_path),
            precision=self.precision,
            device=self.device,
            batch_size=batch_size,
            image_size=self.image_size,
            avg_latency_ms=float(np.mean(latencies_array)),
            min_latency_ms=float(np.min(latencies_array)),
            max_latency_ms=float(np.max(latencies_array)),
            p50_latency_ms=float(np.percentile(latencies_array, 50)),
            p95_latency_ms=float(np.percentile(latencies_array, 95)),
            p99_latency_ms=float(np.percentile(latencies_array, 99)),
            fps=total_samples / total_time,
            throughput_samples_per_sec=total_samples / total_time,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_peak_mb=memory_peak,
            memory_used_mb=memory_after - memory_before,
            num_inferences=len(latencies),
            warmup_runs=self.num_warmup,
            timestamp=datetime.now().isoformat()
        )

        self._print_results(metrics)
        return metrics

    def _print_results(self, metrics: InferenceMetrics):
        """Print test results in formatted table"""
        logger.info(f"\n{'='*60}")
        logger.info("Inference Speed Test Results")
        logger.info(f"{'='*60}")

        logger.info(f"\nConfiguration:")
        logger.info(f"  Model: {metrics.model_name}")
        logger.info(f"  Device: {metrics.device.upper()}")
        logger.info(f"  Batch Size: {metrics.batch_size}")
        logger.info(f"  Image Size: {metrics.image_size[1]}x{metrics.image_size[0]}")

        logger.info(f"\nLatency (ms):")
        logger.info(f"  Average: {metrics.avg_latency_ms:.2f} ms")
        logger.info(f"  Min: {metrics.min_latency_ms:.2f} ms")
        logger.info(f"  Max: {metrics.max_latency_ms:.2f} ms")
        logger.info(f"  P50 (Median): {metrics.p50_latency_ms:.2f} ms")
        logger.info(f"  P95: {metrics.p95_latency_ms:.2f} ms {'✓' if metrics.p95_latency_ms < 33 else '✗'}")
        logger.info(f"  P99: {metrics.p99_latency_ms:.2f} ms")

        logger.info(f"\nThroughput:")
        logger.info(f"  FPS: {metrics.fps:.2f} fps {'✓' if self._check_fps_target(metrics.fps) else '✗'}")
        logger.info(f"  Samples/sec: {metrics.throughput_samples_per_sec:.2f}")

        logger.info(f"\nMemory Usage:")
        logger.info(f"  Before: {metrics.memory_before_mb:.2f} MB")
        logger.info(f"  After: {metrics.memory_after_mb:.2f} MB")
        logger.info(f"  Peak: {metrics.memory_peak_mb:.2f} MB {'✓' if metrics.memory_peak_mb < 2048 else '✗'}")
        logger.info(f"  Used: {metrics.memory_used_mb:.2f} MB")

        logger.info(f"\nTest Info:")
        logger.info(f"  Total Inferences: {metrics.num_inferences}")
        logger.info(f"  Warmup Runs: {metrics.warmup_runs}")
        logger.info(f"  Timestamp: {metrics.timestamp}")

        logger.info(f"{'='*60}\n")

    def _check_fps_target(self, fps: float) -> bool:
        """Check if FPS meets target based on device"""
        if self.device == 'cpu':
            return fps > 30
        else:
            return fps > 80

    def generate_optimization_report(self, metrics: InferenceMetrics) -> OptimizationReport:
        """Generate optimization recommendations"""
        recommendations = []
        bottlenecks = []

        target_fps = 80 if self.device == 'gpu' else 30
        meets_target = metrics.fps >= target_fps

        if not meets_target:
            if metrics.avg_latency_ms > 100:
                recommendations.append("Use FP16 quantization (2x speedup, minimal accuracy loss)")
                bottlenecks.append("Model precision - FP32 is slow")

            if metrics.batch_size == 1 and metrics.device == 'gpu':
                recommendations.append("Increase batch size for better GPU utilization")
                bottlenecks.append("Batch size - single image underutilizes GPU")

            if metrics.memory_peak_mb < 500 and self.device == 'gpu':
                recommendations.append("Model is small - consider using larger backbone or multi-model batching")
                bottlenecks.append("GPU underutilization")

            if self.device == 'cpu':
                recommendations.append("Use GPU inference if available (10-20x speedup)")
                bottlenecks.append("CPU inference is slow for deep learning")
                recommendations.append("Enable MKL-DNN or oneDNN for CPU acceleration")
                recommendations.append("Consider model pruning to reduce FLOPs")

        # Memory optimization
        if metrics.memory_peak_mb > 2000:
            recommendations.append("Memory usage is high - enable gradient checkpointing or model partitioning")
            bottlenecks.append("High memory usage")

        return OptimizationReport(
            current_fps=metrics.fps,
            target_fps=target_fps,
            meets_target=meets_target,
            recommendations=recommendations,
            bottlenecks=bottlenecks
        )


# ============================================================================
# Batch Testing
# ============================================================================

def run_comprehensive_test(
    model_path: str,
    model_type: str,
    precision: str,
    batch_sizes: List[int] = None,
    data_root: str = None
) -> List[InferenceMetrics]:
    """Run tests with multiple batch sizes"""

    if batch_sizes is None:
        batch_sizes = [1, 4, 8, 16]

    results = []

    # Test different image sizes based on model type
    image_size = (224, 224) if model_type == 'classify' else (512, 512)

    for batch_size in batch_sizes:
        tester = InferenceSpeedTester(
            model_path=model_path,
            model_type=model_type,
            precision=precision,
            num_warmup=5,
            num_inferences=50
        )

        try:
            metrics = tester.run_inference_test(
                batch_size=batch_size,
                data_root=data_root
            )
            results.append(metrics)
        except Exception as e:
            logger.error(f"Error testing batch_size={batch_size}: {e}")

    return results


# ============================================================================
# Report Generation
# ============================================================================

def generate_test_report(
    results: List[InferenceMetrics],
    output_path: str = None
) -> Dict:
    """Generate comprehensive test report"""

    if not results:
        logger.error("No results to generate report")
        return {}

    report = {
        "test_summary": {
            "total_tests": len(results),
            "timestamp": datetime.now().isoformat(),
            "target_cpu_fps": 30,
            "target_gpu_fps": 80,
            "target_p95_ms": 33,
            "target_memory_mb": 2048
        },
        "results": [r.to_dict() for r in results],
        "summary": {
            "best_fps": max(r.fps for r in results),
            "best_latency": min(r.avg_latency_ms for r in results),
            "avg_memory": np.mean([r.memory_peak_mb for r in results])
        }
    }

    # Add pass/fail status
    for r in results:
        r_dict = r.to_dict()
        target_fps = 80 if r.device == 'gpu' else 30
        r_dict["passes"] = {
            "fps_target": r.fps >= target_fps,
            "p95_target": r.p95_latency_ms < 33,
            "memory_target": r.memory_peak_mb < 2048
        }

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report saved to {output_path}")

    return report


def print_comparison_table(results: List[InferenceMetrics]):
    """Print comparison table for multiple results"""
    if len(results) < 2:
        return

    logger.info(f"\n{'='*80}")
    logger.info("Performance Comparison Table")
    logger.info(f"{'='*80}")

    # Header
    header = f"{'Batch':<8} {'FPS':<10} {'P95 (ms)':<12} {'Memory (MB)':<12} {'Status'}"
    logger.info(header)
    logger.info("-" * 80)

    # Rows
    for r in results:
        target_fps = 80 if r.device == 'gpu' else 30
        fps_pass = r.fps >= target_fps
        p95_pass = r.p95_latency_ms < 33
        memory_pass = r.memory_peak_mb < 2048
        status = "✓ PASS" if fps_pass and p95_pass and memory_pass else "✗ FAIL"
        row = f"{r.batch_size:<8} {r.fps:<10.2f} {r.p95_latency_ms:<12.2f} {r.memory_peak_mb:<12.2f} {status}"
        logger.info(row)

    logger.info(f"{'='*80}\n")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Inference Speed Testing for Tongue Diagnosis Models')

    parser.add_argument('--model-path', type=str, required=True,
                        help='Path to model weights (.pdparams)')
    parser.add_argument('--model-type', type=str, choices=['classify', 'segment'], default='classify',
                        help='Type of model: classify or segment')
    parser.add_argument('--precision', type=str, choices=['fp32', 'fp16', 'int8'], default='fp32',
                        help='Model precision type')
    parser.add_argument('--device', type=str, choices=['auto', 'cpu', 'gpu'], default='auto',
                        help='Device to run inference on')
    parser.add_argument('--batch-sizes', type=str, default='1',
                        help='Comma-separated list of batch sizes to test')
    parser.add_argument('--image-size', type=str, default=None,
                        help='Image size (e.g., 224,224). Auto-detected if not specified.')
    parser.add_argument('--data-root', type=str, default=None,
                        help='Path to test data directory')
    parser.add_argument('--num-inferences', type=int, default=100,
                        help='Number of inferences for benchmarking')
    parser.add_argument('--num-warmup', type=int, default=10,
                        help='Number of warmup iterations')
    parser.add_argument('--output', type=str, default=None,
                        help='Output path for JSON report')
    parser.add_argument('--optimize', action='store_true',
                        help='Generate optimization recommendations')

    args = parser.parse_args()

    # Parse batch sizes
    batch_sizes = [int(x) for x in args.batch_sizes.split(',')]

    # Determine image size
    if args.image_size:
        image_size = tuple(int(x) for x in args.image_size.split(','))
    else:
        image_size = (224, 224) if args.model_type == 'classify' else (512, 512)

    logger.info("Starting inference speed testing...")
    logger.info(f"Model: {args.model_path}")
    logger.info(f"Type: {args.model_type}, Precision: {args.precision}")

    # Run tests
    results = run_comprehensive_test(
        model_path=args.model_path,
        model_type=args.model_type,
        precision=args.precision,
        batch_sizes=batch_sizes,
        data_root=args.data_root
    )

    if results:
        # Print comparison
        print_comparison_table(results)

        # Generate report
        report = generate_test_report(results, output_path=args.output)

        # Optimization recommendations
        if args.optimize:
            best_result = max(results, key=lambda r: r.fps)
            tester = InferenceSpeedTester(
                model_path=args.model_path,
                model_type=args.model_type,
                precision=args.precision
            )
            opt_report = tester.generate_optimization_report(best_result)

            logger.info(f"\n{'='*60}")
            logger.info("Optimization Recommendations")
            logger.info(f"{'='*60}")
            logger.info(f"Current FPS: {opt_report.current_fps:.2f}")
            logger.info(f"Target FPS: {opt_report.target_fps}")
            logger.info(f"Status: {'✓ Meets target' if opt_report.meets_target else '✗ Below target'}")

            if opt_report.bottlenecks:
                logger.info("\nBottlenecks:")
                for b in opt_report.bottlenecks:
                    logger.info(f"  - {b}")

            if opt_report.recommendations:
                logger.info("\nRecommendations:")
                for r in opt_report.recommendations:
                    logger.info(f"  - {r}")
            logger.info(f"{'='*60}\n")

    return 0 if results else 1


if __name__ == '__main__':
    sys.exit(main())
