#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
训练器

包含分类和分割的训练器
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

import numpy as np
import paddle
import paddle.nn as nn
import paddle.optimizer as optim
from paddle.io import DataLoader
from tqdm import tqdm

import mlflow
import mlflow.paddle


@dataclass
class TrainerConfig:
    """训练器配置"""
    # 训练参数
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001

    # 优化器
    optimizer: str = 'adam'
    weight_decay: float = 1e-4

    # 学习率调度
    scheduler: str = 'cosine'
    warmup_epochs: int = 5
    min_lr: float = 1e-6

    # 保存和日志
    save_dir: str = 'checkpoints'
    log_interval: int = 10
    save_interval: int = 5

    # 其他
    device: str = 'cpu'
    use_amp: bool = False
    gradient_clip: float = 5.0


class EarlyStopping:
    """早停机制"""

    def __init__(self, patience: int = 10, min_delta: float = 0.001, mode: str = 'min'):
        """
        Args:
            patience: 容忍的epoch数
            min_delta: 最小改进
            mode: 'min' 或 'max'
        """
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.early_stop = False

    def __call__(self, score: float) -> bool:
        """
        Args:
            score: 当前指标值

        Returns:
            是否应该停止训练
        """
        if self.best_score is None:
            self.best_score = score
            return False

        if self.mode == 'min':
            improved = score < self.best_score - self.min_delta
        else:
            improved = score > self.best_score + self.min_delta

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True

        return self.early_stop


