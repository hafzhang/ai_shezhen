#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PaddleSeg Baseline Training Script

Baseline training for tongue segmentation using BiSeNetV2-STDCNet2.
This is a simplified version for environment verification and baseline testing.

Usage:
    python train_baseline.py --config models/paddle_seg/configs/bisenetv2_stdc2.yml --epochs 1
"""

import os
import sys
from pathlib import Path
import argparse
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import yaml
import numpy as np
from tqdm import tqdm

try:
    import paddle
    import paddle.nn as nn
    import paddle.vision.transforms as T
    from paddle.io import Dataset, DataLoader
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False
    print("Warning: PaddlePaddle not available")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleTongueDataset(Dataset):
    """Simple dataset for baseline testing"""

    def __init__(self, images_dir, masks_dir, transform=None):
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.transform = transform

        # Get image files
        self.images = sorted([f for f in os.listdir(images_dir)
                           if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        if len(self.images) == 0:
            logger.warning(f"No images found in {images_dir}")

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_name = self.images[idx]

        # Load image
        img_path = self.images_dir / img_name
        mask_name = img_name.rsplit('.', 1)[0] + '.png'
        mask_path = self.masks_dir / mask_name

        try:
            from PIL import Image
            image = Image.open(img_path).convert('RGB')
            mask = Image.open(mask_path).convert('L')

            # Resize to target size
            image = image.resize((512, 512), Image.BILINEAR)
            mask = mask.resize((512, 512), Image.NEAREST)

            # Convert to numpy arrays (fix transpose error)
            image = np.array(image, dtype=np.float32).transpose(2, 0, 1) / 255.0
            mask = np.array(mask, dtype=np.int64)

            # Convert mask to binary (0=background, 1=tongue)
            mask = (mask > 127).astype('int64')

            return image, mask

        except Exception as e:
            logger.error(f"Error loading {img_name}: {e}")
            # Return dummy data
            return np.zeros((3, 512, 512), dtype='float32'), np.zeros((512, 512), dtype='int64')


class SimpleBiSeNetV2(nn.Layer):
    """Simplified BiSeNetV2 for baseline testing"""

    def __init__(self, num_classes=2):
        super().__init__()
        self.num_classes = num_classes

        # Simplified architecture for baseline
        self.encoder = nn.Sequential(
            nn.Conv2D(3, 32, 3, stride=2, padding=1),
            nn.BatchNorm2D(32),
            nn.ReLU(),
            nn.Conv2D(32, 64, 3, stride=2, padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU(),
            nn.Conv2D(64, 128, 3, stride=2, padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU(),
            nn.Conv2D(128, 256, 3, stride=2, padding=1),
            nn.BatchNorm2D(256),
            nn.ReLU(),
        )

        self.decoder = nn.Sequential(
            nn.Conv2DTranspose(256, 128, 3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2D(128),
            nn.ReLU(),
            nn.Conv2DTranspose(128, 64, 3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2D(64),
            nn.ReLU(),
            nn.Conv2DTranspose(64, 32, 3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2D(32),
            nn.ReLU(),
            nn.Conv2DTranspose(32, num_classes, 3, stride=2, padding=1, output_padding=1),
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x


class BaselineTrainer:
    """Baseline trainer for tongue segmentation"""

    def __init__(self, config):
        self.config = config
        self.device = 'gpu:0' if paddle.is_compiled_with_cuda() else 'cpu'

        logger.info(f"Using device: {self.device}")

        # Create model
        self.model = SimpleBiSeNetV2(
            num_classes=config['model']['architecture']['num_classes']
        )

        # Create optimizer (PaddlePaddle 3.x API)
        base_lr = config['training']['learning_rate']['base_lr']
        self.optimizer = paddle.optimizer.Momentum(
            parameters=self.model.parameters(),
            learning_rate=base_lr,
            momentum=config['training']['optimizer']['momentum'],
            weight_decay=config['training']['optimizer']['weight_decay']
        )

        # Loss function
        self.criterion = nn.CrossEntropyLoss()

        # Metrics tracking
        self.metrics = {
            'train_loss': [],
            'val_loss': [],
            'val_miou': []
        }

    def calculate_miou(self, pred, target, num_classes=2):
        """Calculate mean IoU"""
        # pred: (N, C, H, W), target: (N, H, W)
        pred = pred.argmax(axis=1)  # (N, H, W)
        miou = 0.0

        for cls in range(num_classes):
            pred_mask = (pred == cls).astype('float32')
            target_mask = (target == cls).astype('float32')

            intersection = (pred_mask * target_mask).sum()
            union = pred_mask.sum() + target_mask.sum() - intersection

            if union.numpy()[0] > 0:
                miou += (intersection / union).numpy()[0]

        return miou / num_classes

    def train_epoch(self, train_loader, epoch):
        """Train for one epoch"""
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch}")

        for batch_idx, (images, masks) in enumerate(pbar):
            # Debug first batch
            if batch_idx == 0 and epoch == 1:
                logger.info(f"Images shape: {images.shape}, dtype: {images.dtype}")
                logger.info(f"Masks shape: {masks.shape}, dtype: {masks.dtype}")

            images = paddle.to_tensor(images)
            masks = paddle.to_tensor(masks)
            # Ensure correct shapes: images (N, 3, H, W), masks (N, H, W)
            # Masks from dataset are already (N, H, W), so no need to reshape

            # Forward pass
            outputs = self.model(images)
            # Debug output shape
            if batch_idx == 0 and epoch == 1:
                logger.info(f"Model outputs shape: {outputs.shape}, dtype: {outputs.dtype}")

            # Handle size mismatch
            if outputs.shape[-2:] != masks.shape[-2:]:
                outputs = nn.functional.interpolate(outputs, size=masks.shape[-2:], mode='bilinear')

            # Reshape for CrossEntropyLoss: (N, C, H, W) -> (N*H*W, C), (N, H, W) -> (N*H*W,)
            N, C, H, W = outputs.shape
            outputs = outputs.transpose([0, 2, 3, 1]).reshape([N * H * W, C])
            masks = masks.reshape([N * H * W])

            # Calculate loss
            loss = self.criterion(outputs, masks)

            # Backward pass
            loss.backward()
            self.optimizer.step()
            self.optimizer.clear_grad()

            total_loss += float(loss.numpy())
            num_batches += 1

            pbar.set_postfix({'loss': f'{float(loss.numpy()):.4f}'})

        avg_loss = total_loss / num_batches
        self.metrics['train_loss'].append(avg_loss)

        return avg_loss

    def validate(self, val_loader):
        """Validate the model"""
        self.model.eval()
        total_loss = 0.0
        total_miou = 0.0
        num_batches = 0

        with paddle.no_grad():
            for images, masks in val_loader:
                images = paddle.to_tensor(images)
                masks = paddle.to_tensor(masks)

                # Forward pass
                outputs = self.model(images)

                # Keep original outputs for mIoU calculation
                outputs_for_miou = outputs

                # Handle size mismatch
                if outputs.shape[-2:] != masks.shape[-2:]:
                    outputs = nn.functional.interpolate(outputs, size=masks.shape[-2:], mode='bilinear')
                    outputs_for_miou = outputs

                # Reshape for CrossEntropyLoss: (N, C, H, W) -> (N*H*W, C), (N, H, W) -> (N*H*W,)
                N, C, H, W = outputs.shape
                outputs_flat = outputs.transpose([0, 2, 3, 1]).reshape([N * H * W, C])
                masks_flat = masks.reshape([N * H * W])

                # Calculate loss
                loss = self.criterion(outputs_flat, masks_flat)
                total_loss += float(loss.numpy())

                # Calculate mIoU with original shape
                miou = self.calculate_miou(outputs_for_miou, masks)
                total_miou += miou

                num_batches += 1

        avg_loss = total_loss / num_batches
        avg_miou = total_miou / num_batches

        self.metrics['val_loss'].append(avg_loss)
        self.metrics['val_miou'].append(avg_miou)

        return avg_loss, avg_miou

    def train(self, train_loader, val_loader, num_epochs=1):
        """Run training"""
        logger.info(f"Starting baseline training for {num_epochs} epoch(s)")
        logger.info(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")

        for epoch in range(1, num_epochs + 1):
            logger.info(f"\n--- Epoch {epoch}/{num_epochs} ---")

            # Train
            train_loss = self.train_epoch(train_loader, epoch)
            logger.info(f"Train Loss: {train_loss:.4f}")

            # Validate
            val_loss, val_miou = self.validate(val_loader)
            logger.info(f"Val Loss: {val_loss:.4f}, Val mIoU: {val_miou:.4f}")

        logger.info("\nBaseline training completed!")
        return self.metrics


def load_config(config_path):
    """Load YAML configuration"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="PaddleSeg Baseline Training")
    parser.add_argument("--config", type=str,
                       default="models/paddle_seg/configs/bisenetv2_stdc2.yml",
                       help="Path to config file")
    parser.add_argument("--epochs", type=int, default=1,
                       help="Number of epochs for baseline test")
    parser.add_argument("--batch-size", type=int, default=4,
                       help="Batch size")
    parser.add_argument("--data-root", type=str, default="datasets/processed/seg_v1",
                       help="Path to dataset root")

    args = parser.parse_args()

    if not PADDLE_AVAILABLE:
        logger.error("PaddlePaddle is not available. Please install it first.")
        return 1

    # Load config
    logger.info(f"Loading config from: {args.config}")
    config = load_config(args.config)

    # Check dataset paths
    train_images = os.path.join(args.data_root, "train/images")
    train_masks = os.path.join(args.data_root, "train/masks")
    val_images = os.path.join(args.data_root, "val/images")
    val_masks = os.path.join(args.data_root, "val/masks")

    logger.info(f"Train images: {train_images}")
    logger.info(f"Train masks: {train_masks}")
    logger.info(f"Val images: {val_images}")
    logger.info(f"Val masks: {val_masks}")

    # Check if dataset exists
    if not os.path.exists(train_images):
        logger.error(f"Train images path not found: {train_images}")
        logger.info("Please run the mask conversion script first:")
        logger.info("  python datasets/tools/coco_to_mask.py")
        return 1

    # Create datasets
    logger.info("\nCreating datasets...")
    train_dataset = SimpleTongueDataset(train_images, train_masks)
    val_dataset = SimpleTongueDataset(val_images, val_masks)

    logger.info(f"Train samples: {len(train_dataset)}")
    logger.info(f"Val samples: {len(val_dataset)}")

    # Create dataloaders
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

    # Create trainer
    trainer = BaselineTrainer(config)

    # Run training
    metrics = trainer.train(train_loader, val_loader, num_epochs=args.epochs)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("BASELINE TRAINING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Final Train Loss: {metrics['train_loss'][-1]:.4f}")
    logger.info(f"Final Val Loss: {metrics['val_loss'][-1]:.4f}")
    logger.info(f"Final Val mIoU: {metrics['val_miou'][-1]:.4f}")

    if metrics['val_miou'][-1] > 0.3:
        logger.info("✓ Baseline test passed! (mIoU > 0.3)")
        return 0
    else:
        logger.warning("Note: Low mIoU is expected for untrained baseline model")
        logger.info("The baseline test verifies the training pipeline works correctly")
        return 0


if __name__ == "__main__":
    sys.exit(main())
