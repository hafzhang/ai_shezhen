#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分类模型训练脚本

PP-HGNetV2-B4 多标签分类模型训练
包含类别不平衡处理

Usage:
    python train_classification.py --config configs/experiment_config.yaml
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import mlflow
import mlflow.paddle

import paddle
from paddle.io import DataLoader

from agents.ml_engineer import MLEngineerAgent, DatasetConfig, TrainingConfig, ClassificationConfig
from src.data.dataset import TongueClassificationDataset, StratifiedSampler
from src.models.classification import (
    PP_HGNetV2_B4, MultiHeadClassificationModel,
    FocalLoss, AsymmetricLoss, calculate_class_weights
)
from src.training.trainer import ClassificationTrainer, TrainerConfig, EarlyStopping

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_datasets(config: dict):
    """创建数据集"""
    base_path = config['dataset']['base_path']

    train_ann = os.path.join(base_path, config['dataset']['train']['annotations'])
    val_ann = os.path.join(base_path, config['dataset']['val']['annotations'])

    # 图像目录
    train_img_dir = os.path.join(base_path, config['dataset']['train'].get('images', 'train'))
    val_img_dir = os.path.join(base_path, config['dataset']['val'].get('images', 'val'))

    # 如果指定图像目录不存在，尝试其他可能的位置
    if not os.path.exists(train_img_dir):
        train_img_dir = os.path.dirname(train_ann)

    if not os.path.exists(val_img_dir):
        val_img_dir = os.path.dirname(val_ann)

    logger.info(f"Train annotations: {train_ann}")
    logger.info(f"Val annotations: {val_ann}")
    logger.info(f"Train images: {train_img_dir}")
    logger.info(f"Val images: {val_img_dir}")

    # 创建数据集
    image_size = tuple(config['dataset']['image_size'])

    train_dataset = TongueClassificationDataset(
        annotation_file=train_ann,
        image_dir=train_img_dir,
        image_size=image_size,
        transform=None,
        is_training=True,
        use_multi_label=True
    )

    val_dataset = TongueClassificationDataset(
        annotation_file=val_ann,
        image_dir=val_img_dir,
        image_size=image_size,
        transform=None,
        is_training=False,
        use_multi_label=True
    )

    return train_dataset, val_dataset


def create_model(config: dict):
    """创建模型"""
    cls_cfg = config['classification']

    # 创建骨干网络
    backbone = PP_HGNetV2_B4(
        num_classes=1000,
        in_channels=3,
        pretrained=cls_cfg['model'].get('pretrained')
    )

    # 准备多头配置
    head_configs = {}
    for head_name, head_config in cls_cfg['multi_head'].items():
        head_configs[head_name] = {
            "num_classes": head_config['num_classes'],
            "names": head_config.get('names', [])
        }

    # 创建多头分类模型
    model = MultiHeadClassificationModel(
        backbone=backbone,
        head_configs=head_configs,
        dropout=cls_cfg['model'].get('dropout', 0.2)
    )

    logger.info(f"Model created: {cls_cfg['model']['name']} with {len(head_configs)} heads")

    return model


def create_criterion(config: dict):
    """创建损失函数"""
    loss_cfg = config['classification']['loss']
    criterions = {}

    if loss_cfg['focal_loss']['enabled']:
        criterions['focal'] = FocalLoss(
            alpha=loss_cfg['focal_loss']['alpha'],
            gamma=loss_cfg['focal_loss']['gamma']
        )
        logger.info(f"Focal Loss created: alpha={loss_cfg['focal_loss']['alpha']}, "
                   f"gamma={loss_cfg['focal_loss']['gamma']}")

    if loss_cfg['asymmetric_loss']['enabled']:
        criterions['asymmetric'] = AsymmetricLoss(
            gamma_pos=loss_cfg['asymmetric_loss']['gamma_pos'],
            gamma_neg=loss_cfg['asymmetric_loss']['gamma_neg'],
            clip=loss_cfg['asymmetric_loss']['clip']
        )
        logger.info(f"Asymmetric Loss created")

    return criterions


def create_sampler(train_dataset: TongueClassificationDataset, config: dict):
    """创建分层采样器"""
    minority_classes = config['dataset'].get('minority_classes', [])
    sampling_cfg = config['classification']['sampling']

    sampler = StratifiedSampler(
        dataset=train_dataset,
        batch_size=config['classification']['training']['batch_size'],
        minority_classes=minority_classes,
        majority_ratio=sampling_cfg.get('majority_ratio', 0.8)
    )

    logger.info(f"StratifiedSampler created: minority_classes={minority_classes}")

    return sampler


