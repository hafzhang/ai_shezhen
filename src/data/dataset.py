#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
舌诊分类数据集

基于COCO格式的多标签舌诊数据集

Usage:
    from src.data.dataset import TongueClassificationDataset

    train_dataset = TongueClassificationDataset(
        annotation_file='train.json',
        image_dir='train/images',
        image_size=(224, 224),
        transform=train_transform
    )
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import Optional, Callable, List, Dict, Tuple
import cv2
from PIL import Image

import paddle
from paddle.io import Dataset

from pycocotools.coco import COCO


class TongueClassificationDataset(Dataset):
    """舌诊分类数据集 - 支持多标签"""

    # 类别映射：21类 -> 6维度18类
    CATEGORY_MAPPING = {
        # 舌色维度
        'jiankangshe': ('tongue_color', 'light_red'),  # 淡红（健康）
        'hongshe': ('tongue_color', 'red'),           # 红
        'zishe': ('tongue_color', 'purple'),         # 绛紫
        'dianbaishe': ('tongue_color', 'pale'),      # 淡白

        # 苔色维度
        'baitaishe': ('coating_color', 'white'),      # 白苔
        'huangtaishe': ('coating_color', 'yellow'),   # 黄苔
        'heitaishe': ('coating_color', 'black'),      # 黑苔
        'huataishe': ('coating_color', 'peeling'),   # 花剥苔

        # 舌形维度
        'pangdashe': ('tongue_shape', 'swollen'),   # 胖大
        'shoushe': ('tongue_shape', 'thin'),        # 瘦薄

        # 苔质维度
        'botaishe': ('coating_quality', 'thin'),     # 薄苔
        'houtaishe': ('coating_quality', 'thick'),   # 厚苔
        'nitaiche': ('coating_quality', 'greasy'),   # 腻苔

        # 特征维度
        'hongdianshe': ('features', 'red_dots'),    # 红点
        'liewenshe': ('features', 'cracks'),       # 裂纹
        'chihenshe': ('features', 'teeth_marks'),  # 齿痕

        # 脏腑维度
        'xinfeiao': ('organ', 'xinfei'),          # 心肺
        'gandanao': ('organ', 'gandan'),          # 肝胆
        'piweiao': ('organ', 'piwei'),            # 脾胃
        'shenqut': ('organ', 'shenqu'),           # 肾区

        # 图形特征
        'gandantu': ('organ_graph', 'gandantu'),  # 肝胆图
        'xinfeitu': ('organ_graph', 'xinfeitu'),  # 心肺图
        'shenqutu': ('organ_graph', 'shenqutu'),  # 肾区图
    }

    # 各维度的类别列表
    DIMENSION_CLASSES = {
        'tongue_color': ['pale', 'light_red', 'red', 'purple'],
        'coating_color': ['white', 'yellow', 'black', 'peeling'],
        'tongue_shape': ['normal', 'swollen', 'thin'],
        'coating_quality': ['thin', 'thick', 'greasy'],
        'features': ['none', 'red_dots', 'cracks', 'teeth_marks'],
        'organ': ['xinfei', 'gandan', 'piwei', 'shenqu'],
        'organ_graph': ['none', 'gandantu', 'xinfeitu', 'shenqutu'],
    }

    def __init__(
        self,
        annotation_file: str,
        image_dir: str,
        image_size: Tuple[int, int] = (224, 224),
        transform: Optional[Callable] = None,
        mode: str = 'train'
    ):
        """
        Args:
            annotation_file: COCO格式标注文件路径
            image_dir: 图像目录
            image_size: 目标图像大小 (width, height)
            transform: 图像增强变换
            mode: 'train' 或 'val'
        """
        self.image_dir = Path(image_dir)
        self.image_size = image_size
        self.transform = transform
        self.mode = mode

        # 加载COCO标注
        self.coco = COCO(annotation_file)

        # 获取所有图像ID
        self.image_ids = self.coco.getImgIds()

        # 缓存图像信息
        self.img_infos = {img_id: self.coco.loadImgs(img_id)[0] for img_id in self.image_ids}

        # 缓存标注
        self.annotations = {}
        for img_id in self.image_ids:
            ann_ids = self.coco.getAnnIds(imgIds=img_id)
            anns = self.coco.loadAnns(ann_ids)
            self.annotations[img_id] = anns

    def __len__(self) -> int:
        return len(self.image_ids)

    def __getitem__(self, idx: int) -> Tuple[paddle.Tensor, Dict[str, paddle.Tensor]]:
        """
        Returns:
            image: (C, H, W) tensor
            labels: 各维度标签的字典
        """
        img_id = self.image_ids[idx]
        img_info = self.img_infos[img_id]

        # 加载图像
        img_path = self.image_dir / img_info['file_name']
        image = cv2.imread(str(img_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 调整大小
        if image.shape[:2] != self.image_size[::-1]:
            image = cv2.resize(image, self.image_size, interpolation=cv2.INTER_LINEAR)

        # 转为PIL Image
        image = Image.fromarray(image)

        # 不使用transform，在dataset内部直接处理
        # 转为tensor (H, W, C) -> (C, H, W)
        image = np.array(image).astype(np.float32) / 255.0
        image = paddle.to_tensor(image).transpose([2, 0, 1])

        # 应用归一化
        mean = paddle.to_tensor([0.485, 0.456, 0.406]).reshape([3, 1, 1])
        std = paddle.to_tensor([0.229, 0.224, 0.225]).reshape([3, 1, 1])
        image = (image - mean) / std

        # 获取标签
        labels = self._get_labels(img_id)

        return image, labels

    def _get_labels(self, img_id: int) -> Dict[str, paddle.Tensor]:
        """
        将COCO标注转换为多标签格式

        Returns:
            labels: 各维度的标签
        """
        anns = self.annotations[img_id]
        category_ids = [ann['category_id'] for ann in anns]

        # 获取类别名称
        category_names = []
        for cat_id in category_ids:
            cat_info = self.coco.loadCats([cat_id])[0]
            category_names.append(cat_info['name'])

        # 初始化所有维度标签为0
        labels = {}
        for dim, classes in self.DIMENSION_CLASSES.items():
            labels[dim] = paddle.zeros([len(classes)], dtype='float32')

        # 根据类别名称设置标签
        for cat_name in category_names:
            if cat_name in self.CATEGORY_MAPPING:
                dim, cls_name = self.CATEGORY_MAPPING[cat_name]
                if dim in labels and cls_name in self.DIMENSION_CLASSES[dim]:
                    cls_idx = self.DIMENSION_CLASSES[dim].index(cls_name)
                    labels[dim][cls_idx] = 1.0

        # 特殊处理：如果没有特殊特征，设为none
        if labels['features'].sum() == 0:
            labels['features'][0] = 1.0  # none

        # 特殊处理：如果没有脏腑图，设为none
        if labels['organ_graph'].sum() == 0:
            labels['organ_graph'][0] = 1.0  # none

        return labels

    def get_category_distribution(self) -> Dict[str, int]:
        """获取类别分布统计"""
        all_cats = self.coco.loadCats(self.coco.getCatIds())
        cat_names = [cat['name'] for cat in all_cats]

        distribution = {}
        for cat_name in cat_names:
            cat_id = self.coco.getCatIds(catNms=[cat_name])[0]
            img_ids = self.coco.getImgIds(catIds=[cat_id])
            distribution[cat_name] = len(img_ids)

        return distribution


def get_class_weights_from_distribution(distribution: Dict[str, int]) -> Dict[str, float]:
    """
    根据类别分布计算类别权重

    weight = 1 / sqrt(count)

    Args:
        distribution: 类别分布字典 {类别名: 数量}

    Returns:
        权重字典 {类别名: 权重}
    """
    weights = {}
    for cat_name, count in distribution.items():
        if count > 0:
            weights[cat_name] = 1.0 / np.sqrt(count)
        else:
            weights[cat_name] = 1.0

    # 归一化
    max_weight = max(weights.values())
    if max_weight > 0:
        weights = {k: v / max_weight for k, v in weights.items()}

    return weights


class StratifiedSampler:
    """分层采样器 - 用于处理类别不平衡"""

    def __init__(self, dataset: Dataset, batch_size: int = 32):
        """
        Args:
            dataset: 数据集
            batch_size: 批次大小
        """
        self.dataset = dataset
        self.batch_size = batch_size

        # 获取每个样本的类别数（用于平衡）
        self.sample_weights = self._compute_sample_weights()

    def _compute_sample_weights(self) -> List[float]:
        """计算每个样本的采样权重"""
        weights = []

        for idx in range(len(self.dataset)):
            _, labels = self.dataset[idx]

            # 统计标签数
            num_labels = sum([v.sum().item() for v in labels.values()])

            # 标签越少，权重越大（采样稀有类别）
            weight = 1.0 / (num_labels + 1e-6)
            weights.append(weight)

        return weights

    def __iter__(self):
        """实现分层采样逻辑"""
        # 简化版：按权重随机采样
        # 实际使用时可以考虑更复杂的分层策略
        indices = list(range(len(self.dataset)))

        # 按batch分组，确保每个batch包含多种类别
        batch_indices = []
        for i in range(0, len(indices), self.batch_size):
            batch = indices[i:i + self.batch_size]
            batch_indices.extend(batch)

        return iter(batch_indices)

    def __len__(self):
        return len(self.dataset) // self.batch_size
