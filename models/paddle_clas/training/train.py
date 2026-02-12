#!/usr/bin/env python
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
# We don't wrap stdout/stderr at module level as it causes issues with imports

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
        label_file: Path to label file (filename\tlabels)
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
                parts = line.split('\t')
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
# Data Augmentation (CutMix & MixUp)
# ============================================================================

def cutmix_data(
    images: paddle.Tensor,
    targets: Dict[str, paddle.Tensor],
    alpha: float = 1.0
) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor], paddle.Tensor]:
    """Apply CutMix augmentation

    Args:
        images: Batch of images (N, C, H, W)
        targets: Dictionary of targets
        alpha: CutMix mixing coefficient

    Returns:
        Mixed images, targets, lambda values
    """
    batch_size = images.shape[0]
    if alpha == 0:
        return images, targets, paddle.ones([batch_size])

    # Generate lambda from Beta distribution
    lam = np.random.beta(alpha, alpha)

    # Get shuffle index
    index = paddle.randperm(batch_size)

    # Get bounding box
    h, w = images.shape[2], images.shape[3]
    cut_rat = np.sqrt(1.0 - lam)
    cut_w = int(w * cut_rat)
    cut_h = int(h * cut_rat)

    # Uniform sampling
    cx = np.random.randint(w)
    cy = np.random.randint(h)

    bbx1 = np.clip(cx - cut_w // 2, 0, w)
    bby1 = np.clip(cy - cut_h // 2, 0, h)
    bbx2 = np.clip(cx + cut_w // 2, 0, w)
    bby2 = np.clip(cy + cut_h // 2, 0, h)

    # Create mixed images
    mixed_images = images.clone()
    mixed_images[:, :, bby1:bby2, bbx1:bbx2] = images[index, :, bby1:bby2, bbx1:bbx2]

    # Adjust lambda based on actual box area
    lam = 1 - ((bbx2 - bbx1) * (bby2 - bby1) / (w * h))
    lam = paddle.to_tensor(lam).reshape([1])

    return mixed_images, targets, lam


def mixup_data(
    images: paddle.Tensor,
    targets: Dict[str, paddle.Tensor],
    alpha: float = 0.2
) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor], paddle.Tensor]:
    """Apply MixUp augmentation

    Args:
        images: Batch of images (N, C, H, W)
        targets: Dictionary of targets
        alpha: MixUp mixing coefficient

    Returns:
        Mixed images, targets, lambda values
    """
    batch_size = images.shape[0]
    if alpha == 0:
        return images, targets, paddle.ones([batch_size])

    # Generate lambda from Beta distribution
    lam = np.random.beta(alpha, alpha)

    # Get shuffle index
    index = paddle.randperm(batch_size)

    # Mix images
    mixed_images = lam * images + (1 - lam) * images[index]
    lam = paddle.to_tensor(lam).reshape([1])

    return mixed_images, targets, lam


# ============================================================================
# Learning Rate Scheduler
# ============================================================================

class CosineAnnealingWarmRestarts:
    """Cosine annealing with warm restarts

    Args:
        T_0: Initial restart period
        T_mult: Period multiplication factor
        eta_min: Minimum learning rate
        last_epoch: Last epoch index
    """

    def __init__(
        self,
        base_lr: float,
        T_0: int,
        T_mult: int = 1,
        eta_min: float = 1e-6,
        last_epoch: int = -1
    ):
        self.base_lr = base_lr
        self.T_0 = T_0
        self.T_mult = T_mult
        self.eta_min = eta_min
        self.last_epoch = last_epoch
        self.current_period = T_0

    def get_lr(self, epoch: int) -> float:
        """Get learning rate for given epoch"""
        if epoch < 0:
            epoch = 0

        # Find which restart period we're in
        period = self.T_0
        epochs_in_period = epoch
        while epochs_in_period >= period:
            epochs_in_period -= period
            period *= self.T_mult

        # Cosine annealing within period
        lr = self.eta_min + (self.base_lr - self.eta_min) * (
            1 + np.cos(np.pi * epochs_in_period / period)
        ) / 2

        return lr

    def step(self, epoch: int) -> float:
        """Update learning rate for epoch"""
        lr = self.get_lr(epoch)
        self.last_epoch = epoch
        return lr


# ============================================================================
# Metrics Computation
# ============================================================================

def compute_metrics(
    predictions: Dict[str, paddle.Tensor],
    targets: Dict[str, paddle.Tensor],
    head_configs: Dict[str, Any]
) -> Dict[str, float]:
    """Compute evaluation metrics

    Args:
        predictions: Dictionary of head_name -> prediction logits
        targets: Dictionary of head_name -> target tensors
        head_configs: Configuration for each head

    Returns:
        Dictionary of metrics
    """
    metrics = {}
    all_f1_scores = []

    for head_name in head_configs.keys():
        if head_name not in predictions or head_name not in targets:
            continue

        pred = predictions[head_name]
        target = targets[head_name]

        # Get predictions
        if head_configs[head_name].multi_label:
            # Multi-label: apply sigmoid and threshold
            pred_labels = (F.sigmoid(pred) > 0.5).astype('int64')
        else:
            # Single-label: argmax
            pred_labels = pred.argmax(axis=-1).astype('int64')

        # Convert target to int64 if needed
        if target.dtype != paddle.int64:
            target = target.astype('int64')

        # Calculate per-class accuracy
        num_classes = head_configs[head_name].num_classes
        class_correct = []
        class_total = []

        for c in range(num_classes):
            mask = target == c
            if mask.sum() == 0:
                continue

            class_pred = pred_labels[mask]
            class_target = target[mask]
            correct = (class_pred == class_target).sum().item()
            total = mask.sum().item()

            class_correct.append(correct)
            class_total.append(total)

        # Average accuracy
        if sum(class_total) > 0:
            accuracy = sum(class_correct) / sum(class_total)
            metrics[f"{head_name}_accuracy"] = accuracy

        # Calculate F1 score
        from sklearn.metrics import f1_score
        target_np = target.numpy()
        pred_np = pred_labels.numpy()

        if head_configs[head_name].multi_label:
            f1 = f1_score(target_np, pred_np, average='macro', zero_division=0)
        else:
            f1 = f1_score(target_np, pred_np, average='macro', zero_division=0)

        metrics[f"{head_name}_f1"] = f1
        all_f1_scores.append(f1)

    # Compute macro and micro averages
    if all_f1_scores:
        metrics['macro_f1'] = np.mean(all_f1_scores)
        metrics['micro_f1'] = np.mean(all_f1_scores)

    return metrics


# ============================================================================
# Early Stopping
# ============================================================================

class EarlyStopping:
    """Early stopping for training

    Args:
        patience: Number of epochs to wait before stopping
        min_delta: Minimum change to qualify as improvement
        mode: 'min' or 'max'
        monitor: Metric to monitor
    """

    def __init__(
        self,
        patience: int = 10,
        min_delta: float = 0.001,
        mode: str = 'max',
        monitor: str = 'val_macro_f1'
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.monitor = monitor
        self.counter = 0
        self.best_score = None
        self.early_stop = False

    def __call__(self, metrics: Dict[str, float]) -> bool:
        """Check if should stop training

        Returns:
            True if should stop, False otherwise
        """
        current_score = metrics.get(self.monitor)

        if current_score is None:
            return False

        if self.best_score is None:
            self.best_score = current_score
            return False

        # Check if improved
        if self.mode == 'max':
            improved = current_score > self.best_score + self.min_delta
        else:
            improved = current_score < self.best_score - self.min_delta

        if improved:
            self.best_score = current_score
            self.counter = 0
        else:
            self.counter += 1

        if self.counter >= self.patience:
            self.early_stop = True

        return self.early_stop


# ============================================================================
# Main Training Loop
# ============================================================================

def train_one_epoch(
    model: nn.Layer,
    dataloader: DataLoader,
    criterion: MultiTaskLoss,
    optimizer: paddle.optimizer.Optimizer,
    scheduler: CosineAnnealingWarmRestarts,
    curriculum_config: CurriculumTrainingConfig,
    epoch: int,
    gradient_accumulator: GradientAccumulator,
    cutmix_prob: float = 0.2,
    mixup_prob: float = 0.1,
    amp_level: str = 'O1',
    grad_clip_max_norm: float = 1.0
) -> Dict[str, float]:
    """Train for one epoch

    Returns:
        Dictionary of training metrics
    """
    model.train()
    criterion.train()

    # Get curriculum state
    training_state = curriculum_config.get_training_state(epoch)
    active_tasks = training_state['curriculum']['active_tasks']
    task_weights = training_state['task_weights']

    # Update loss weights based on curriculum
    for task_name, weight in task_weights.items():
        criterion.set_task_weight(task_name, weight)

    epoch_loss = 0.0
    epoch_head_losses = {k: 0.0 for k in active_tasks}
    num_batches = 0

    for batch_idx, (images, targets) in enumerate(dataloader):
        # Get current learning rate
        lr = scheduler.get_lr(epoch)
        optimizer.set_lr(lr)

        # Apply CutMix/MixUp
        if np.random.random() < cutmix_prob:
            images, targets, lam = cutmix_data(images, targets, alpha=1.0)
        elif np.random.random() < mixup_prob:
            images, targets, lam = mixup_data(images, targets, alpha=0.2)
        else:
            lam = None

        with gradient_accumulator.accumulate():
            # Forward pass with only active tasks
            outputs = model(images, head_names=active_tasks)
            predictions = {
                task: outputs[i] for i, task in enumerate(active_tasks)
            }

            # Compute loss
            loss, head_losses = criterion(predictions, targets, head_names=active_tasks)

            # Scale loss for gradient accumulation
            loss = loss / gradient_accumulator.accumulate_steps

            # Backward pass
            if amp_level == 'O1':
                with paddle.amp.auto_cast():
                    scaler = paddle.amp.GradScaler()
                    scaler.scale(loss).backward()
            else:
                loss.backward()

            epoch_loss += loss.item() * gradient_accumulator.accumulate_steps
            for task, task_loss in head_losses.items():
                epoch_head_losses[task] += task_loss.item()

        # Optimizer step
        if gradient_accumulator.step():
            # Gradient clipping
            if grad_clip_max_norm > 0:
                paddle.nn.utils.clip_grad_norm_(
                    model.parameters(), grad_clip_max_norm
                )

            optimizer.step()
            optimizer.clear_grad()

        num_batches += 1

    # Compute average losses
    avg_loss = epoch_loss / num_batches
    avg_head_losses = {
        k: v / num_batches for k, v in epoch_head_losses.items()
    }

    return {
        'train_loss': avg_loss,
        'learning_rate': lr,
        **{f"train_{k}_loss": v for k, v in avg_head_losses.items()}
    }


def validate(
    model: nn.Layer,
    dataloader: DataLoader,
    criterion: MultiTaskLoss,
    epoch: int,
    active_tasks: List[str]
) -> Dict[str, float]:
    """Validate the model

    Returns:
        Dictionary of validation metrics
    """
    model.eval()
    criterion.eval()

    val_loss = 0.0
    all_predictions = {k: [] for k in active_tasks}
    all_targets = {k: [] for k in active_tasks}

    with paddle.no_grad():
        for images, targets in dataloader:
            # Forward pass
            outputs = model(images, head_names=active_tasks)
            predictions = {
                task: outputs[i] for i, task in enumerate(active_tasks)
            }

            # Compute loss
            loss, _ = criterion(predictions, targets, head_names=active_tasks)
            val_loss += loss.item()

            # Collect predictions and targets
            for task in active_tasks:
                all_predictions[task].append(predictions[task])
                all_targets[task].append(targets[task])

    # Concatenate all batches
    for task in active_tasks:
        all_predictions[task] = paddle.concat(all_predictions[task], axis=0)
        all_predictions[task] = paddle.concat(all_predictions[task], axis=0)

    # Compute metrics
    metrics = compute_metrics(all_predictions, all_targets, DEFAULT_HEAD_CONFIGS)
    metrics['val_loss'] = val_loss / len(dataloader)

    return metrics


def train(
    config: Dict[str, Any],
    resume_from: Optional[str] = None
) -> Dict[str, Any]:
    """Main training function

    Args:
        config: Training configuration dictionary
        resume_from: Path to checkpoint to resume from

    Returns:
        Training results dictionary
    """
    # Setup output directories
    output_dir = Path(config['output_dir'])
    checkpoint_dir = output_dir / 'checkpoints'
    best_model_dir = output_dir / 'best_model'
    log_dir = Path(config['log_dir'])

    for dir_path in [output_dir, checkpoint_dir, best_model_dir, log_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Initialize MLflow
    if MLFLOW_AVAILABLE and config.get('mlflow', {}).get('enabled', False):
        mlflow.set_tracking_uri(config['mlflow']['tracking_uri'])
        mlflow.set_experiment(config['mlflow']['experiment_name'])
        mlflow.start_run(run_name=config['mlflow'].get('run_name'))

        # Log parameters
        mlflow.log_params({
            'model': config['model']['name'],
            'batch_size': config['training']['batch_size'],
            'num_epochs': config['training']['num_epochs'],
            'learning_rate': config['training']['optimizer']['lr'],
            'accumulation_steps': config['training']['accumulation_steps']
        })

    # Create datasets
    print("Creating datasets...")
    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomCrop((224, 224)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.1),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

    val_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.CenterCrop((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

    train_dataset = TongueClassificationDataset(
        image_dir=config['data']['train_images'],
        label_file=config['data']['train_labels'],
        transform=train_transform
    )

    val_dataset = TongueClassificationDataset(
        image_dir=config['data']['val_images'],
        label_file=config['data']['val_labels'],
        transform=val_transform
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=config['training']['batch_size'],
        shuffle=True,
        num_workers=config['data'].get('num_workers', 4),
        drop_last=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config['training']['batch_size'],
        shuffle=False,
        num_workers=config['data'].get('num_workers', 4)
    )

    print(f"Train dataset: {len(train_dataset)} samples")
    print(f"Val dataset: {len(val_dataset)} samples")

    # Create model
    print("Creating model...")
    backbone = create_backbone(
        pretrained=config['pretrained'].get('weights_path'),
        num_classes=0
    )

    model = create_multi_head_model(
        backbone=backbone,
        head_configs=DEFAULT_HEAD_CONFIGS,
        dropout=config['model'].get('dropout', 0.2)
    )

    model_info = model.get_model_info()
    print(f"Model parameters: {model_info['total_parameters']:,}")

    # Create loss function
    criterion = create_multi_task_loss_from_config(
        class_weights_path=config['data'].get('class_weights')
    )

    # Create optimizer
    optimizer = paddle.optimizer.Momentum(
        parameters=model.parameters(),
        lr=config['training']['optimizer']['lr'],
        momentum=config['training']['optimizer']['momentum'],
        weight_decay=config['training']['optimizer']['weight_decay']
    )

    # Create learning rate scheduler
    scheduler_config = config['training']['scheduler']
    scheduler = CosineAnnealingWarmRestarts(
        base_lr=scheduler_config['warmup_start_lr'],
        T_0=scheduler_config['T_0'],
        T_mult=scheduler_config['T_mult'],
        eta_min=scheduler_config['min_lr']
    )

    # Create curriculum learning config
    curriculum_config = CurriculumTrainingConfig(
        total_epochs=config['training']['num_epochs'],
        warmup_epochs=20,
        accumulate_steps=config['training']['accumulation_steps'],
        class_weights_path=config['data'].get('class_weights')
    )

    # Create gradient accumulator
    gradient_accumulator = GradientAccumulator(
        accumulate_steps=config['training']['accumulation_steps']
    )

    # Create early stopping
    early_stopping = EarlyStopping(
        patience=config['training']['early_stopping']['patience'],
        min_delta=config['training']['early_stopping']['min_delta'],
        mode=config['training']['early_stopping']['mode'],
        monitor=config['training']['early_stopping']['monitor']
    )

    # Training loop
    num_epochs = config['training']['num_epochs']
    start_epoch = 0
    best_score = 0.0

    print(f"\nStarting training for {num_epochs} epochs...")
    print("=" * 60)

    training_history = []

    for epoch in range(start_epoch, num_epochs):
        epoch_start_time = time.time()

        # Train
        train_metrics = train_one_epoch(
            model=model,
            dataloader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
            scheduler=scheduler,
            curriculum_config=curriculum_config,
            epoch=epoch,
            gradient_accumulator=gradient_accumulator,
            cutmix_prob=0.2,
            mixup_prob=0.1,
            amp_level=config['training']['amp']['level'],
            grad_clip_max_norm=config['training']['grad_clip']['max_norm']
        )

        # Get active tasks for validation
        training_state = curriculum_config.get_training_state(epoch)
        active_tasks = training_state['curriculum']['active_tasks']

        # Validate
        val_metrics = validate(
            model=model,
            dataloader=val_loader,
            criterion=criterion,
            epoch=epoch,
            active_tasks=active_tasks
        )

        # Compute epoch time
        epoch_time = time.time() - epoch_start_time

        # Print metrics
        print(f"\nEpoch {epoch+1}/{num_epochs} ({epoch_time:.1f}s)")
        print(f"  Phase: {training_state['curriculum']['phase']}")
        print(f"  Active tasks: {len(active_tasks)}")
        print(f"  LR: {train_metrics['learning_rate']:.6f}")
        print(f"  Train Loss: {train_metrics['train_loss']:.4f}")
        print(f"  Val Loss: {val_metrics['val_loss']:.4f}")
        print(f"  Val Macro F1: {val_metrics.get('macro_f1', 0):.4f}")

        # Log to MLflow
        if MLFLOW_AVAILABLE and config.get('mlflow', {}).get('enabled', False):
            mlflow.log_metrics({
                **{f"train_{k}": v for k, v in train_metrics.items()},
                **{f"val_{k}": v for k, v in val_metrics.items()},
                'epoch': epoch + 1
            })

        # Save checkpoint
        if (epoch + 1) % config['output']['save_freq'] == 0:
            checkpoint_path = checkpoint_dir / f"checkpoint_epoch_{epoch+1}.pdparams"
            paddle.save(model.state_dict(), checkpoint_path)
            print(f"  Saved checkpoint: {checkpoint_path}")

        # Save best model
        current_score = val_metrics.get(config['training']['early_stopping']['monitor'], 0)
        if current_score > best_score:
            best_score = current_score
            best_model_path = best_model_dir / 'best_model.pdparams'
            paddle.save(model.state_dict(), best_model_path)
            print(f"  New best score: {best_score:.4f}")

        # Check early stopping
        if early_stopping(val_metrics):
            print(f"\nEarly stopping triggered at epoch {epoch+1}")
            break

        training_history.append({
            'epoch': epoch + 1,
            **train_metrics,
            **val_metrics
        })

    # Finalize
    print("\n" + "=" * 60)
    print("Training completed!")
    print(f"Best score: {best_score:.4f}")
    print(f"Total epochs: {epoch + 1}")

    # Save final training history
    history_path = output_dir / 'training_history.json'
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(training_history, f, indent=2, ensure_ascii=False)

    if MLFLOW_AVAILABLE and config.get('mlflow', {}).get('enabled', False):
        mlflow.end_run()

    return {
        'best_score': best_score,
        'total_epochs': epoch + 1,
        'training_history': training_history
    }


# ============================================================================
# Configuration Loader
# ============================================================================

def load_config(config_path: str) -> Dict[str, Any]:
    """Load training configuration from YAML file

    Args:
        config_path: Path to config YAML file

    Returns:
        Configuration dictionary
    """
    import yaml

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Update paths to be relative to project root
    project_root = Path(__file__).resolve().parents[3]

    if 'data' in config:
        for key in ['train_images', 'val_images', 'train_labels', 'val_labels']:
            if key in config['data']:
                path = config['data'][key]
                if not Path(path).is_absolute():
                    config['data'][key] = str(project_root / path)

    if 'pretrained' in config and 'weights_path' in config['pretrained']:
        path = config['pretrained']['weights_path']
        if not Path(path).is_absolute():
            config['pretrained']['weights_path'] = str(project_root / path)

    # Output directories
    config['output_dir'] = str(project_root / config['output']['checkpoint_dir']).replace('/checkpoints', '')
    config['log_dir'] = str(project_root / config['output']['log_dir'])

    return config


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train tongue classification model')
    parser.add_argument(
        '--config',
        type=str,
        default='models/paddle_clas/configs/pphgnetv2_b4.yml',
        help='Path to config file'
    )
    parser.add_argument(
        '--resume',
        type=str,
        default=None,
        help='Path to checkpoint to resume from'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Override output directory'
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    if args.output_dir:
        config['output_dir'] = args.output_dir

    # Print configuration
    print("=" * 60)
    print("Tongue Classification Training")
    print("=" * 60)
    print(f"Model: {config['model']['name']}")
    print(f"Epochs: {config['training']['num_epochs']}")
    print(f"Batch size: {config['training']['batch_size']}")
    print(f"Learning rate: {config['training']['optimizer']['lr']}")
    print(f"Accumulation steps: {config['training']['accumulation_steps']}")
    print("=" * 60)

    # Run training
    results = train(config, resume_from=args.resume)

    print("\nTraining results:")
    print(f"  Best score: {results['best_score']:.4f}")
    print(f"  Total epochs: {results['total_epochs']}")


if __name__ == "__main__":
    main()
