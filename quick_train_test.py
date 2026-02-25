#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速训练测试脚本

验证训练流程是否正常工作
"""

import sys
import yaml
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import paddle
from paddle.io import DataLoader
import paddle.vision.transforms as T

from src.data.dataset import TongueClassificationDataset, get_class_weights_from_distribution
from src.models.classification import MultiHeadClassificationModel, FocalLoss
from src.training.trainer import ClassificationTrainer, TrainerConfig

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_datasets(config: dict):
    """创建数据集"""
    base_path = config['dataset']['base_path']

    train_ann = f"{base_path}/train/annotations/train.json"
    val_ann = f"{base_path}/val/annotations/val.json"

    train_img_dir = f"{base_path}/train/images"
    val_img_dir = f"{base_path}/val/images"

    logger.info(f"Train annotations: {train_ann}")
    logger.info(f"Val annotations: {val_ann}")

    # 简化版图像增强 - 数据集已经处理过resize
    # 只使用Paddle内置的最小化增强
    train_transform = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_transform = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # 创建数据集
    train_dataset = TongueClassificationDataset(
        annotation_file=train_ann,
        image_dir=train_img_dir,
        image_size=(224, 224),
        transform=train_transform,
        mode='train'
    )

    val_dataset = TongueClassificationDataset(
        annotation_file=val_ann,
        image_dir=val_img_dir,
        image_size=(224, 224),
        transform=val_transform,
        mode='val'
    )

    logger.info(f"Train dataset size: {len(train_dataset)}")
    logger.info(f"Val dataset size: {len(val_dataset)}")

    # 获取类别分布
    train_dist = train_dataset.get_category_distribution()
    logger.info(f"Training distribution: {train_dist}")

    # 计算权重
    class_weights = get_class_weights_from_distribution(train_dist)

    return train_dataset, val_dataset, class_weights


def main():
    """主函数"""
    # 加载配置
    config_path = 'configs/experiment_config.yaml'
    config = load_config(config_path)

    # 创建数据集
    logger.info("Creating datasets...")
    train_dataset, val_dataset, class_weights = create_datasets(config)

    # 创建数据加载器
    logger.info("Creating data loaders...")
    train_loader = DataLoader(
        train_dataset,
        batch_size=16,
        shuffle=True,
        num_workers=2,
        drop_last=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=16,
        shuffle=False,
        num_workers=2
    )

    # 创建模型
    logger.info("Creating model...")
    model = MultiHeadClassificationModel()
    logger.info(f"Model created with {sum(p.numel().numpy() for p in model.parameters()):,} parameters")

    # 创建损失函数
    criterion = FocalLoss(alpha=0.25, gamma=2.0)

    # 训练配置
    trainer_config = TrainerConfig(
        epochs=3,  # 快速测试，只训练3个epoch
        batch_size=16,
        learning_rate=0.001,
        device='cpu',
        save_dir='checkpoints/quick_test',
        log_interval=5,
        save_interval=1
    )

    # 创建训练器
    logger.info("Creating trainer...")
    trainer = ClassificationTrainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        criterion=criterion,
        config=trainer_config,
        class_weights={}
    )

    # 开始训练
    logger.info("Starting training...")
    trainer.fit()

    logger.info("Training test completed!")


if __name__ == "__main__":
    main()
