#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据增强Pipeline配置（Albumentations）

为分割和分类任务配置数据增强策略，包括：
- 分割任务增强：翻转、旋转、缩放、颜色抖动
- 分类任务增强：CutMix、MixUp、AutoAugment
- 少数类专项增强策略
- 医学图像专用增强（Lab颜色空间）

Usage:
    python datasets/tools/augmentation.py --task segmentation --visualize
    python datasets/tools/augmentation.py --task classification --visualize
    python datasets/tools/augmentation.py --minority-only --augment-count 10
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from PIL import Image
import cv2
import albumentations as A
from albumentations.pytorch import ToTensorV2
import matplotlib.pyplot as plt
import matplotlib
from tqdm import tqdm

# Set Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Use non-interactive backend for matplotlib
matplotlib.use('Agg')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Enums and Constants ====================

class TaskType(Enum):
    """任务类型"""
    SEGMENTATION = "segmentation"
    CLASSIFICATION = "classification"


class AugmentationStrength(Enum):
    """增强强度"""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


# Medical image augmentation constants
TONGUE_COLOR_RANGE = {
    'healthy': {'h_min': 0, 'h_max': 30, 's_min': 20, 's_max': 80, 'v_min': 180, 'v_max': 255},  # 淡红/淡白
    'red': {'h_min': 0, 'h_max': 20, 's_min': 50, 's_max': 150, 'v_min': 100, 'v_max': 255},  # 红舌
    'purple': {'h_min': 240, 'h_max': 280, 's_min': 30, 's_max': 100, 'v_min': 80, 'v_max': 200},  # 绛紫舌
    'pale': {'h_min': 0, 'h_max': 30, 's_min': 0, 's_max': 30, 'v_min': 180, 'v_max': 255},  # 淡白舌
}

COATING_COLOR_RANGE = {
    'white': {'h_min': 0, 'h_max': 180, 's_min': 0, 's_max': 30, 'v_min': 180, 'v_max': 255},  # 白苔
    'yellow': {'h_min': 30, 'h_max': 60, 's_min': 30, 's_max': 120, 'v_min': 150, 'v_max': 255},  # 黄苔
    'black': {'h_min': 0, 'h_max': 180, 's_min': 0, 's_max': 30, 'v_min': 20, 'v_max': 100},  # 黑苔
}


# ==================== Augmentation Pipeline Classes ====================

@dataclass
class AugmentationConfig:
    """增强配置"""
    task_type: TaskType
    strength: AugmentationStrength = AugmentationStrength.MEDIUM
    image_size: Tuple[int, int] = (512, 512)
    use_lab_color: bool = True
    minority_class_enhanced: bool = False
    probability: float = 0.8


