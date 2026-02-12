#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tongue Segmentation Training Script

Core training script for tongue segmentation using BiSeNetV2 with:
- Combined Loss (CrossEntropy + Dice + Boundary)
- Warmup + PolyLR learning rate schedule
- Early stopping (patience=10)
- MLflow experiment tracking

task-2-3: 核心训练（80 epochs + 早停）

Usage:
    # Full training (80 epochs with early stopping)
    python train_segmentation.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml

    # Quick test (5 epochs)
    python train_segmentation.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml --epochs 5

    # Resume from checkpoint
    python train_segmentation.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml --resume output/checkpoints/checkpoint_epoch_10.pdparams
"""

import os
import sys
from pathlib import Path
import argparse
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import yaml
import numpy as np
from PIL import Image
from tqdm import tqdm

try:
    import paddle
    import paddle.nn as nn
    import paddle.nn.functional as F
    from paddle.io import Dataset, DataLoader
    PADDLE_AVAILABLE = True
except ImportError as e:
    PADDLE_AVAILABLE = False
    print(f"Warning: PaddlePaddle not available: {e}")

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# Learning Rate Scheduler
# ============================================================

class WarmupPolyLR:
    """
    Warmup + Polynomial Decay Learning Rate Scheduler.

    Combines linear warmup with polynomial decay for stable training.
    """

    def __init__(
        self,
        base_lr: float,
        warmup_epochs: int,
        total_epochs: int,
        warmup_start_lr: float = 1e-6,
        min_lr: float = 1e-6,
        power: float = 0.9
    ):
        self.base_lr = base_lr
        self.warmup_epochs = warmup_epochs
        self.total_epochs = total_epochs
        self.warmup_start_lr = warmup_start_lr
        self.min_lr = min_lr
        self.power = power

        self.current_epoch = 0
        self.current_lr = warmup_start_lr

    def step(self, epoch: int = None) -> float:
        """Update learning rate."""
        if epoch is not None:
            self.current_epoch = epoch

        if self.current_epoch < self.warmup_epochs:
            # Warmup phase: linear increase
            alpha = self.current_epoch / max(1, self.warmup_epochs)
            self.current_lr = self.warmup_start_lr + (self.base_lr - self.warmup_start_lr) * alpha
        else:
            # Polynomial decay phase
            progress = (self.current_epoch - self.warmup_epochs) / max(1, self.total_epochs - self.warmup_epochs)
            self.current_lr = self.min_lr + (self.base_lr - self.min_lr) * max(0, (1 - progress) ** self.power)

        return self.current_lr

    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.current_lr


# ============================================================
# Early Stopping
# ============================================================

class EarlyStopping:
    """
    Early stopping utility to stop training when validation metric stops improving.
    """

    def __init__(
        self,
        patience: int = 10,
        min_delta: float = 0.001,
        monitor: str = 'val_miou',
        mode: str = 'max',
        verbose: bool = True
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.monitor = monitor
        self.mode = mode
        self.verbose = verbose

        self.best_score = None
        self.counter = 0
        self.best_epoch = 0
        self.early_stop = False

        if mode == 'max':
            self.is_better = lambda new, best: new > best + min_delta
        else:
            self.is_better = lambda new, best: new < best - min_delta

    def __call__(self, current_score: float, epoch: int) -> bool:
        """Check if training should stop."""
        if self.best_score is None:
            self.best_score = current_score
            self.best_epoch = epoch
            return False

        if self.is_better(current_score, self.best_score):
            if self.verbose:
                logger.info(f"{self.monitor} improved from {self.best_score:.4f} to {current_score:.4f}")
            self.best_score = current_score
            self.best_epoch = epoch
            self.counter = 0
        else:
            self.counter += 1
            if self.verbose:
                logger.info(f"{self.monitor} did not improve. {self.counter}/{self.patience} epochs without improvement.")

            if self.counter >= self.patience:
                self.early_stop = True
                if self.verbose:
                    logger.info(f"Early stopping triggered! Best {self.monitor}: {self.best_score:.4f} at epoch {self.best_epoch}")
                return True

        return False


# ============================================================
# Metrics Calculator
# ============================================================

class SegmentationMetrics:
    """Calculator for segmentation metrics."""

    def __init__(self, num_classes: int = 2, ignore_index: int = 255):
        self.num_classes = num_classes
        self.ignore_index = ignore_index
        self.reset()

    def reset(self):
        self.intersection = np.zeros(self.num_classes, dtype=np.float64)
        self.union = np.zeros(self.num_classes, dtype=np.float64)
        self.total_seen = 0
        self.total_correct = 0

    def update(self, pred: np.ndarray, target: np.ndarray):
        pred_flat = pred.flatten()
        target_flat = target.flatten()

        valid_mask = target_flat != self.ignore_index
        pred_flat = pred_flat[valid_mask]
        target_flat = target_flat[valid_mask]

        for cls in range(self.num_classes):
            pred_cls = (pred_flat == cls)
            target_cls = (target_flat == cls)

            self.intersection[cls] += (pred_cls & target_cls).sum()
            self.union[cls] += (pred_cls | target_cls).sum()

        self.total_correct += (pred_flat == target_flat).sum()
        self.total_seen += len(pred_flat)

    def compute(self) -> Dict[str, float]:
        union_safe = np.where(self.union > 0, self.union, 1)
        iou_per_class = self.intersection / union_safe
        miou = np.mean(iou_per_class)

        dice_per_class = 2 * self.intersection / (self.union + self.intersection + 1e-5)
        dice = np.mean(dice_per_class)

        accuracy = self.total_correct / max(self.total_seen, 1)

        return {
            'miou': float(miou),
            'dice': float(dice),
            'accuracy': float(accuracy),
        }

    def compute_boundary_metrics(self, pred, target) -> Dict[str, float]:
        """
        Compute boundary F1, precision, and recall.

        This method is called by evaluate.py for comprehensive boundary evaluation.

        Args:
            pred: Predictions tensor of shape (N, H, W) or numpy array
            target: Ground truth tensor of shape (N, H, W) or numpy array

        Returns:
            Dictionary with boundary_f1, boundary_precision, boundary_recall
        """
        # Convert to numpy if needed
        if paddle.is_tensor(pred):
            pred = pred.numpy()
        if paddle.is_tensor(target):
            target = target.numpy()

        try:
            from scipy import ndimage
        except ImportError:
            # If scipy not available, return placeholder values
            logger.warning("scipy not available, returning placeholder boundary metrics")
            return {
                'boundary_f1': 0.0,
                'boundary_precision': 0.0,
                'boundary_recall': 0.0,
            }

        boundary_tp = 0
        boundary_fp = 0
        boundary_fn = 0
        struct_elem = np.ones((3, 3), dtype=np.uint8)

        for i in range(len(pred)):
            pred_mask = pred[i]
            target_mask = target[i]

            # Handle ignore index
            valid_mask = (target_mask != self.ignore_index)

            # Extract boundaries using morphological gradient
            pred_boundaries = self._extract_boundary(pred_mask, struct_elem, valid_mask)
            target_boundaries = self._extract_boundary(target_mask, struct_elem, valid_mask)

            # Compute TP, FP, FN for boundaries
            boundary_tp += ((pred_boundaries == 1) & (target_boundaries == 1)).sum()
            boundary_fp += ((pred_boundaries == 1) & (target_boundaries == 0)).sum()
            boundary_fn += ((pred_boundaries == 0) & (target_boundaries == 1)).sum()

        # Compute metrics
        boundary_precision = boundary_tp / max(boundary_tp + boundary_fp, 1e-5)
        boundary_recall = boundary_tp / max(boundary_tp + boundary_fn, 1e-5)
        boundary_f1 = 2 * boundary_precision * boundary_recall / max(boundary_precision + boundary_recall, 1e-5)

        return {
            'boundary_f1': float(boundary_f1),
            'boundary_precision': float(boundary_precision),
            'boundary_recall': float(boundary_recall),
        }

    def _extract_boundary(self, mask: np.ndarray, struct_elem: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
        """Extract boundary pixels using morphological operations."""
        # Clean mask for boundary extraction
        mask_clean = np.where(valid_mask, mask, 0)

        # Dilated and eroded versions
        dilated = ndimage.binary_dilation(mask_clean.astype(np.uint8), structure=struct_elem)
        eroded = ndimage.binary_erosion(mask_clean.astype(np.uint8), structure=struct_elem)

        # Boundary = dilated - eroded
        boundaries = (dilated.astype(np.int8) - eroded.astype(np.int8)).astype(np.uint8)

        # Focus on foreground (tongue) boundaries only
        return boundaries & (mask_clean > 0).astype(np.uint8)


# ============================================================
# Dataset
# ============================================================

class TongueSegmentationDataset(Dataset):
    """Tongue segmentation dataset with augmentation."""

    def __init__(
        self,
        images_dir: str,
        masks_dir: str,
        image_size: Tuple[int, int] = (512, 512),
        is_training: bool = True
    ):
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.image_size = image_size
        self.is_training = is_training

        self.images = sorted([f for f in os.listdir(images_dir)
                           if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        if len(self.images) == 0:
            logger.warning(f"No images found in {images_dir}")

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_name = self.images[idx]

        img_path = self.images_dir / img_name
        mask_name = img_name.rsplit('.', 1)[0] + '.png'
        mask_path = self.masks_dir / mask_name

        try:
            image = Image.open(img_path).convert('RGB')
            mask = Image.open(mask_path).convert('L')

            image_np = np.array(image)
            mask_np = np.array(mask)

            # Simple resize
            image = image.resize((self.image_size[1], self.image_size[0]), Image.BILINEAR)
            mask = mask.resize((self.image_size[1], self.image_size[0]), Image.NEAREST)
            image_np = np.array(image)
            mask_np = np.array(mask)

            # Normalize
            image_np = image_np.astype(np.float32) / 255.0
            image_np = (image_np - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])

            # Convert mask to binary (0=background, 1=tongue)
            mask_np = (mask_np > 127).astype(np.int64)

            # Transpose to (C, H, W)
            image_np = image_np.transpose(2, 0, 1).astype(np.float32)

            return image_np, mask_np

        except Exception as e:
            logger.error(f"Error loading {img_name}: {e}")
            image_np = np.zeros((3, self.image_size[0], self.image_size[1]), dtype=np.float32)
            mask_np = np.zeros((self.image_size[0], self.image_size[1]), dtype=np.int64)
            return image_np, mask_np


# ============================================================
# Import model and loss from existing modules
# ============================================================

class SimpleUNet(nn.Layer):
    """Simple UNet as fallback model."""
    def __init__(self, num_classes=2):
        super().__init__()

        # Encoder
        self.enc1 = nn.Sequential(
            nn.Conv2D(3, 64, 3, padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU()
        )
        self.pool1 = nn.MaxPool2D(2, 2)

        self.enc2 = nn.Sequential(
            nn.Conv2D(64, 128, 3, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU()
        )
        self.pool2 = nn.MaxPool2D(2, 2)

        self.enc3 = nn.Sequential(
            nn.Conv2D(128, 256, 3, padding=1),
            nn.BatchNorm2D(256),
            nn.ReLU()
        )
        self.pool3 = nn.MaxPool2D(2, 2)

        self.bottleneck = nn.Sequential(
            nn.Conv2D(256, 512, 3, padding=1),
            nn.BatchNorm2D(512),
            nn.ReLU()
        )

        # Decoder
        self.up3 = nn.Sequential(
            nn.Conv2DTranspose(512, 256, 2, stride=2, padding=1),
            nn.BatchNorm2D(256),
            nn.ReLU()
        )

        self.up2 = nn.Sequential(
            nn.Conv2DTranspose(256, 128, 2, stride=2, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU()
        )

        self.up1 = nn.Sequential(
            nn.Conv2DTranspose(128, 64, 2, stride=2, padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU()
        )

        self.dec3 = nn.Sequential(
            nn.Conv2D(512, 256, 3, padding=1),
            nn.BatchNorm2D(256),
            nn.ReLU()
        )

        self.dec2 = nn.Sequential(
            nn.Conv2D(256, 128, 3, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU()
        )

        self.dec1 = nn.Sequential(
            nn.Conv2D(128, 64, 3, padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU()
        )

        self.final = nn.Conv2D(64, num_classes, 1)

    def forward(self, x):
        # Encoder
        e1 = self.enc1(x)
        p1 = self.pool1(e1)
        e2 = self.enc2(p1)
        p2 = self.pool2(e2)
        e3 = self.enc3(p2)
        p3 = self.pool3(e3)
        b = self.bottleneck(p3)

        # Decoder
        d3 = self.up3(b)
        d3 = paddle.concat([d3, e3], axis=1)
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        d2 = paddle.concat([d2, e2], axis=1)
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        d1 = paddle.concat([d1, e1], axis=1)
        d1 = self.dec1(d1)

        out = self.final(d1)
        return out


def create_model(config: Dict) -> nn.Layer:
    """Create model from config."""
    try:
        from models.paddle_seg.models.bisenetv2 import BiSeNetV2

        model_config = config['model']
        model = BiSeNetV2(
            num_classes=model_config['architecture']['num_classes'],
            in_channels=model_config['architecture']['in_channels'],
            attention=model_config['architecture'].get('attention', True),
        )
        logger.info(f"Using BiSeNetV2 model")
        return model
    except Exception as e:
        logger.warning(f"BiSeNetV2 creation failed: {e}, falling back to SimpleUNet")
        model = SimpleUNet(num_classes=config['model']['architecture']['num_classes'])
        logger.info(f"Using SimpleUNet fallback model")
        return model


def create_loss(config: Dict):
    """Create combined loss function."""
    from models.paddle_seg.losses.combined_loss import CombinedLoss, calculate_class_weights_from_dataset

    loss_config = config['loss']

    class_weights = None
    if loss_config['ce_loss'].get('use_class_weights', False):
        class_weights = calculate_class_weights_from_dataset(
            config['dataset']['train']['masks'],
            num_classes=config['model']['architecture']['num_classes']
        )

    criterion = CombinedLoss(
        num_classes=config['model']['architecture']['num_classes'],
        ce_weight=loss_config['ce_loss']['weight'],
        dice_weight=loss_config['dice_loss']['weight'],
        boundary_weight=loss_config['boundary_loss']['weight'],
        class_weights=class_weights,
        ignore_index=loss_config['ce_loss']['ignore_index'],
        boundary_theta=loss_config['boundary_loss'].get('theta', 3),
    )

    return criterion


# ============================================================
# Trainer
# ============================================================

class TongueSegmentationTrainer:
    """Trainer for tongue segmentation."""

    def __init__(self, config: Dict):
        self.config = config
        self.device = 'gpu:0' if paddle.is_compiled_with_cuda() else 'cpu'

        logger.info(f"Using device: {self.device}")

        # Setup paths
        self.output_dir = Path(config['checkpoint']['output_dir'])
        self.save_dir = self.output_dir / config['checkpoint']['save_dir']
        self.checkpoint_dir = self.output_dir / config['checkpoint']['checkpoint_dir']

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Training settings
        self.num_epochs = config['training']['num_epochs']
        self.batch_size = config['training']['batch_size']

        # Create model
        self.model = create_model(config)

        # Setup loss
        self.criterion = create_loss(config)

        # Setup optimizer
        self.optimizer = self._create_optimizer()

        # Learning rate scheduler
        self.lr_scheduler = WarmupPolyLR(
            base_lr=config['training']['learning_rate']['base_lr'],
            warmup_epochs=config['training']['warmup_epochs'],
            total_epochs=self.num_epochs,
            warmup_start_lr=config['training']['warmup_start_lr'],
            min_lr=config['training']['learning_rate']['min_lr'],
            power=config['training']['learning_rate']['power'],
        )

        # Early stopping
        early_stop_config = config.get('early_stopping', {})
        self.early_stopping = EarlyStopping(
            patience=early_stop_config.get('patience', 10),
            min_delta=early_stop_config.get('min_delta', 0.001),
            monitor=early_stop_config.get('monitor', 'val_miou'),
            mode=early_stop_config.get('mode', 'max'),
        )

        # Metrics
        self.metrics_calculator = SegmentationMetrics(num_classes=2)

        # Training history
        self.history = {
            'train_loss': [],
            'train_ce_loss': [],
            'train_dice_loss': [],
            'train_boundary_loss': [],
            'val_loss': [],
            'val_miou': [],
            'val_dice': [],
            'val_f1': [],
            'lr': [],
        }

        # MLflow setup
        self._setup_mlflow()

    def _create_optimizer(self):
        opt_config = self.config['training']['optimizer']

        if opt_config['type'] == 'Momentum' or opt_config['type'] == 'SGD':
            return paddle.optimizer.Momentum(
                parameters=self.model.parameters(),
                learning_rate=self.lr_scheduler.base_lr,
                momentum=opt_config['momentum'],
                weight_decay=opt_config['weight_decay'],
            )
        elif opt_config['type'] == 'Adam':
            return paddle.optimizer.Adam(
                parameters=self.model.parameters(),
                learning_rate=self.lr_scheduler.base_lr,
                weight_decay=opt_config.get('weight_decay', 0),
            )
        else:
            raise ValueError(f"Unknown optimizer type: {opt_config['type']}")

    def _setup_mlflow(self):
        if MLFLOW_AVAILABLE and self.config.get('mlflow', {}).get('enabled', False):
            mlflow_config = self.config['mlflow']
            mlflow.set_tracking_uri(mlflow_config.get('tracking_uri', './mlruns'))
            mlflow.set_experiment(mlflow_config.get('experiment_name', 'tongue_segmentation'))

            run_name = mlflow_config.get('run_name') or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            mlflow.start_run(run_name=run_name)

            mlflow.log_params({
                'num_epochs': self.num_epochs,
                'batch_size': self.batch_size,
                'base_lr': self.config['training']['learning_rate']['base_lr'],
                'warmup_epochs': self.config['training']['warmup_epochs'],
            })

            self.mlflow_enabled = True
            logger.info(f"MLflow tracking enabled: {run_name}")
        else:
            self.mlflow_enabled = False

    def train_epoch(self, train_loader: DataLoader, epoch: int) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        self.metrics_calculator.reset()

        total_losses = {
            'loss': 0.0,
            'ce_loss': 0.0,
            'dice_loss': 0.0,
            'boundary_loss': 0.0,
        }
        num_batches = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{self.num_epochs}")

        for batch_idx, (images, masks) in enumerate(pbar):
            images = paddle.to_tensor(images)
            masks = paddle.to_tensor(masks)

            # Update learning rate
            current_lr = self.lr_scheduler.step(epoch=epoch)
            self.optimizer.set_lr(current_lr)

            # Forward pass
            outputs = self.model(images)

            # Calculate loss
            loss_dict = self.criterion(outputs, masks)

            # Backward pass
            loss_dict['loss'].backward()
            self.optimizer.step()
            self.optimizer.clear_grad()

            for key in total_losses:
                total_losses[key] += float(loss_dict[key].numpy())

            num_batches += 1

            pbar.set_postfix({
                'loss': f"{float(loss_dict['loss'].numpy()):.4f}",
                'lr': f"{current_lr:.2e}",
            })

        avg_losses = {k: v / max(num_batches, 1) for k, v in total_losses.items()}
        return avg_losses

    def validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate model."""
        self.model.eval()
        self.metrics_calculator.reset()

        total_loss = 0.0
        num_batches = 0

        with paddle.no_grad():
            for images, masks in val_loader:
                images = paddle.to_tensor(images)
                masks = paddle.to_tensor(masks)

                outputs = self.model(images)
                loss_dict = self.criterion(outputs, masks)
                total_loss += float(loss_dict['loss'].numpy())

                preds = outputs.argmax(axis=1).numpy()
                masks_np = masks.numpy()

                self.metrics_calculator.update(preds, masks_np)
                num_batches += 1

        metrics = self.metrics_calculator.compute()
        metrics['loss'] = total_loss / max(num_batches, 1)

        return metrics

    def save_checkpoint(self, epoch: int, is_best: bool = False):
        """Save checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'history': self.history,
            'config': self.config,
        }

        checkpoint_path = self.checkpoint_dir / f"checkpoint_epoch_{epoch}.pdparams"
        paddle.save(checkpoint, checkpoint_path)

        if is_best:
            best_path = self.save_dir / 'best_model.pdparams'
            paddle.save(checkpoint, best_path)
            logger.info(f"Best model saved to {best_path}")

    def train(self, train_loader: DataLoader, val_loader: DataLoader, resume_from: str = None):
        """Run full training loop."""
        start_epoch = 1
        if resume_from:
            checkpoint = paddle.load(resume_from)
            self.model.set_state_dict(checkpoint['model_state_dict'])
            self.optimizer.set_state_dict(checkpoint['optimizer_state_dict'])
            self.history = checkpoint.get('history', self.history)
            start_epoch = checkpoint['epoch'] + 1
            logger.info(f"Resumed from epoch {start_epoch}")

        best_miou = 0.0

        for epoch in range(start_epoch, self.num_epochs + 1):
            start_time = time.time()

            train_losses = self.train_epoch(train_loader, epoch)
            val_metrics = self.validate(val_loader)

            self.history['train_loss'].append(train_losses['loss'])
            self.history['train_ce_loss'].append(train_losses['ce_loss'])
            self.history['train_dice_loss'].append(train_losses['dice_loss'])
            self.history['train_boundary_loss'].append(train_losses['boundary_loss'])
            self.history['val_loss'].append(val_metrics['loss'])
            self.history['val_miou'].append(val_metrics['miou'])
            self.history['val_dice'].append(val_metrics['dice'])
            self.history['lr'].append(self.lr_scheduler.get_lr())

            epoch_time = time.time() - start_time

            logger.info(f"\n--- Epoch {epoch}/{self.num_epochs} ---")
            logger.info(f"Time: {epoch_time:.1f}s | LR: {self.lr_scheduler.get_lr():.2e}")
            logger.info(f"Train Loss: {train_losses['loss']:.4f}")
            logger.info(f"Val Loss: {val_metrics['loss']:.4f} | mIoU: {val_metrics['miou']:.4f} | Dice: {val_metrics['dice']:.4f}")

            if self.mlflow_enabled:
                mlflow.log_metrics({
                    'train_loss': train_losses['loss'],
                    'val_loss': val_metrics['loss'],
                    'val_miou': val_metrics['miou'],
                    'val_dice': val_metrics['dice'],
                }, step=epoch)

            is_best = val_metrics['miou'] > best_miou
            if is_best:
                best_miou = val_metrics['miou']

            if epoch % self.config['checkpoint']['save_freq'] == 0:
                self.save_checkpoint(epoch, is_best=is_best)
            elif is_best:
                self.save_checkpoint(epoch, is_best=True)

            if self.early_stopping(val_metrics['miou'], epoch):
                logger.info("Early stopping triggered.")
                break

        history_path = self.output_dir / 'training_history.json'
        with open(history_path, 'w') as f:
            json.dump(self.history, f, indent=2)

        if self.mlflow_enabled:
            mlflow.end_run()

        logger.info(f"\nTraining completed! Best mIoU: {best_miou:.4f}")
        logger.info(f"Best model saved to: {self.save_dir / 'best_model.pdparams'}")

        return self.history


def load_config(config_path: str) -> Dict:
    """Load YAML configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Tongue Segmentation Training")
    parser.add_argument("--config", type=str,
                       default="models/paddle_seg/configs/bisenetv2_stdc2.yml",
                       help="Path to config file")
    parser.add_argument("--epochs", type=int, default=None,
                       help="Override number of epochs")
    parser.add_argument("--batch-size", type=int, default=None,
                       help="Override batch size")
    parser.add_argument("--data-root", type=str, default="datasets/processed/seg_v1",
                       help="Path to dataset root")
    parser.add_argument("--resume", type=str, default=None,
                       help="Resume from checkpoint path")

    args = parser.parse_args()

    if not PADDLE_AVAILABLE:
        logger.error("PaddlePaddle is not available. Please install it first.")
        return 1

    logger.info(f"Loading config from: {args.config}")
    config = load_config(args.config)

    if args.epochs:
        config['training']['num_epochs'] = args.epochs
    if args.batch_size:
        config['training']['batch_size'] = args.batch_size

    base_path = Path(args.data_root)
    config['dataset']['train']['images'] = str(base_path / 'train/images')
    config['dataset']['train']['masks'] = str(base_path / 'train/masks')
    config['dataset']['val']['images'] = str(base_path / 'val/images')
    config['dataset']['val']['masks'] = str(base_path / 'val/masks')

    train_images = config['dataset']['train']['images']
    train_masks = config['dataset']['train']['masks']
    val_images = config['dataset']['val']['images']
    val_masks = config['dataset']['val']['masks']

    logger.info(f"Train images: {train_images}")
    logger.info(f"Train masks: {train_masks}")
    logger.info(f"Val images: {val_images}")
    logger.info(f"Val masks: {val_masks}")

    if not os.path.exists(train_images):
        logger.error(f"Train images path not found: {train_images}")
        logger.info("Please run mask conversion script first:")
        logger.info("  python datasets/tools/coco_to_mask.py")
        return 1

    image_size = tuple(config['dataset']['preprocessing']['image_size'])

    train_dataset = TongueSegmentationDataset(
        images_dir=train_images,
        masks_dir=train_masks,
        image_size=image_size,
        is_training=True,
    )
    val_dataset = TongueSegmentationDataset(
        images_dir=val_images,
        masks_dir=val_masks,
        image_size=image_size,
        is_training=False,
    )

    logger.info(f"Train samples: {len(train_dataset)}")
    logger.info(f"Val samples: {len(val_dataset)}")

    num_workers = config['training'].get('num_workers', 0)
    if sys.platform == 'win32':
        num_workers = 0

    train_loader = DataLoader(
        train_dataset,
        batch_size=config['training']['batch_size'],
        shuffle=True,
        num_workers=num_workers,
        drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config['training']['batch_size'],
        shuffle=False,
        num_workers=num_workers,
        drop_last=False,
    )

    trainer = TongueSegmentationTrainer(config)
    history = trainer.train(train_loader, val_loader, resume_from=args.resume)

    logger.info("\n" + "=" * 60)
    logger.info("TRAINING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Final Train Loss: {history['train_loss'][-1]:.4f}")
    logger.info(f"Final Val Loss: {history['val_loss'][-1]:.4f}")
    logger.info(f"Best Val mIoU: {max(history['val_miou']):.4f}")
    logger.info(f"Best Val Dice: {max(history['val_dice']):.4f}")

    final_miou = max(history['val_miou'])
    final_dice = max(history['val_dice'])

    success = True
    if final_miou < 0.90:
        logger.warning(f"Val mIoU {final_miou:.4f} < 0.90 target")
        success = False
    if final_dice < 0.95:
        logger.warning(f"Val Dice {final_dice:.4f} < 0.95 target")
        success = False

    if success:
        logger.info("✓ Acceptance criteria met!")
    else:
        logger.info("Note: Some targets not met. Consider:")
        logger.info("  - Increasing training epochs")
        logger.info("  - Adjusting loss weights")
        logger.info("  - Adding more data augmentation")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