def train(config: dict, resume_from: str = None):
    """执行训练流程"""
    logger.info("=" * 60)
    logger.info("Starting Classification Training")
    logger.info("=" * 60)

    # 创建数据集
    train_dataset, val_dataset = create_datasets(config)
    logger.info(f"Datasets: Train={len(train_dataset)}, Val={len(val_dataset)}")

    # 创建采样器（处理类别不平衡）
    sampler = create_sampler(train_dataset, config)

    # 创建数据加载器
    train_cfg = config['training']
    batch_size = config['classification']['training']['batch_size']

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        sampler=sampler,  # 使用分层采样器
        num_workers=train_cfg['num_workers'],
        drop_last=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=train_cfg['num_workers'],
        drop_last=False
    )

    logger.info(f"DataLoaders: Train batches={len(train_loader)}, Val batches={len(val_loader)}")

    # 创建模型
    model = create_model(config)

    # 创建损失函数
    criterions = create_criterion(config)

    # 创建训练配置
    cls_train_cfg = config['classification']['training']

    trainer_config = TrainerConfig(
        num_epochs=cls_train_cfg['num_epochs'],
        batch_size=cls_train_cfg['batch_size'],
        learning_rate=cls_train_cfg['learning_rate'],
        momentum=cls_train_cfg['momentum'],
        weight_decay=cls_train_cfg['weight_decay'],
        warmup_epochs=cls_train_cfg['warmup_epochs'],
        min_lr=cls_train_cfg.get('min_lr', 1e-6),
        early_stopping_patience=cls_train_cfg['early_stopping']['patience'],
        min_delta=cls_train_cfg['early_stopping']['min_delta'],
        checkpoint_dir=config['output']['checkpoints'] + '/classification',
        save_freq=train_cfg['checkpoint']['save_freq'],
        use_amp=train_cfg['amp']['enabled'],
        amp_level=train_cfg['amp']['level']
    )

    # 创建早停器
    early_stopping = EarlyStopping(
        patience=cls_train_cfg['early_stopping']['patience'],
        min_delta=cls_train_cfg['early_stopping']['min_delta'],
        mode=cls_train_cfg['early_stopping']['mode'],
        metric_name=cls_train_cfg['early_stopping']['monitor']
    )

    # 创建训练器
    trainer = ClassificationTrainer(
        model=model,
        criterion=criterions,
        config=trainer_config,
        train_loader=train_loader,
        val_loader=val_loader,
        early_stopping=early_stopping
    )

    # 恢复训练
    if resume_from:
        logger.info(f"Resuming from checkpoint: {resume_from}")
        trainer.load_checkpoint(resume_from)

    # MLflow配置
    if config['mlflow']['enabled']:
        mlflow.set_tracking_uri(config['mlflow']['tracking_uri'])
        mlflow.set_experiment(config['mlflow']['experiment_name'])

        # 记录参数
        mlflow.log_params({
            "model": config['classification']['model']['name'],
            "batch_size": cls_train_cfg['batch_size'],
            "learning_rate": cls_train_cfg['learning_rate'],
            "num_epochs": cls_train_cfg['num_epochs'],
            "sampling_strategy": config['classification']['sampling']['strategy'],
            "focal_alpha": config['classification']['loss']['focal_loss']['alpha'],
            "focal_gamma": config['classification']['loss']['focal_loss']['gamma']
        })

    # 开始训练
    history = trainer.train()

    # 记录最终指标
    if config['mlflow']['enabled']:
        final_f1 = history['val_macro_f1'][-1] if 'val_macro_f1' in history else 0
        final_map = history.get('val_mAP', [0])[-1] if 'val_mAP' in history else 0

        mlflow.log_metrics({
            "final_macro_f1": final_f1,
            "final_mAP": final_map
        })

    logger.info("=" * 60)
    logger.info("Training completed!")
    logger.info("=" * 60)
    logger.info(f"Final Macro F1: {history['val_macro_f1'][-1]:.4f}")
    logger.info(f"Final mAP: {history.get('val_mAP', [0])[-1]:.4f}")

    return history


def main():
    parser = argparse.ArgumentParser(description="Train classification model")
    parser.add_argument("--config", type=str, default="configs/experiment_config.yaml",
                       help="Path to config file")
    parser.add_argument("--resume", type=str, default=None,
                       help="Path to checkpoint to resume from")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 设置随机种子
    paddle.seed(config['training']['seed'])

    # 开始训练
    train(config, args.resume)


if __name__ == "__main__":
    main()