class SegmentationAugmentationPipeline:
    """
    分割任务增强Pipeline

    使用Albumentations库实现，支持：
    - 几何变换：翻转、旋转、缩放、弹性变换
    - 颜色变换：HSV调整、对比度、亮度
    - 医学图像专用：Lab颜色空间增强
    - 噪声注入：高斯噪声、模糊
    """

    # Predefined augmentation presets
    AUGMENTATION_PRESETS = {
        AugmentationStrength.LIGHT: {
            'horizontal_flip_prob': 0.5,
            'vertical_flip_prob': 0.0,
            'rotate_prob': 0.3,
            'rotate_limit': 15,
            'scale_prob': 0.3,
            'scale_limit': 0.1,
            'brightness_prob': 0.3,
            'brightness_limit': 0.1,
            'contrast_prob': 0.3,
            'contrast_limit': 0.1,
            'blur_prob': 0.1,
            'noise_prob': 0.1,
        },
        AugmentationStrength.MEDIUM: {
            'horizontal_flip_prob': 0.5,
            'vertical_flip_prob': 0.1,
            'rotate_prob': 0.5,
            'rotate_limit': 30,
            'scale_prob': 0.4,
            'scale_limit': 0.2,
            'brightness_prob': 0.4,
            'brightness_limit': 0.2,
            'contrast_prob': 0.4,
            'contrast_limit': 0.2,
            'blur_prob': 0.2,
            'noise_prob': 0.2,
            'elastic_prob': 0.2,
            'elastic_alpha': 50,
            'grid_distortion_prob': 0.1,
        },
        AugmentationStrength.HEAVY: {
            'horizontal_flip_prob': 0.5,
            'vertical_flip_prob': 0.2,
            'rotate_prob': 0.7,
            'rotate_limit': 45,
            'scale_prob': 0.5,
            'scale_limit': 0.3,
            'brightness_prob': 0.5,
            'brightness_limit': 0.3,
            'contrast_prob': 0.5,
            'contrast_limit': 0.3,
            'blur_prob': 0.3,
            'noise_prob': 0.3,
            'elastic_prob': 0.4,
            'elastic_alpha': 100,
            'grid_distortion_prob': 0.3,
            'optical_distortion_prob': 0.2,
            'shift_scale_rotate_prob': 0.5,
        }
    }

    def __init__(self, config: AugmentationConfig):
        """
        初始化分割增强Pipeline

        Args:
            config: 增强配置
        """
        self.config = config
        self.pipeline = self._build_pipeline()

    def _build_pipeline(self) -> A.Compose:
        """构建增强Pipeline"""
        params = self.AUGMENTATION_PRESETS[self.config.strength]

        transforms = []

        # Geometric transformations
        if params['horizontal_flip_prob'] > 0:
            transforms.append(A.HorizontalFlip(p=params['horizontal_flip_prob']))

        if params['vertical_flip_prob'] > 0:
            transforms.append(A.VerticalFlip(p=params['vertical_flip_prob']))

        if params['rotate_prob'] > 0:
            transforms.append(A.Rotate(
                limit=params['rotate_limit'],
                p=params['rotate_prob'],
                border_mode=cv2.BORDER_CONSTANT,
                fill=0
            ))

        if params.get('shift_scale_rotate_prob', 0) > 0:
            transforms.append(A.ShiftScaleRotate(
                shift_limit=0.1,
                scale_limit=params['scale_limit'],
                rotate_limit=params['rotate_limit'],
                p=params['shift_scale_rotate_prob'],
                border_mode=cv2.BORDER_CONSTANT,
                value=0
            ))

        if params['scale_prob'] > 0:
            transforms.append(A.RandomScale(
                scale_limit=params['scale_limit'],
                p=params['scale_prob']
            ))

        # Elastic and distortion transformations
        if params.get('elastic_prob', 0) > 0:
            transforms.append(A.ElasticTransform(
                alpha=params.get('elastic_alpha', 50),
                sigma=120 * 0.05,
                p=params['elastic_prob']
            ))

        if params.get('grid_distortion_prob', 0) > 0:
            transforms.append(A.GridDistortion(
                num_steps=5,
                distort_limit=0.1,
                p=params['grid_distortion_prob']
            ))

        if params.get('optical_distortion_prob', 0) > 0:
            transforms.append(A.OpticalDistortion(
                distort_limit=0.1,
                shift_limit=0.05,
                p=params['optical_distortion_prob']
            ))

        # Color augmentations
        if params['brightness_prob'] > 0 or params['contrast_prob'] > 0:
            transforms.append(A.RandomBrightnessContrast(
                brightness_limit=params['brightness_limit'],
                contrast_limit=params['contrast_limit'],
                p=max(params['brightness_prob'], params['contrast_prob'])
            ))

        # HSV color space augmentation (useful for tongue color variations)
        transforms.append(A.HueSaturationValue(
            hue_shift_limit=20,
            sat_shift_limit=30,
            val_shift_limit=20,
            p=0.5
        ))

        # Blur and noise
        if params['blur_prob'] > 0:
            transforms.append(A.OneOf([
                A.GaussianBlur(blur_limit=(3, 7), p=1.0),
                A.MotionBlur(blur_limit=(3, 7), p=1.0),
                A.MedianBlur(blur_limit=(3, 7), p=1.0),
            ], p=params['blur_prob']))

        if params['noise_prob'] > 0:
            transforms.append(A.OneOf([
                A.GaussNoise(std_range=(10.0/255, 50.0/255), p=1.0),  # Convert to [0,1] range
                A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.3), p=1.0),
            ], p=params['noise_prob']))

        # Cropping and resizing
        transforms.append(A.RandomResizedCrop(
            size=self.config.image_size,
            scale=(0.8, 1.0),
            ratio=(0.9, 1.1),
            p=0.5
        ))

        # Ensure final size
        transforms.append(A.Resize(
            height=self.config.image_size[0],
            width=self.config.image_size[1]
        ))

        # Normalize
        transforms.append(A.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
            p=1.0
        ))

        return A.Compose(transforms, p=self.config.probability)

    def __call__(self, image: np.ndarray, mask: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        """
        应用增强

        Args:
            image: 输入图像 (H, W, C)
            mask: 分割mask (H, W)，可选

        Returns:
            增强后的图像和mask
        """
        if mask is not None:
            augmented = self.pipeline(image=image, mask=mask)
            return {'image': augmented['image'], 'mask': augmented['mask']}
        else:
            augmented = self.pipeline(image=image)
            return {'image': augmented['image']}


class ClassificationAugmentationPipeline:
    """
    分类任务增强Pipeline

    支持：
    - AutoAugment: 自动搜索最优增强策略
    - CutMix: 混合两张图像和标签
    - MixUp: 线性插值两张图像
    - RandAugment: 随机选择增强组合
    - 标签平滑
    """

    AUGMENTATION_PRESETS = {
        AugmentationStrength.LIGHT: {
            'horizontal_flip_prob': 0.5,
            'rotate_prob': 0.3,
            'rotate_limit': 15,
            'color_jitter_prob': 0.3,
            'color_jitter_strength': 0.1,
            'cutmix_prob': 0.0,
            'cutmix_beta': 1.0,
            'mixup_prob': 0.0,
            'mixup_alpha': 0.2,
        },
        AugmentationStrength.MEDIUM: {
            'horizontal_flip_prob': 0.5,
            'rotate_prob': 0.5,
            'rotate_limit': 30,
            'color_jitter_prob': 0.5,
            'color_jitter_strength': 0.2,
            'cutmix_prob': 0.2,
            'cutmix_beta': 1.0,
            'mixup_prob': 0.1,
            'mixup_alpha': 0.2,
        },
        AugmentationStrength.HEAVY: {
            'horizontal_flip_prob': 0.5,
            'rotate_prob': 0.7,
            'rotate_limit': 45,
            'color_jitter_prob': 0.7,
            'color_jitter_strength': 0.3,
            'cutmix_prob': 0.3,  # CutMix 0.2-0.5 range
            'cutmix_beta': 1.0,
            'mixup_prob': 0.2,  # MixUp 0.1-0.3 range
            'mixup_alpha': 0.2,
            'randaugment_num': 2,
            'randaugment_magnitude': 9,
        }
    }

    def __init__(self, config: AugmentationConfig):
        """
        初始化分类增强Pipeline

        Args:
            config: 增强配置
        """
        self.config = config
        self.train_pipeline = self._build_train_pipeline()
        self.val_pipeline = self._build_val_pipeline()

    def _build_train_pipeline(self) -> A.Compose:
        """构建训练增强Pipeline"""
        params = self.AUGMENTATION_PRESETS[self.config.strength]

        transforms = []

        # Geometric transformations
        transforms.append(A.HorizontalFlip(p=params['horizontal_flip_prob']))
        transforms.append(A.VerticalFlip(p=0.1))
        transforms.append(A.Rotate(limit=params['rotate_limit'], p=params['rotate_prob']))

        # Color augmentations
        transforms.append(A.OneOf([
            A.ColorJitter(
                brightness=params['color_jitter_strength'],
                contrast=params['color_jitter_strength'],
                saturation=params['color_jitter_strength'],
                hue=0.1,
                p=1.0
            ),
            A.HueSaturationValue(
                hue_shift_limit=20,
                sat_shift_limit=30,
                val_shift_limit=20,
                p=1.0
            ),
            A.RGBShift(r_shift_limit=20, g_shift_limit=20, b_shift_limit=20, p=1.0),
        ], p=params['color_jitter_prob']))

        # AutoAugment / RandAugment for medical images
        if self.config.strength == AugmentationStrength.HEAVY:
            num_ops = params.get('randaugment_num', 2)
            magnitude = params.get('randaugment_magnitude', 9)
            transforms.append(A.RandAugment(num_ops=num_ops, magnitude=magnitude, p=0.5))

        # Blur and noise
        transforms.append(A.OneOf([
            A.GaussianBlur(blur_limit=(3, 7), p=1.0),
            A.MotionBlur(blur_limit=(3, 7), p=1.0),
            A.MedianBlur(blur_limit=(3, 5), p=1.0),
        ], p=0.2))

        # Cropping
        transforms.append(A.RandomResizedCrop(
            size=self.config.image_size,
            scale=(0.8, 1.0),
            ratio=(0.9, 1.1),
            p=0.5
        ))

        # Resize
        transforms.append(A.Resize(
            height=self.config.image_size[0],
            width=self.config.image_size[1]
        ))

        # Coarse dropout (simulating occlusions)
        transforms.append(A.CoarseDropout(
            max_holes=8,
            max_size=32,
            min_holes=1,
            min_size=8,
            p=0.2
        ))

        # Normalize
        transforms.append(A.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ))

        return A.Compose(transforms, p=self.config.probability)

    def _build_val_pipeline(self) -> A.Compose:
        """构建验证Pipeline（仅Resize和Normalize）"""
        return A.Compose([
            A.Resize(height=self.config.image_size[0], width=self.config.image_size[1]),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def __call__(self, image: np.ndarray, training: bool = True) -> np.ndarray:
        """
        应用增强

        Args:
            image: 输入图像 (H, W, C)
            training: 是否为训练模式

        Returns:
            增强后的图像
        """
        pipeline = self.train_pipeline if training else self.val_pipeline
        augmented = pipeline(image=image)
        return augmented['image']

    def cutmix(self, image1: np.ndarray, label1: np.ndarray,
               image2: np.ndarray, label2: np.ndarray,
               beta: float = 1.0) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        CutMix增强：混合两张图像

        Args:
            image1: 图像1 (H, W, C)
            label1: 标签1
            image2: 图像2 (H, W, C)
            label2: 标签2
            beta: Beta分布参数

        Returns:
            混合图像、混合标签、lambda值
        """
        lam = np.random.beta(beta, beta)
        h, w, _ = image1.shape

        # 随机裁剪区域
        cut_rat = np.sqrt(1.0 - lam)
        cut_w = int(w * cut_rat)
        cut_h = int(h * cut_rat)

        cx = np.random.randint(w)
        cy = np.random.randint(h)

        bbx1 = np.clip(cx - cut_w // 2, 0, w)
        bby1 = np.clip(cy - cut_h // 2, 0, h)
        bbx2 = np.clip(cx + cut_w // 2, 0, w)
        bby2 = np.clip(cy + cut_h // 2, 0, h)

        # 混合图像
        mixed_image = image1.copy()
        mixed_image[bby1:bby2, bbx1:bbx2] = image2[bby1:bby2, bbx1:bbx2]

        # 调整lambda
        lam = 1 - ((bbx2 - bbx1) * (bby2 - bby1) / (w * h))

        # 混合标签
        mixed_label = lam * label1 + (1 - lam) * label2

        return mixed_image, mixed_label, lam

    def mixup(self, image1: np.ndarray, label1: np.ndarray,
              image2: np.ndarray, label2: np.ndarray,
              alpha: float = 0.2) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        MixUp增强：线性插值两张图像

        Args:
            image1: 图像1 (H, W, C)
            label1: 标签1
            image2: 图像2 (H, W, C)
            label2: 标签2
            alpha: Beta分布参数

        Returns:
            混合图像、混合标签、lambda值
        """
        lam = np.random.beta(alpha, alpha)

        mixed_image = lam * image1 + (1 - lam) * image2
        mixed_label = lam * label1 + (1 - lam) * label2

        return mixed_image.astype(np.uint8), mixed_label, lam


class MinorityClassAugmentation:
    """
    少数类专项增强策略

    针对样本数<100的类别实施更强增强：
    - 更高的增强概率
    - 更多样的增强组合
    - 超分辨率增强
    - 语义保持的颜色增强
    """

    # Minority classes based on dataset analysis
    MINORITY_CLASSES = {
        # 舌色
        'jiangpushe': 3,      # 绛紫舌
        # 苔色
        'heitaishe': 11,      # 黑苔舌
        'huataishe': 12,      # 花剥苔舌
        # 舌形
        'shoushe': 5,         # 瘦薄舌
        # 苔质
        # 特征
        'liewenshe': 7,       # 裂纹舌
    }

    def __init__(self, base_pipeline: Union[SegmentationAugmentationPipeline, ClassificationAugmentationPipeline]):
        """
        初始化少数类增强器

        Args:
            base_pipeline: 基础增强Pipeline
        """
        self.base_pipeline = base_pipeline
        self.intense_pipeline = self._build_intense_pipeline()

    def _build_intense_pipeline(self) -> A.Compose:
        """构建更强增强Pipeline"""
        transforms = [
            # More aggressive geometric transforms
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.3),
            A.Rotate(limit=45, p=0.8),

            # Elastic transformations for tongue shape variation
            A.ElasticTransform(alpha=100, sigma=120 * 0.05, p=0.5),
            A.GridDistortion(num_steps=5, distort_limit=0.2, p=0.4),

            # Perspective transform
            A.PerspectiveScale(scale=0.05, p=0.3),

            # More aggressive color jitter
            A.OneOf([
                A.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1, p=1.0),
                A.HueSaturationValue(hue_shift_limit=30, sat_shift_limit=50, val_shift_limit=30, p=1.0),
                A.RGBShift(r_shift_limit=30, g_shift_limit=30, b_shift_limit=30, p=1.0),
            ], p=0.7),

            # Noise and blur variations
            A.OneOf([
                A.GaussianBlur(blur_limit=(3, 9), p=1.0),
                A.MotionBlur(blur_limit=(3, 9), p=1.0),
                A.GaussNoise(std_range=(10.0/255, 80.0/255), p=1.0),  # Convert to [0,1] range
                A.ISONoise(color_shift=(0.01, 0.1), intensity=(0.1, 0.5), p=1.0),
            ], p=0.4),

            # Coarse dropout for robustness
            A.CoarseDropout(max_holes=12, max_size=32, p=0.3),

            # Resize
            A.Resize(height=512, width=512),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]

        return A.Compose(transforms, p=1.0)

    def augment(self, image: np.ndarray, mask: Optional[np.ndarray] = None,
               augment_count: int = 5) -> List[Dict[str, np.ndarray]]:
        """
        对少数类样本进行多次增强

        Args:
            image: 输入图像
            mask: 分割mask（可选）
            augment_count: 增强次数

        Returns:
            增强后的图像列表
        """
        results = []

        for i in range(augment_count):
            # Use intense pipeline for minority classes
            if mask is not None:
                augmented = self.intense_pipeline(image=image, mask=mask)
                results.append({'image': augmented['image'], 'mask': augmented['mask']})
            else:
                augmented = self.intense_pipeline(image=image)
                results.append({'image': augmented['image']})

        return results


