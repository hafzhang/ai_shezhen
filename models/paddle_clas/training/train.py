#\!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Training Script for Multi-Task Tongue Classification

Implements 60-epoch training with:
- CosineAnnealingWarmRestarts learning rate schedule
- Early stopping (patience=10)
- CutMix and MixUp augmentation
- Curriculum learning strategy
- MLflow tracking
- Multi-task loss with FocalLoss and AsymmetricLoss

Author: Ralph Agent
Date: 2026-02-12
Task: task-3-4 - 核心训练（60 epochs + 早停）
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import numpy as np

import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from paddle.io import Dataset, DataLoader
from paddle.vision.transforms import transforms

# Note: UTF-8 encoding is configured by setting PYTHONIOENCODING=utf-8
# We do not wrap stdout/stderr at module level as it causes issues with imports

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from models.paddle_clas.models.pphgnetv2 import PP_HGNetV2_B4, create_backbone
from models.paddle_clas.models.multi_head import (
    MultiHeadTongueModel, create_multi_head_model, DEFAULT_HEAD_CONFIGS
)
from models.paddle_clas.losses.multi_task_loss import (
    MultiTaskLoss, create_multi_task_loss_from_config, HeadLossConfig
)
from models.paddle_clas.training.curriculum_learning import (
    CurriculumScheduler,
    DynamicClassWeightScheduler,
    GradientAccumulator,
    CurriculumTrainingConfig
)

# MLflow integration (optional)
try:
    import mlflow
    import mlflow.paddle
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    print("Warning: MLflow not available. Install with: pip install mlflow")


# ============================================================================
# Dataset Implementation
# ============================================================================

class TongueClassificationDataset(Dataset):
    """Dataset for multi-task tongue classification

    Args:
        image_dir: Directory containing images
        label_file: Path to label file (filename	labels)
        transform: Optional transforms
    """

    def __init__(
        self,
        image_dir: str,
        label_file: str,
        transform: Optional[Any] = None
    ):
        self.image_dir = Path(image_dir)
        self.transform = transform
        self.samples = []

        # Parse label file
        with open(label_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('	')
                if len(parts) >= 2:
                    filename = parts[0]
                    labels = [int(x) for x in parts[1].split(',')]
                    self.samples.append({
                        'filename': filename,
                        'labels': labels  # 19-dimensional multi-label vector
                    })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor]]:
        sample = self.samples[idx]

        # Load image
        image_path = self.image_dir / sample['filename']
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        from PIL import Image
        image = Image.open(image_path).convert('RGB')

        # Apply transforms
        if self.transform:
            image = self.transform(image)

        # Parse multi-label into head-specific targets
        labels = sample['labels']
        # Format: [tongue_color(4), coating_color(4), tongue_shape(3),
        #          coating_quality(3), features(3), health(2)] = 19 total

        targets = {
            'tongue_color': paddle.to_tensor(labels[0:4], dtype='int64').argmax(),
            'coating_color': paddle.to_tensor(labels[4:8], dtype='int64').argmax(),
            'tongue_shape': paddle.to_tensor(labels[8:11], dtype='int64').argmax(),
            'coating_quality': paddle.to_tensor(labels[11:14], dtype='int64').argmax(),
            'features': paddle.to_tensor(labels[14:17], dtype='float32'),
            'health': paddle.to_tensor(labels[17:19], dtype='int64').argmax()
        }

        return image, targets