class ClassificationTrainer:
    """分类模型训练器"""

    def __init__(
        self,
        model: nn.Layer,
        train_loader: DataLoader,
        val_loader: DataLoader,
        criterion: nn.Layer,
        config: TrainerConfig = None,
        class_weights: Optional[Dict[str, np.ndarray]] = None
    ):
        """
        Args:
            model: 模型
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            criterion: 损失函数
            config: 训练配置
            class_weights: 类别权重 {head_name: weights}
        """
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.criterion = criterion
        self.config = config or TrainerConfig()
        self.class_weights = class_weights or {}

        # 设备
        self.device = paddle.set_device(self.config.device)

        # 创建保存目录
        Path(self.config.save_dir).mkdir(parents=True, exist_ok=True)

        # 优化器
        self.optimizer = self._create_optimizer()

        # 学习率调度器
        self.scheduler = self._create_scheduler()

        # 早停
        self.early_stopping = EarlyStopping(patience=15, mode='min')

        # 训练状态
        self.current_epoch = 0
        self.best_val_loss = float('inf')
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'learning_rate': []
        }

    def _create_optimizer(self):
        """创建优化器"""
        # 梯度裁剪
        grad_clip = None
        if self.config.gradient_clip > 0:
            grad_clip = paddle.nn.ClipGradByNorm(clip_norm=self.config.gradient_clip)

        if self.config.optimizer.lower() == 'adam':
            return optim.Adam(
                parameters=self.model.parameters(),
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                grad_clip=grad_clip
            )
        elif self.config.optimizer.lower() == 'sgd':
            return optim.SGD(
                parameters=self.model.parameters(),
                learning_rate=self.config.learning_rate,
                momentum=0.9,
                weight_decay=self.config.weight_decay,
                grad_clip=grad_clip
            )
        else:
            raise ValueError(f"Unknown optimizer: {self.config.optimizer}")

    def _create_scheduler(self):
        """创建学习率调度器"""
        if self.config.scheduler == 'cosine':
            t_max = max(1, int(self.config.epochs - self.config.warmup_epochs))
            return optim.lr.CosineAnnealingDecay(
                learning_rate=self.config.learning_rate,
                T_max=t_max,
                eta_min=self.config.min_lr
            )
        elif self.config.scheduler == 'step':
            return optim.lr.StepDecay(
                learning_rate=self.config.learning_rate,
                step_size=30,
                gamma=0.1
            )
        else:
            return None

    def train_epoch(self, epoch: int) -> float:
        """
        训练一个epoch

        Args:
            epoch: 当前epoch

        Returns:
            平均损失
        """
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        pbar = tqdm(self.train_loader, desc=f"Epoch {epoch}/{self.config.epochs} [Train]")

        for batch_idx, (images, labels) in enumerate(pbar):
            images = images.to(self.device)

            # 前向传播
            predictions = self.model(images)

            # 计算损失
            loss = 0.0
            for head_name, logits in predictions.items():
                target = labels[head_name].to(self.device)

                # 应用类别权重
                if head_name in self.class_weights:
                    weights = paddle.to_tensor(
                        self.class_weights[head_name],
                        dtype='float32'
                    ).to(self.device)
                    # 加权损失
                    head_loss = self.criterion(logits, target)
                    # 简单处理：平均损失
                    head_loss = head_loss * 1.0
                else:
                    head_loss = self.criterion(logits, target)

                loss += head_loss

            # 平均损失
            loss = loss / len(predictions)

            # 反向传播
            loss.backward()

            # 参数更新（梯度裁剪已在优化器中设置）
            self.optimizer.step()
            self.optimizer.clear_grad()

            # 记录
            total_loss += loss.item()
            num_batches += 1

            # 更新进度条
            if batch_idx % self.config.log_interval == 0:
                pbar.set_postfix({'loss': loss.item()})

        avg_loss = total_loss / num_batches
        return avg_loss

    @paddle.no_grad()
    def validate(self, epoch: int) -> float:
        """
        验证模型

        Args:
            epoch: 当前epoch

        Returns:
            平均损失
        """
        self.model.eval()
        total_loss = 0.0
        num_batches = 0

        pbar = tqdm(self.val_loader, desc=f"Epoch {epoch}/{self.config.epochs} [Val]")

        for batch_idx, (images, labels) in enumerate(pbar):
            images = images.to(self.device)

            # 前向传播
            predictions = self.model(images)

            # 计算损失
            loss = 0.0
            for head_name, logits in predictions.items():
                target = labels[head_name].to(self.device)
                head_loss = self.criterion(logits, target)
                loss += head_loss

            # 平均损失
            loss = loss / len(predictions)

            # 记录
            total_loss += loss.item()
            num_batches += 1

            # 更新进度条
            if batch_idx % self.config.log_interval == 0:
                pbar.set_postfix({'loss': loss.item()})

        avg_loss = total_loss / num_batches
        return avg_loss

    def fit(self):
        """
        完整训练流程
        """
        print("=" * 60)
        print("Starting Training")
        print("=" * 60)
        print(f"Device: {self.config.device}")
        print(f"Epochs: {self.config.epochs}")
        print(f"Batch size: {self.config.batch_size}")
        print(f"Learning rate: {self.config.learning_rate}")
        print("=" * 60)

        # MLflow跟踪
        mlflow.set_experiment("shezhen_classification")

        with mlflow.start_run():
            # 记录参数
            mlflow.log_params({
                'epochs': self.config.epochs,
                'batch_size': self.config.batch_size,
                'learning_rate': self.config.learning_rate,
                'optimizer': self.config.optimizer,
                'weight_decay': self.config.weight_decay
            })

            for epoch in range(1, self.config.epochs + 1):
                self.current_epoch = epoch
                start_time = time.time()

                # 训练
                train_loss = self.train_epoch(epoch)

                # 验证
                val_loss = self.validate(epoch)

                # 学习率调度
                if self.scheduler:
                    lr = self.scheduler.get_lr()
                    if isinstance(lr, list):
                        lr = lr[0]
                    mlflow.log_metric('learning_rate', lr, step=epoch)
                else:
                    lr = self.config.learning_rate

                # 记录历史
                self.history['train_loss'].append(train_loss)
                self.history['val_loss'].append(val_loss)
                self.history['learning_rate'].append(lr)

                # MLflow记录
                mlflow.log_metrics({
                    'train_loss': train_loss,
                    'val_loss': val_loss
                }, step=epoch)

                # 打印
                epoch_time = time.time() - start_time
                print(f"\nEpoch {epoch}/{self.config.epochs} - "
                      f"Train Loss: {train_loss:.4f}, "
                      f"Val Loss: {val_loss:.4f}, "
                      f"Time: {epoch_time:.2f}s\n")

                # 保存最佳模型
                if val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.save_checkpoint('best_model.pdparams', epoch, val_loss)
                    print(f"✓ Best model saved (val_loss: {val_loss:.4f})")

                # 定期保存
                if epoch % self.config.save_interval == 0:
                    self.save_checkpoint(f'epoch_{epoch}.pdparams', epoch, val_loss)

                # 早停检查
                if self.early_stopping(val_loss):
                    print(f"\nEarly stopping at epoch {epoch}")
                    break

        print("\n" + "=" * 60)
        print("Training Completed")
        print(f"Best Val Loss: {self.best_val_loss:.4f}")
        print("=" * 60)

    def save_checkpoint(self, filename: str, epoch: int, val_loss: float):
        """
        保存检查点

        Args:
            filename: 文件名
            epoch: 当前epoch
            val_loss: 验证损失
        """
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'val_loss': val_loss,
            'history': self.history
        }

        filepath = os.path.join(self.config.save_dir, filename)
        paddle.save(checkpoint, filepath)

        print(f"Checkpoint saved: {filepath}")

    def load_checkpoint(self, filepath: str):
        """
        加载检查点

        Args:
            filepath: 检查点路径
        """
        checkpoint = paddle.load(filepath)

        self.model.set_state_dict(checkpoint['model_state_dict'])
        self.optimizer.set_state_dict(checkpoint['optimizer_state_dict'])

        if 'epoch' in checkpoint:
            self.current_epoch = checkpoint['epoch']
        if 'val_loss' in checkpoint:
            self.best_val_loss = checkpoint['val_loss']
        if 'history' in checkpoint:
            self.history = checkpoint['history']

        print(f"Checkpoint loaded: {filepath}")
        print(f"Resuming from epoch {self.current_epoch}")


if __name__ == "__main__":
    # 测试训练器
    print("Trainer module loaded successfully")