class LabColorSpaceAugmentation:
    """
    Lab颜色空间增强（医学图像专用）

    Lab颜色空间更符合人眼感知，适合舌诊图像增强：
    - L通道：亮度调整
    - a通道：红绿调整
    - b通道：黄蓝调整
    """

    def __init__(self, config: AugmentationConfig):
        """
        初始化Lab颜色空间增强

        Args:
            config: 增强配置
        """
        self.config = config

    def _rgb_to_lab(self, image: np.ndarray) -> np.ndarray:
        """RGB转Lab颜色空间"""
        # Convert RGB to Lab via float conversion
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        return lab

    def _lab_to_rgb(self, lab: np.ndarray) -> np.ndarray:
        """Lab转RGB颜色空间"""
        rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        return rgb

    def augment(self, image: np.ndarray) -> np.ndarray:
        """
        在Lab颜色空间进行增强

        Args:
            image: RGB图像 (H, W, C)

        Returns:
            增强后的RGB图像
        """
        # Convert to Lab
        lab = self._rgb_to_lab(image)

        # Split channels
        l, a, b = cv2.split(lab)

        # Apply augmentations
        # L channel: brightness
        l_shift = np.random.randint(-20, 20)
        l = np.clip(l.astype(np.int16) + l_shift, 0, 255).astype(np.uint8)

        # a channel: red-green balance
        a_shift = np.random.randint(-15, 15)
        a = np.clip(a.astype(np.int16) + a_shift, 0, 255).astype(np.uint8)

        # b channel: yellow-blue balance
        b_shift = np.random.randint(-15, 15)
        b = np.clip(b.astype(np.int16) + b_shift, 0, 255).astype(np.uint8)

        # Merge and convert back
        lab_aug = cv2.merge([l, a, b])
        rgb_aug = self._lab_to_rgb(lab_aug)

        return rgb_aug


