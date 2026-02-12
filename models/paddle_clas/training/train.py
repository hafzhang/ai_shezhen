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


# ============================================================================
# CutMix and MixUp Augmentation
# ============================================================================

class CutMix:
    """CutMix augmentation for classification

    CutMix cuts a random box from one image and pastes it onto another.
    The label is mixed proportionally to the area of the cut.

    Args:
        alpha: Beta distribution parameter for cut ratio (default: 1.0)
        prob: Probability of applying CutMix (default: 0.2)
    """

    def __init__(self, alpha: float = 1.0, prob: float = 0.2):
        self.alpha = alpha
        self.prob = prob

    def __call__(
        self,
        images: paddle.Tensor,
        targets: Dict[str, paddle.Tensor]
    ) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor], paddle.Tensor, Dict[str, paddle.Tensor]]:
        """
        Apply CutMix augmentation

        Args:
            images: Batch of images (B, C, H, W)
            targets: Dictionary of target tensors

        Returns:
            Tuple of (mixed_images, mixed_targets, lambda, targets_a, targets_b)
        """
        if np.random.random() > self.prob:
            return images, targets, None, None, None

        batch_size = images.shape[0]
        lam = np.random.beta(self.alpha, self.alpha)

        # Shuffle indices
        rand_index = np.random.permutation(batch_size)
        rand_index = paddle.to_tensor(rand_index, dtype='int64')

        # Get cut ratio
        cut_rat = np.sqrt(1.0 - lam)
        cut_w = int(images.shape[3] * cut_rat)
        cut_h = int(images.shape[2] * cut_rat)

        # Get random center
        cx = np.random.randint(images.shape[3])
        cy = np.random.randint(images.shape[2])

        # Get box boundaries
        bbx1 = np.clip(cx - cut_w // 2, 0, images.shape[3])
        bby1 = np.clip(cy - cut_h // 2, 0, images.shape[2])
        bbx2 = np.clip(cx + cut_w // 2, 0, images.shape[3])
        bby2 = np.clip(cy + cut_h // 2, 0, images.shape[2])

        # Apply CutMix
        mixed_images = images.clone()
        mixed_images[:, :, bby1:bby2, bbx1:bbx2] = \
            images[rand_index, :, bby1:bby2, bbx1:bbx2]

        # Adjust lambda based on actual cut area
        lam = 1 - ((bbx2 - bbx1) * (bby2 - bby1) /
                   (images.shape[3] * images.shape[2]))
        lam = paddle.to_tensor(lam, dtype='float32')

        # Split targets for two images
        targets_a = targets
        targets_b = {k: v[rand_index] for k, v in targets.items()}

        return mixed_images, targets, lam, targets_a, targets_b


class MixUp:
    """MixUp augmentation for classification

    MixUp blends two images and their labels.
    label = lam * label_a + (1 - lam) * label_b

    Args:
        alpha: Beta distribution parameter for mixing ratio (default: 0.2)
        prob: Probability of applying MixUp (default: 0.1)
    """

    def __init__(self, alpha: float = 0.2, prob: float = 0.1):
        self.alpha = alpha
        self.prob = prob

    def __call__(
        self,
        images: paddle.Tensor,
        targets: Dict[str, paddle.Tensor]
    ) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor], paddle.Tensor, Dict[str, paddle.Tensor]]:
        """
        Apply MixUp augmentation

        Args:
            images: Batch of images (B, C, H, W)
            targets: Dictionary of target tensors

        Returns:
            Tuple of (mixed_images, mixed_targets, lambda, targets_a, targets_b)
        """
        if np.random.random() > self.prob:
            return images, targets, None, None, None

        batch_size = images.shape[0]
        lam = np.random.beta(self.alpha, self.alpha)

        # Shuffle indices
        rand_index = np.random.permutation(batch_size)
        rand_index = paddle.to_tensor(rand_index, dtype='int64')

        # Mix images
        mixed_images = lam * images + (1 - lam) * images[rand_index]

        lam = paddle.to_tensor(lam, dtype='float32')

        # Split targets
        targets_a = targets
        targets_b = {k: v[rand_index] for k, v in targets.items()}

        return mixed_images, targets, lam, targets_a, targets_b


# ============================================================================
# Learning Rate Schedulers
# ============================================================================

class CosineAnnealingWarmRestarts:
    """Cosine annealing with warm restarts

    Implements the SGDR scheduler with periodic warm restarts.
    LR = min_lr + (max_lr - min_lr) * (1 + cos(pi * T_cur / T_i)) / 2

    Args:
        max_lr: Maximum learning rate
        min_lr: Minimum learning rate
        T_0: Initial period (number of iterations in first restart)
        T_mult: Factor to multiply T_0 after each restart (default: 1)
    """

    def __init__(
        self,
        max_lr: float = 0.001,
        min_lr: float = 1e-6,
        T_0: int = 10,
        T_mult: int = 2
    ):
        self.max_lr = max_lr
        self.min_lr = min_lr
        self.T_0 = T_0
        self.T_mult = T_mult
        self.T_cur = 0
        self.current_T_i = T_0
        self.restart_count = 0

    def step(self):
        """Advance one step"""
        self.T_cur += 1
        if self.T_cur >= self.current_T_i:
            self.T_cur = 0
            self.restart_count += 1
            self.current_T_i *= self.T_mult

    def get_lr(self) -> float:
        """Get current learning rate"""
        return self.min_lr + (self.max_lr - self.min_lr) * \
            (1 + np.cos(np.pi * self.T_cur / self.current_T_i)) / 2

    def state_dict(self) -> Dict:
        """Get scheduler state"""
        return {
            'max_lr': self.max_lr,
            'min_lr': self.min_lr,
            'T_0': self.T_0,
            'T_mult': self.T_mult,
            'T_cur': self.T_cur,
            'current_T_i': self.current_T_i,
            'restart_count': self.restart_count
        }

    def load_state_dict(self, state: Dict):
        """Load scheduler state"""
        self.max_lr = state['max_lr']
        self.min_lr = state['min_lr']
        self.T_0 = state['T_0']
        self.T_mult = state['T_mult']
        self.T_cur = state['T_cur']
        self.current_T_i = state['current_T_i']
        self.restart_count = state['restart_count']


# ============================================================================
# Early Stopping
# ============================================================================

class EarlyStopping:
    """Early stopping to stop training when validation metric doesn't improve

    Args:
        patience: Number of epochs to wait for improvement (default: 10)
        min_delta: Minimum change to qualify as improvement (default: 0.001)
        mode: 'min' for metrics like loss, 'max' for metrics like mIoU (default: 'max')
        verbose: Print messages (default: True)
    """

    def __init__(
        self,
        patience: int = 10,
        min_delta: float = 0.001,
        mode: str = 'max',
        verbose: bool = True
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.verbose = verbose
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.best_epoch = 0

    def __call__(self, epoch: int, score: float) -> bool:
        """
        Check if should stop training

        Args:
            epoch: Current epoch number
            score: Current validation score

        Returns:
            True if should stop, False otherwise
        """
        if self.best_score is None:
            self.best_score = score
            self.best_epoch = epoch
            return False

        if self.mode == 'max':
            improved = score > self.best_score + self.min_delta
        else:
            improved = score < self.best_score - self.min_delta

        if improved:
            self.best_score = score
            self.best_epoch = epoch
            self.counter = 0
            if self.verbose:
                print(f"Validation improved. Best score: {self.best_score:.4f}")
        else:
            self.counter += 1
            if self.verbose:
                print(f"Validation didn't improve. Counter: {self.counter}/{self.patience}")
            if self.counter >= self.patience:
                self.early_stop = True
                if self.verbose:
                    print(f"Early stopping triggered at epoch {epoch}")
                return True

        return False

    def get_best_info(self) -> Dict[str, Any]:
        """Get information about best epoch"""
        return {
            'best_score': self.best_score,
            'best_epoch': self.best_epoch,
            'counter': self.counter,
            'early_stop': self.early_stop
        }


# ============================================================================
# Metrics Computation
# ============================================================================

def compute_metrics(
    predictions: Dict[str, paddle.Tensor],
    targets: Dict[str, paddle.Tensor]
) -> Dict[str, Dict[str, float]]:
    """
    Compute evaluation metrics for all heads

    Args:
        predictions: Dictionary of prediction tensors
        targets: Dictionary of target tensors

    Returns:
        Dictionary of metrics per head
    """
    metrics = {}

    for head_name in predictions.keys():
        if head_name not in targets:
            continue

        pred = predictions[head_name]
        target = targets[head_name]

        # Get predicted class
        if pred.ndim > 2:
            pred = pred.reshape([pred.shape[0], pred.shape[1], -1]).mean(axis=2)
        pred_class = pred.argmax(axis=1)

        # Get target class
        if target.ndim > 1:
            target_class = target.argmax(axis=1)
        else:
            target_class = target

        # Convert to numpy for computation
        pred_np = pred_class.numpy()
        target_np = target_class.numpy()

        # Compute accuracy
        accuracy = (pred_np == target_np).mean()

        # Compute per-class precision/recall/F1
        num_classes = pred.shape[1]
        precision_list = []
        recall_list = []
        f1_list = []

        for c in range(num_classes):
            tp = ((pred_np == c) & (target_np == c)).sum()
            fp = ((pred_np == c) & (target_np != c)).sum()
            fn = ((pred_np != c) & (target_np == c)).sum()

            if tp + fp > 0:
                precision = tp / (tp + fp)
            else:
                precision = 0.0

            if tp + fn > 0:
                recall = tp / (tp + fn)
            else:
                recall = 0.0

            if precision + recall > 0:
                f1 = 2 * precision * recall / (precision + recall)
            else:
                f1 = 0.0

            precision_list.append(precision)
            recall_list.append(recall)
            f1_list.append(f1)

        metrics[head_name] = {
            'accuracy': float(accuracy),
            'precision': float(np.mean(precision_list)),
            'recall': float(np.mean(recall_list)),
            'f1': float(np.mean(f1_list)),
            'per_class_f1': f1_list
        }

    return metrics


def compute_map(
    all_predictions: Dict[str, List[paddle.Tensor]],
    all_targets: Dict[str, List[paddle.Tensor]]
) -> Dict[str, float]:
    """
    Compute mean Average Precision (mAP) for multi-label classification

    Args:
        all_predictions: Dictionary of lists of prediction tensors
        all_targets: Dictionary of lists of target tensors

    Returns:
        Dictionary of mAP per head
    """
    map_scores = {}

    for head_name in all_predictions.keys():
        if head_name not in all_targets:
            continue

        preds = paddle.concat(all_predictions[head_name], axis=0)
        targets = paddle.concat(all_targets[head_name], axis=0)

        # Convert to numpy
        pred_probs = F.sigmoid(preds).numpy() if preds.shape[1] > 2 else \
            F.softmax(preds, axis=1).numpy()
        target_np = targets.numpy()

        # Compute AP for each class
        num_classes = pred_probs.shape[1]
        ap_scores = []

        for c in range(num_classes):
            # Sort by prediction confidence
            indices = np.argsort(-pred_probs[:, c])
            sorted_preds = pred_probs[indices, c]
            sorted_targets = target_np[indices]

            # Compute precision at each threshold
            tp = np.cumsum(sorted_targets == c)
            fp = np.cumsum(sorted_targets != c)
            precision = tp / (tp + fp + 1e-8)

            # Compute AP
            if sorted_targets[-1] == c:
                ap = precision[sorted_targets == c].mean()
            else:
                ap = 0.0
            ap_scores.append(ap)

        map_scores[head_name] = float(np.mean(ap_scores))

    return map_scores


# ============================================================================
# Training Function
# ============================================================================

def train_one_epoch(
    model: nn.Layer,
    dataloader: DataLoader,
    criterion: MultiTaskLoss,
    optimizer: paddle.optimizer.Optimizer,
    scheduler: CosineAnnealingWarmRestarts,
    cutmix: CutMix,
    mixup: MixUp,
    curriculum_config: CurriculumTrainingConfig,
    epoch: int,
    active_tasks: List[str],
    gradient_accumulation_steps: int = 1
) -> Dict[str, float]:
    """Train for one epoch

    Args:
        model: The model to train
        dataloader: Training data loader
        criterion: Loss function
        optimizer: Optimizer
        scheduler: Learning rate scheduler
        cutmix: CutMix augmentation
        mixup: MixUp augmentation
        curriculum_config: Curriculum learning configuration
        epoch: Current epoch number
        active_tasks: List of active tasks for this epoch
        gradient_accumulation_steps: Number of steps to accumulate gradients

    Returns:
        Dictionary of training metrics
    """
    model.train()
    total_loss = 0.0
    per_head_losses = {k: 0.0 for k in active_tasks}
    num_batches = 0

    accumulator = GradientAccumulator(accumulate_steps=gradient_accumulation_steps)

    for batch_idx, (images, targets) in enumerate(dataloader):
        images = paddle.to_tensor(images.numpy(), dtype='float32')
        for k, v in targets.items():
            targets[k] = paddle.to_tensor(v.numpy())

        # Apply CutMix or MixUp
        lam = None
        targets_a, targets_b = None, None

        if np.random.random() < 0.3:
            # Try CutMix first
            images, targets, lam, targets_a, targets_b = cutmix(images, targets)
        else:
            # Try MixUp
            images, targets, lam, targets_a, targets_b = mixup(images, targets)

        with accumulator.accumulate():
            # Forward pass
            predictions = model(images)

            # Compute loss for active tasks only
            loss, head_losses = criterion(predictions, targets, head_names=active_tasks)

            # Apply MixUp/CutMix label smoothing if applicable
            if lam is not None:
                loss_b, _ = criterion(predictions, targets_b, head_names=active_tasks)
                loss = lam * loss + (1 - lam) * loss_b

            # Scale loss for gradient accumulation
            loss = loss / gradient_accumulation_steps

            # Backward pass
            loss.backward()

        # Update weights
        if accumulator.step():
            optimizer.step()
            optimizer.clear_grad()
            scheduler.step()

        # Track metrics
        total_loss += loss.item() * gradient_accumulation_steps
        for head_name in head_losses.keys():
            per_head_losses[head_name] += head_losses[head_name].item()
        num_batches += 1

        # Print progress
        if (batch_idx + 1) % 50 == 0:
            print(f"Batch [{batch_idx + 1}/{len(dataloader)}], "
                  f"Loss: {loss.item() * gradient_accumulation_steps:.4f}, "
                  f"LR: {scheduler.get_lr():.6f}")

    # Compute average metrics
    avg_metrics = {
        'total_loss': total_loss / num_batches,
        'lr': scheduler.get_lr()
    }
    for head_name in active_tasks:
        avg_metrics[f'{head_name}_loss'] = per_head_losses[head_name] / num_batches

    return avg_metrics


def validate(
    model: nn.Layer,
    dataloader: DataLoader,
    criterion: MultiTaskLoss,
    active_tasks: List[str]
) -> Dict[str, float]:
    """Validate the model

    Args:
        model: The model to validate
        dataloader: Validation data loader
        criterion: Loss function
        active_tasks: List of active tasks

    Returns:
        Dictionary of validation metrics
    """
    model.eval()
    total_loss = 0.0
    per_head_losses = {k: 0.0 for k in active_tasks}
    num_batches = 0

    all_predictions = {k: [] for k in active_tasks}
    all_targets = {k: [] for k in active_tasks}

    with paddle.no_grad():
        for images, targets in dataloader:
            images = paddle.to_tensor(images.numpy(), dtype='float32')
            for k, v in targets.items():
                targets[k] = paddle.to_tensor(v.numpy())

            # Forward pass
            predictions = model(images)

            # Compute loss
            loss, head_losses = criterion(predictions, targets, head_names=active_tasks)

            total_loss += loss.item()
            for head_name in head_losses.keys():
                per_head_losses[head_name] += head_losses[head_name].item()
            num_batches += 1

            # Store predictions and targets for metrics
            for head_name in active_tasks:
                if head_name in predictions:
                    all_predictions[head_name].append(predictions[head_name].clone())
                    all_targets[head_name].append(targets[head_name].clone())

    # Compute average loss
    avg_metrics = {
        'val_loss': total_loss / num_batches
    }
    for head_name in active_tasks:
        avg_metrics[f'val_{head_name}_loss'] = per_head_losses[head_name] / num_batches

    # Compute metrics
    metrics_dict = compute_metrics(
        {k: paddle.concat(v, axis=0) for k, v in all_predictions.items()},
        {k: paddle.concat(v, axis=0) for k, v in all_targets.items()}
    )

    for head_name, head_metrics in metrics_dict.items():
        avg_metrics[f'{head_name}_accuracy'] = head_metrics['accuracy']
        avg_metrics[f'{head_name}_f1'] = head_metrics['f1']

    # Compute overall F1 score
    f1_scores = [metrics_dict[k]['f1'] for k in active_tasks if k in metrics_dict]
    if f1_scores:
        avg_metrics['macro_f1'] = float(np.mean(f1_scores))

    return avg_metrics


# ============================================================================
# Main Training Loop
# ============================================================================

def train_classification(args):
    """Main training function

    Args:
        args: Command line arguments
    """
    print("=" * 70)
    print("Multi-Task Tongue Classification Training")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  - Data root: {args.data_root}")
    print(f"  - Output dir: {args.output_dir}")
    print(f"  - Epochs: {args.epochs}")
    print(f"  - Batch size: {args.batch_size}")
    print(f"  - Learning rate: {args.lr}")
    print(f"  - GPU: {args.use_gpu}")
    print("=" * 70)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    best_model_dir = output_dir / "best_model"
    best_model_dir.mkdir(exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)

    # Setup transforms
    train_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

    val_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

    # Create datasets
    print("Loading datasets...")
    train_dataset = TongueClassificationDataset(
        image_dir=str(Path(args.data_root) / "train/images"),
        label_file=str(Path(args.data_root) / "train/labels.txt"),
        transform=train_transforms
    )

    val_dataset = TongueClassificationDataset(
        image_dir=str(Path(args.data_root) / "val/images"),
        label_file=str(Path(args.data_root) / "val/labels.txt"),
        transform=val_transforms
    )

    print(f"  - Train samples: {len(train_dataset)}")
    print(f"  - Val samples: {len(val_dataset)}")

    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,  # Windows compatibility
        drop_last=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        drop_last=False
    )

    # Create model
    print("Creating model...")
    model = create_multi_head_model(
        backbone_name="PP-HGNetV2-B4",
        pretrained=True
    )

    # Print model info
    total_params = sum(p.numel().item() for p in model.parameters())
    trainable_params = sum(p.numel().item() for p in model.parameters() if not p.stop_gradient)
    print(f"  - Total parameters: {total_params:,}")
    print(f"  - Trainable parameters: {trainable_params:,}")

    # Create loss function
    print("Creating loss function...")
    criterion = create_multi_task_loss_from_config(
        class_weights_path=str(Path(args.data_root) / "class_weights.json")
    )

    # Create optimizer
    optimizer = paddle.optimizer.AdamW(
        parameters=model.parameters(),
        learning_rate=args.lr,
        weight_decay=0.0001,
        grad_clip=nn.ClipGradByNorm(clip_norm=1.0)
    )

    # Create scheduler
    scheduler = CosineAnnealingWarmRestarts(
        max_lr=args.lr,
        min_lr=1e-6,
        T_0=10,
        T_mult=2
    )

    # Create augmentation
    cutmix = CutMix(alpha=1.0, prob=0.2)
    mixup = MixUp(alpha=0.2, prob=0.1)

    # Create curriculum config
    curriculum_config = CurriculumTrainingConfig(
        total_epochs=args.epochs,
        warmup_epochs=args.warmup_epochs,
        main_task="tongue_color",
        accumulate_steps=2,
        weight_strategy="linear_decay",
        class_weights_path=str(Path(args.data_root) / "class_weights.json")
    )

    # Create early stopping
    early_stopping = EarlyStopping(
        patience=10,
        min_delta=0.001,
        mode='max',
        verbose=True
    )

    # MLflow setup
    if MLFLOW_AVAILABLE and args.use_mlflow:
        mlflow.set_experiment("Tongue_Classification")
        mlflow.start_run()
        mlflow.log_params({
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "warmup_epochs": args.warmup_epochs,
            "cutmix_prob": 0.2,
            "mixup_prob": 0.1
        })

    # Training loop
    print("\nStarting training...")
    print("=" * 70)

    training_history = []
    best_score = 0.0

    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")
        print("-" * 70)

        # Get active tasks from curriculum scheduler
        active_tasks = curriculum_config.curriculum.get_active_tasks(epoch)
        print(f"Active tasks: {active_tasks}")

        # Train
        train_metrics = train_one_epoch(
            model=model,
            dataloader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
            scheduler=scheduler,
            cutmix=cutmix,
            mixup=mixup,
            curriculum_config=curriculum_config,
            epoch=epoch,
            active_tasks=active_tasks,
            gradient_accumulation_steps=2
        )

        # Validate
        val_metrics = validate(
            model=model,
            dataloader=val_loader,
            criterion=criterion,
            active_tasks=active_tasks
        )

        # Combine metrics
        epoch_metrics = {**train_metrics, **val_metrics}
        epoch_metrics['epoch'] = epoch + 1
        training_history.append(epoch_metrics)

        # Print metrics
        print(f"\nEpoch {epoch + 1} Summary:")
        print(f"  Train Loss: {train_metrics['total_loss']:.4f}")
        print(f"  Val Loss: {val_metrics['val_loss']:.4f}")
        print(f"  Macro F1: {val_metrics.get('macro_f1', 0):.4f}")
        for head in active_tasks:
            if f'{head}_accuracy' in val_metrics:
                print(f"  {head} Acc: {val_metrics[f'{head}_accuracy']:.4f}, "
                      f"F1: {val_metrics[f'{head}_f1']:.4f}")

        # Log to MLflow
        if MLFLOW_AVAILABLE and args.use_mlflow:
            mlflow.log_metrics(epoch_metrics, step=epoch + 1)

        # Save checkpoint
        if (epoch + 1) % args.save_freq == 0:
            checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch + 1}.pdparams"
            paddle.save(model.state_dict(), str(checkpoint_path))
            print(f"Saved checkpoint: {checkpoint_path}")

        # Check for best model
        current_score = val_metrics.get('macro_f1', 0.0)
        if current_score > best_score:
            best_score = current_score
            best_model_path = best_model_dir / "best_model.pdparams"
            paddle.save(model.state_dict(), str(best_model_path))
            print(f"Saved best model (F1: {best_score:.4f})")

        # Early stopping check
        if early_stopping(epoch, current_score):
            print(f"Early stopping at epoch {epoch + 1}")
            break

    print("\n" + "=" * 70)
    print("Training completed!")
    print("=" * 70)
    print(f"Best macro F1: {best_score:.4f}")
    print(f"Best epoch: {early_stopping.best_epoch + 1}")

    # Save training history
    history_path = output_dir / "training_history.json"
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(training_history, f, indent=2, ensure_ascii=False)
    print(f"Training history saved to: {history_path}")

    # Save final model
    final_model_path = output_dir / "final_model.pdparams"
    paddle.save(model.state_dict(), str(final_model_path))
    print(f"Final model saved to: {final_model_path}")

    if MLFLOW_AVAILABLE and args.use_mlflow:
        mlflow.log_metric("best_macro_f1", best_score)
        mlflow.log_artifact(str(best_model_dir))
        mlflow.end_run()

    return best_score


# ============================================================================
# Command Line Interface
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Train multi-task tongue classification model"
    )

    parser.add_argument(
        "--data-root",
        type=str,
        default="datasets/processed/clas_v1",
        help="Path to dataset root directory"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/paddle_clas/output",
        help="Path to output directory"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=60,
        help="Number of training epochs (default: 60)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Batch size for training (default: 16)"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.001,
        help="Initial learning rate (default: 0.001)"
    )
    parser.add_argument(
        "--warmup-epochs",
        type=int,
        default=20,
        help="Number of warmup epochs for curriculum learning (default: 20)"
    )
    parser.add_argument(
        "--save-freq",
        type=int,
        default=10,
        help="Save checkpoint every N epochs (default: 10)"
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Path to checkpoint to resume from"
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="Use GPU for training"
    )
    parser.add_argument(
        "--use-mlflow",
        action="store_true",
        help="Enable MLflow logging"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train_classification(args)
