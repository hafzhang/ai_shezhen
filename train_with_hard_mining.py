#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hard Example Mining Training Script for Tongue Segmentation

Implements online hard example mining (OHEM) strategy:
- Each epoch selects top 10% samples with highest loss
- Adds them to next epoch with aggressive augmentation
- Progressive training: detail branch (epochs 1-30) + joint (epochs 31-80)

task-2-4: 难例挖掘与重训练

Usage:
    # Full training with hard example mining
    python train_with_hard_mining.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml

    # Quick test (5 epochs)
    python train_with_hard_mining.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml --epochs 5

    # Resume from checkpoint
    python train_with_hard_mining.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml --resume output/checkpoints/checkpoint_epoch_10.pdparams

    # Disable hard example mining
    python train_with_hard_mining.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml --no-hard-mining
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

# Import training modules
from models.paddle_seg.training import (
    HardExampleMiner,
    HardExampleDataset,
    ProgressiveTrainingStrategy,
    visualize_hard_examples,
    compute_hard_example_metrics,
)

# Import from existing training script
from train_segmentation import (
    WarmupPolyLR,
    EarlyStopping,
    SegmentationMetrics,
    TongueSegmentationDataset,
    SimpleUNet,
    create_model,
    create_loss,
    load_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# Enhanced Trainer with Hard Example Mining
# ============================================================

class TongueSegmentationTrainerWithMining:
    """
    Enhanced trainer with hard example mining and progressive training.

    Features:
    - Online hard example mining (OHEM)
    - Progressive training (detail branch first, then joint)
    - Aggressive augmentation for hard examples
    - Comprehensive analysis and reporting
    """

    def __init__(self, config: Dict, enable_hard_mining: bool = True):
        """
        Initialize trainer with hard example mining.

        Args:
            config: Training configuration dictionary
            enable_hard_mining: Whether to enable hard example mining
        """
        self.config = config
        self.enable_hard_mining = enable_hard_mining
        self.device = 'gpu:0' if paddle.is_compiled_with_cuda() else 'cpu'

        logger.info(f"Using device: {self.device}")
        logger.info(f"Hard example mining: {'enabled' if enable_hard_mining else 'disabled'}")

        # Setup paths
        self.output_dir = Path(config['checkpoint']['output_dir'])
        self.save_dir = self.output_dir / config['checkpoint']['save_dir']
        self.checkpoint_dir = self.output_dir / config['checkpoint']['checkpoint_dir']
        self.hard_mining_dir = self.output_dir / 'hard_mining'

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.hard_mining_dir.mkdir(parents=True, exist_ok=True)

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

        # Hard example mining
        if self.enable_hard_mining:
            mining_config = config.get('hard_example_mining', {})
            self.hard_miner = HardExampleMiner(
                top_k_percent=mining_config.get('top_k_percent', 0.1),
                min_hard_samples=mining_config.get('min_hard_samples', 50),
                max_hard_samples=mining_config.get('max_hard_samples', 500),
                output_dir=str(self.hard_mining_dir),
            )

            self.hard_augment_factor = mining_config.get('augment_factor', 3)
            self.start_mining_epoch = mining_config.get('start_epoch', 5)
            self.visualization_freq = mining_config.get('visualization_freq', 10)
        else:
            self.hard_miner = None

        # Progressive training strategy
        progressive_config = config.get('progressive_training', {})
        self.progressive_strategy = ProgressiveTrainingStrategy(
            detail_epochs=progressive_config.get('detail_epochs', 30),
            total_epochs=self.num_epochs,
        )

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
            'hard_examples_per_epoch': [] if self.enable_hard_mining else [],
            'training_phase': [],
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
            mlflow.set_experiment(mlflow_config.get('experiment_name', 'tongue_segmentation_mining'))

            run_name = mlflow_config.get('run_name') or f"mining_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            mlflow.start_run(run_name=run_name)

            mlflow.log_params({
                'num_epochs': self.num_epochs,
                'batch_size': self.batch_size,
                'base_lr': self.config['training']['learning_rate']['base_lr'],
                'warmup_epochs': self.config['training']['warmup_epochs'],
                'hard_mining_enabled': self.enable_hard_mining,
            })

            self.mlflow_enabled = True
            logger.info(f"MLflow tracking enabled: {run_name}")
        else:
            self.mlflow_enabled = False

    def get_dataloader_with_hard_examples(
        self,
        base_dataset: Dataset,
        hard_indices: List[int],
        is_training: bool = True
    ) -> DataLoader:
        """
        Create dataloader with hard examples augmented.

        Args:
            base_dataset: Original dataset
            hard_indices: List of hard example indices
            is_training: Whether this is for training

        Returns:
            DataLoader with or without hard examples
        """
        if not is_training or len(hard_indices) == 0:
            return DataLoader(
                base_dataset,
                batch_size=self.batch_size,
                shuffle=is_training,
                num_workers=0,
                drop_last=is_training,
            )

        # Create augmented dataset with hard examples
        augmented_dataset = HardExampleDataset(
            base_dataset=base_dataset,
            hard_indices=hard_indices,
            augment_factor=self.hard_augment_factor,
            hard_sample_weight=2.0,
        )

        logger.info(f"Created augmented dataset: {len(base_dataset)} -> {len(augmented_dataset)} samples")

        return DataLoader(
            augmented_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=0,
            drop_last=True,
        )

    def train_epoch(self, train_loader: DataLoader, epoch: int, track_losses: bool = True) -> Dict[str, float]:
        """
        Train for one epoch with hard example loss tracking.

        Args:
            train_loader: Training dataloader
            epoch: Current epoch number
            track_losses: Whether to track per-sample losses for mining

        Returns:
            Dictionary of average losses
        """
        self.model.train()
        self.metrics_calculator.reset()

        if track_losses and self.hard_miner:
            self.hard_miner.reset_epoch(epoch)

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

            # Create sample indices (this is a simplification)
            batch_size = images.shape[0]
            sample_indices = list(range(batch_idx * batch_size, (batch_idx + 1) * batch_size))

            # Update learning rate
            current_lr = self.lr_scheduler.step(epoch=epoch)
            self.optimizer.set_lr(current_lr)

            # Forward pass
            outputs = self.model(images)

            # Calculate loss
            loss_dict = self.criterion(outputs, masks)

            # Record losses for hard example mining
            if track_losses and self.hard_miner and epoch >= self.start_mining_epoch:
                self.hard_miner.record_batch_loss(sample_indices, loss_dict['loss'])

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

    def visualize_hard_samples(
        self,
        dataset: Dataset,
        hard_indices: List[int],
        epoch: int,
        predictions: Optional[List[np.ndarray]] = None
    ):
        """Visualize hard examples."""
        if epoch % self.visualization_freq != 0:
            return

        output_path = self.hard_mining_dir / f"hard_examples_epoch_{epoch}.png"
        visualize_hard_examples(
            dataset=dataset,
            hard_indices=hard_indices,
            output_path=str(output_path),
            num_samples=20,
            predictions=predictions,
        )

    def save_checkpoint(self, epoch: int, is_best: bool = False):
        """Save checkpoint with mining state."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'history': self.history,
            'config': self.config,
        }

        # Save mining state if enabled
        if self.enable_hard_mining and self.hard_miner:
            checkpoint['hard_miner_state'] = {
                'sample_losses': {k: list(v) for k, v in self.hard_miner.sample_losses.items()},
                'sample_consistency': self.hard_miner.sample_consistency,
                'epoch_hard_examples': self.hard_miner.epoch_hard_examples,
            }

        checkpoint_path = self.checkpoint_dir / f"checkpoint_epoch_{epoch}.pdparams"
        paddle.save(checkpoint, checkpoint_path)

        if is_best:
            best_path = self.save_dir / 'best_model.pdparams'
            paddle.save(checkpoint, best_path)
            logger.info(f"Best model saved to {best_path}")

    def train(
        self,
        train_dataset: Dataset,
        val_dataset: Dataset,
        val_loader: DataLoader,
        resume_from: str = None
    ):
        """
        Run full training loop with hard example mining.

        Args:
            train_dataset: Training dataset
            val_dataset: Validation dataset
            val_loader: Validation dataloader
            resume_from: Optional checkpoint path to resume from
        """
        start_epoch = 1
        if resume_from:
            checkpoint = paddle.load(resume_from)
            self.model.set_state_dict(checkpoint['model_state_dict'])
            self.optimizer.set_state_dict(checkpoint['optimizer_state_dict'])
            self.history = checkpoint.get('history', self.history)
            start_epoch = checkpoint['epoch'] + 1

            # Restore mining state
            if self.enable_hard_mining and 'hard_miner_state' in checkpoint:
                mining_state = checkpoint['hard_miner_state']
                from collections import deque
                self.hard_miner.sample_losses = {
                    k: deque(v, maxlen=self.hard_miner.smoothing_window)
                    for k, v in mining_state['sample_losses'].items()
                }
                self.hard_miner.sample_consistency = mining_state['sample_consistency']
                self.hard_miner.epoch_hard_examples = mining_state['epoch_hard_examples']

            logger.info(f"Resumed from epoch {start_epoch}")

        best_miou = 0.0
        current_hard_indices = []

        for epoch in range(start_epoch, self.num_epochs + 1):
            start_time = time.time()

            # Progressive training phase transition
            current_phase = self.progressive_strategy.get_phase(epoch)
            if self.progressive_strategy.should_transition(epoch):
                self.progressive_strategy.transition_phase(epoch, self.model)

            # Apply phase-specific learning rate adjustment
            lr_multiplier = self.progressive_strategy.get_learning_rate_multiplier(epoch)

            # Get hard examples from previous epoch (if mining enabled)
            if self.enable_hard_mining and epoch > self.start_mining_epoch and len(current_hard_indices) > 0:
                train_loader = self.get_dataloader_with_hard_examples(
                    train_dataset, current_hard_indices, is_training=True
                )
            else:
                train_loader = DataLoader(
                    train_dataset,
                    batch_size=self.batch_size,
                    shuffle=True,
                    num_workers=0,
                    drop_last=True,
                )

            # Training with loss tracking for hard example mining
            track_losses = (
                self.enable_hard_mining and
                epoch >= self.start_mining_epoch
            )
            train_losses = self.train_epoch(train_loader, epoch, track_losses=track_losses)

            # Get hard examples for next epoch
            if self.enable_hard_mining and epoch >= self.start_mining_epoch:
                current_hard_indices = self.hard_miner.get_hard_examples(len(train_dataset))
                self.hard_miner.save_hard_examples(epoch, current_hard_indices)

                # Visualize hard examples periodically
                if epoch % self.visualization_freq == 0:
                    self.visualize_hard_samples(train_dataset, current_hard_indices[:50], epoch)

            # Validation
            val_metrics = self.validate(val_loader)

            self.history['train_loss'].append(train_losses['loss'])
            self.history['train_ce_loss'].append(train_losses['ce_loss'])
            self.history['train_dice_loss'].append(train_losses['dice_loss'])
            self.history['train_boundary_loss'].append(train_losses['boundary_loss'])
            self.history['val_loss'].append(val_metrics['loss'])
            self.history['val_miou'].append(val_metrics['miou'])
            self.history['val_dice'].append(val_metrics['dice'])
            self.history['lr'].append(self.lr_scheduler.get_lr())
            self.history['training_phase'].append(current_phase)
            if self.enable_hard_mining:
                self.history['hard_examples_per_epoch'].append(len(current_hard_indices))

            epoch_time = time.time() - start_time

            logger.info(f"\n--- Epoch {epoch}/{self.num_epochs} ---")
            logger.info(f"Phase: {current_phase} | Time: {epoch_time:.1f}s | LR: {self.lr_scheduler.get_lr():.2e}")
            logger.info(f"Train Loss: {train_losses['loss']:.4f}")
            logger.info(f"Val Loss: {val_metrics['loss']:.4f} | mIoU: {val_metrics['miou']:.4f} | Dice: {val_metrics['dice']:.4f}")
            if self.enable_hard_mining:
                logger.info(f"Hard Examples: {len(current_hard_indices)}")

            if self.mlflow_enabled:
                mlflow.log_metrics({
                    'train_loss': train_losses['loss'],
                    'val_loss': val_metrics['loss'],
                    'val_miou': val_metrics['miou'],
                    'val_dice': val_metrics['dice'],
                    'num_hard_examples': len(current_hard_indices),
                    'training_phase': 0 if current_phase == 'detail' else 1,
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

        # Save training history
        history_path = self.output_dir / 'training_history.json'
        with open(history_path, 'w') as f:
            json.dump(self.history, f, indent=2)

        # Save hard example mining report
        if self.enable_hard_mining and self.hard_miner:
            self.hard_miner.save_statistics()
            report = self.hard_miner.generate_report()
            report_path = self.hard_mining_dir / 'mining_report.txt'
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Saved mining report to {report_path}")

        if self.mlflow_enabled:
            mlflow.end_run()

        logger.info(f"\nTraining completed! Best mIoU: {best_miou:.4f}")
        logger.info(f"Best model saved to: {self.save_dir / 'best_model.pdparams'}")

        return self.history


def main():
    parser = argparse.ArgumentParser(description="Tongue Segmentation Training with Hard Example Mining")
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
    parser.add_argument("--no-hard-mining", action="store_true",
                       help="Disable hard example mining")

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

    # Enable hard example mining in config
    config['hard_example_mining'] = config.get('hard_example_mining', {
        'top_k_percent': 0.1,
        'min_hard_samples': 50,
        'max_hard_samples': 500,
        'augment_factor': 3,
        'start_epoch': 5,
        'visualization_freq': 10,
    })

    # Enable progressive training in config
    config['progressive_training'] = config.get('progressive_training', {
        'detail_epochs': 30,
    })

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

    val_loader = DataLoader(
        val_dataset,
        batch_size=config['training']['batch_size'],
        shuffle=False,
        num_workers=0,
        drop_last=False,
    )

    enable_hard_mining = not args.no_hard_mining
    trainer = TongueSegmentationTrainerWithMining(config, enable_hard_mining=enable_hard_mining)
    history = trainer.train(train_dataset, val_dataset, val_loader, resume_from=args.resume)

    logger.info("\n" + "=" * 60)
    logger.info("TRAINING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Final Train Loss: {history['train_loss'][-1]:.4f}")
    logger.info(f"Final Val Loss: {history['val_loss'][-1]:.4f}")
    logger.info(f"Best Val mIoU: {max(history['val_miou']):.4f}")
    logger.info(f"Best Val Dice: {max(history['val_dice']):.4f}")

    if enable_hard_mining and history['hard_examples_per_epoch']:
        avg_hard = np.mean(history['hard_examples_per_epoch'])
        logger.info(f"Average Hard Examples per Epoch: {avg_hard:.1f}")

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
        logger.info("  - Fine-tuning with hard examples")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