# ==================== Visualization ====================

class AugmentationVisualizer:
    """增强效果可视化工具"""

    def __init__(self, output_dir: str):
        """
        初始化可视化器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def visualize_segmentation_augmentations(
        self,
        original_image: np.ndarray,
        original_mask: np.ndarray,
        augmented_samples: List[Dict[str, np.ndarray]],
        sample_name: str,
        num_variants: int = 9
    ) -> str:
        """
        可视化分割增强效果（原始 + 9种变体）

        Args:
            original_image: 原始图像
            original_mask: 原始mask
            augmented_samples: 增强样本列表
            sample_name: 样本名称
            num_variants: 变体数量

        Returns:
            保存的图片路径
        """
        num_display = min(num_variants, len(augmented_samples))
        num_cols = 5
        num_rows = 2

        fig, axes = plt.subplots(num_rows, num_cols, figsize=(20, 8))
        fig.suptitle(f'Segmentation Augmentation Visualization - {sample_name}', fontsize=16)

        # Original image + mask overlay
        axes[0, 0].imshow(original_image)
        axes[0, 0].set_title('Original Image')
        axes[0, 0].axis('off')

        # Original mask
        axes[1, 0].imshow(original_mask, cmap='gray')
        axes[1, 0].set_title('Original Mask')
        axes[1, 0].axis('off')

        # Display augmented samples
        for i in range(num_display):
            # Layout: 2 rows x 5 columns (10 slots total)
            # Slot 0,0 and 1,0 are used for original
            # Remaining 8 slots (0,1-0,4 and 1,1-1,4) for augmentations
            if i < 4:
                row, col = 0, i + 1
            else:
                row, col = 1, i - 4

            aug_image = augmented_samples[i]['image']

            # Denormalize for visualization
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            aug_image = aug_image * std + mean
            aug_image = np.clip(aug_image, 0, 1)

            axes[row, col].imshow(aug_image)

            if 'mask' in augmented_samples[i]:
                aug_mask = augmented_samples[i]['mask']
                # Overlay mask with transparency
                axes[row, col].imshow(aug_mask, cmap='jet', alpha=0.3)

            axes[row, col].set_title(f'Augment {i+1}')
            axes[row, col].axis('off')

        # Hide unused subplots
        for row in range(num_rows):
            for col in range(num_cols):
                if row == 0 and col == 0:
                    continue  # Original image
                if row == 1 and col == 0:
                    continue  # Original mask
                # Check if this position was used
                pos_used = False
                if row == 0 and col <= num_display:
                    if col - 1 < num_display:
                        pos_used = True
                elif row == 1 and col <= num_display - 4:
                    if col + 3 < num_display:
                        pos_used = True
                if not pos_used:
                    axes[row, col].axis('off')

        plt.tight_layout()

        output_path = self.output_dir / f"{sample_name}_seg_aug.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return str(output_path)

    def visualize_classification_augmentations(
        self,
        original_image: np.ndarray,
        augmented_samples: List[np.ndarray],
        sample_name: str,
        num_variants: int = 9
    ) -> str:
        """
        可视化分类增强效果（原始 + 9种变体）

        Args:
            original_image: 原始图像
            augmented_samples: 增强样本列表
            sample_name: 样本名称
            num_variants: 变体数量

        Returns:
            保存的图片路径
        """
        num_display = min(num_variants, len(augmented_samples))
        num_cols = 5
        num_rows = 2

        fig, axes = plt.subplots(num_rows, num_cols, figsize=(20, 8))
        fig.suptitle(f'Classification Augmentation Visualization - {sample_name}', fontsize=16)

        # Original image
        axes[0, 0].imshow(original_image)
        axes[0, 0].set_title('Original')
        axes[0, 0].axis('off')

        # Display augmented samples
        for i in range(num_display):
            # Layout: 2 rows x 5 columns (10 slots total)
            # Slot 0,0 is used for original
            # Remaining 9 slots for augmentations
            if i < 4:
                row, col = 0, i + 1
            else:
                row, col = 1, i - 4

            aug_image = augmented_samples[i]

            # Denormalize for visualization
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            aug_image = aug_image * std + mean
            aug_image = np.clip(aug_image, 0, 1)

            axes[row, col].imshow(aug_image)
            axes[row, col].set_title(f'Augment {i+1}')
            axes[row, col].axis('off')

        # Hide unused subplots
        for row in range(num_rows):
            for col in range(num_cols):
                if row == 0 and col == 0:
                    continue  # Original image
                # Check if this position was used
                pos_used = False
                if row == 0 and col <= num_display:
                    if col - 1 < num_display:
                        pos_used = True
                elif row == 1 and col < num_display - 4:
                    pos_used = True
                if not pos_used:
                    axes[row, col].axis('off')

        plt.tight_layout()

        output_path = self.output_dir / f"{sample_name}_cla_aug.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return str(output_path)


# ==================== Main Functions ====================

def load_sample_images(data_root: str, task: TaskType, num_samples: int = 10) -> List[Dict[str, Any]]:
    """
    加载样本图像

    Args:
        data_root: 数据集根目录
        task: 任务类型
        num_samples: 加载数量

    Returns:
        样本列表
    """
    samples = []

    if task == TaskType.SEGMENTATION:
        image_dir = Path(data_root) / "train" / "images"
        mask_dir = Path(data_root) / "train" / "masks"

        image_files = list(image_dir.glob("*.jpg"))[:num_samples]

        for img_file in image_files:
            image = np.array(Image.open(img_file).convert('RGB'))

            mask_file = mask_dir / f"{img_file.stem}.png"
            if mask_file.exists():
                mask = np.array(Image.open(mask_file).convert('L'))
            else:
                mask = None

            samples.append({
                'name': img_file.stem,
                'image': image,
                'mask': mask
            })

    elif task == TaskType.CLASSIFICATION:
        # For classification, data_root should be the base directory (e.g., datasets/processed)
        # We need to find clas_v1/train/labels.txt
        # data_root is passed as datasets/processed/clas_v1 for classification
        base_path = Path(data_root)

        # Check if we're at the right level
        if base_path.name in ['train', 'val', 'test']:
            # data_root is pointing to a split directory
            label_file = base_path / "labels.txt"
            image_base = base_path.parent.parent / "seg_v1" / base_path.name / "images"
        else:
            # data_root is pointing to the processed/clas_v1 level
            label_file = base_path / "train" / "labels.txt"
            # For images, look in seg_v1 since that's where actual images are
            image_base = base_path.parent / "seg_v1" / "train" / "images"

        if label_file.exists():
            with open(label_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:num_samples]

            for line in lines:
                parts = line.strip().split('\t')
                if len(parts) < 2:
                    continue

                filename, labels_str = parts[0], parts[1]

                # Try to find the image
                img_file = None
                for ext in ['.jpg', '.png']:
                    candidate = image_base / filename
                    if candidate.exists():
                        img_file = candidate
                        break

                if img_file and img_file.exists():
                    image = np.array(Image.open(img_file).convert('RGB'))
                    label = np.array([int(x) for x in labels_str.split(',')])

                    samples.append({
                        'name': Path(filename).stem,
                        'image': image,
                        'label': label
                    })

    return samples


def main():
    parser = argparse.ArgumentParser(
        description="数据增强Pipeline配置（Albumentations）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 生成可视化示例
    python datasets/tools/augmentation.py --task segmentation --visualize

    # 生成增强配置文件
    python datasets/tools/augmentation.py --task classification --generate-config

    # 少数类专项增强
    python datasets/tools/augmentation.py --minority-only --augment-count 10
        """
    )

    parser.add_argument(
        "--task",
        type=str,
        choices=["segmentation", "classification", "both"],
        default="both",
        help="任务类型"
    )

    parser.add_argument(
        "--data_root",
        type=str,
        default="datasets/processed",
        help="数据集根目录"
    )

    parser.add_argument(
        "--strength",
        type=str,
        choices=["light", "medium", "heavy"],
        default="medium",
        help="增强强度"
    )

    parser.add_argument(
        "--visualize",
        action="store_true",
        help="生成增强可视化"
    )

    parser.add_argument(
        "--num_samples",
        type=int,
        default=10,
        help="可视化样本数量"
    )

    parser.add_argument(
        "--num_variants",
        type=int,
        default=9,
        help="每个样本的增强变体数量"
    )

    parser.add_argument(
        "--output_dir",
        type=str,
        default="datasets/tools/augmentation_visualization",
        help="可视化输出目录"
    )

    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="生成增强配置YAML文件"
    )

    parser.add_argument(
        "--config_output",
        type=str,
        default="datasets/tools/augmentation_config.yml",
        help="配置文件输出路径"
    )

    parser.add_argument(
        "--minority-only",
        action="store_true",
        help="仅处理少数类样本"
    )

    parser.add_argument(
        "--augment-count",
        type=int,
        default=5,
        help="少数类每个样本的增强次数"
    )

    parser.add_argument(
        "--image-size",
        type=int,
        nargs=2,
        default=[512, 512],
        help="目标图像尺寸 (H W)"
    )

    args = parser.parse_args()

    # Parse arguments
    task_type = TaskType(args.task) if args.task != "both" else None
    strength = AugmentationStrength(args.strength)
    image_size = tuple(args.image_size)

    # Generate config file
    if args.generate_config:
        config_data = {
            'segmentation': {
                'strength': args.strength,
                'image_size': args.image_size,
                'augmentations': SegmentationAugmentationPipeline.AUGMENTATION_PRESETS[strength]
            },
            'classification': {
                'strength': args.strength,
                'image_size': args.image_size,
                'cutmix_prob': SegmentationAugmentationPipeline.AUGMENTATION_PRESETS[strength].get('cutmix_prob', 0.2),
                'mixup_prob': SegmentationAugmentationPipeline.AUGMENTATION_PRESETS[strength].get('mixup_prob', 0.1),
                'augmentations': ClassificationAugmentationPipeline.AUGMENTATION_PRESETS[strength]
            },
            'minority_classes': {
                'enabled': True,
                'classes': MinorityClassAugmentation.MINORITY_CLASSES,
                'augment_multiplier': args.augment_count
            },
            'lab_color_space': {
                'enabled': True,
                'description': 'Lab颜色空间增强，更符合人眼感知，适合舌诊图像'
            }
        }

        import yaml
        config_path = Path(args.config_output)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Generated config file: {config_path}")

    # Visualize augmentations
    if args.visualize:
        visualizer = AugmentationVisualizer(args.output_dir)
        config = AugmentationConfig(
            task_type=TaskType.SEGMENTATION,
            strength=strength,
            image_size=image_size,
            probability=1.0
        )

        tasks_to_process = []
        if args.task == "both":
            tasks_to_process = [(TaskType.SEGMENTATION, "seg_v1"), (TaskType.CLASSIFICATION, "clas_v1")]
        else:
            data_subdir = "seg_v1" if args.task == "segmentation" else "clas_v1"
            tasks_to_process = [(task_type, data_subdir)]

        for task_type, data_subdir in tasks_to_process:
            logger.info(f"Processing {task_type.value} task...")

            config.task_type = task_type
            data_path = Path(args.data_root) / data_subdir

            samples = load_sample_images(str(data_path), task_type, args.num_samples)

            if not samples:
                logger.warning(f"No samples found for {task_type.value} task in {data_path}")
                continue

            logger.info(f"Loaded {len(samples)} samples")

            for sample in tqdm(samples, desc=f"Generating {task_type.value} visualizations"):
                if task_type == TaskType.SEGMENTATION:
                    if sample['mask'] is None:
                        continue

                    pipeline = SegmentationAugmentationPipeline(config)

                    # Generate augmented samples
                    augmented = []
                    for _ in range(args.num_variants):
                        aug_result = pipeline(sample['image'].copy(), sample['mask'].copy())
                        augmented.append(aug_result)

                    # Visualize
                    output_path = visualizer.visualize_segmentation_augmentations(
                        sample['image'],
                        sample['mask'],
                        augmented,
                        sample['name'],
                        args.num_variants
                    )
                    logger.info(f"Saved segmentation visualization: {output_path}")

                elif task_type == TaskType.CLASSIFICATION:
                    pipeline = ClassificationAugmentationPipeline(config)

                    # Generate augmented samples
                    augmented = []
                    for _ in range(args.num_variants):
                        aug_image = pipeline(sample['image'].copy(), training=True)
                        augmented.append(aug_image)

                    # Visualize
                    output_path = visualizer.visualize_classification_augmentations(
                        sample['image'],
                        augmented,
                        sample['name'],
                        args.num_variants
                    )
                    logger.info(f"Saved classification visualization: {output_path}")

        logger.info(f"Visualizations saved to: {args.output_dir}")

    logger.info("=" * 60)
    logger.info("Augmentation Pipeline Configuration Summary:")
    logger.info(f"  Task: {args.task}")
    logger.info(f"  Strength: {args.strength}")
    logger.info(f"  Image Size: {image_size}")
    logger.info(f"  Config Generated: {args.generate_config}")
    logger.info(f"  Visualization: {args.visualize}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
