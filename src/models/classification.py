#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分类模型

包含 PP-HGNetV2-B4 骨干网络和多头分类器
"""

import numpy as np
import paddle
import paddle.nn as nn
import paddle.nn.functional as F


class LightConvBNReLU(nn.Layer):
    """轻量级卷积块"""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.conv1 = nn.Conv2D(in_channels, in_channels, kernel_size=1, bias_attr=False)
        self.bn1 = nn.BatchNorm2D(in_channels)
        self.conv2 = nn.Conv2D(
            in_channels, in_channels, kernel_size=kernel_size,
            padding=kernel_size // 2, groups=in_channels, bias_attr=False
        )
        self.bn2 = nn.BatchNorm2D(in_channels)
        self.conv3 = nn.Conv2D(in_channels, out_channels, kernel_size=1, bias_attr=False)
        self.bn3 = nn.BatchNorm2D(out_channels)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = F.relu(x)

        x = self.conv2(x)
        x = self.bn2(x)
        x = F.relu(x)

        x = self.conv3(x)
        x = self.bn3(x)
        x = F.relu(x)

        return x


class HG_Block(nn.Layer):
    """HGNet 基础块"""

    def __init__(self, in_channels: int, mid_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.branch0 = LightConvBNReLU(in_channels, out_channels, kernel_size)
        self.branch1 = LightConvBNReLU(in_channels, out_channels, kernel_size)
        self.branch2 = LightConvBNReLU(in_channels, out_channels, kernel_size)
        self.branch3 = LightConvBNReLU(in_channels, out_channels, kernel_size)

    def forward(self, x):
        x0 = self.branch0(x)
        x1 = self.branch1(x)
        x2 = self.branch2(x)
        x3 = self.branch3(x)

        return paddle.concat([x0, x1, x2, x3], axis=1)


class HG_Stage(nn.Layer):
    """HGNet 阶段"""

    def __init__(self, in_channels: int, mid_channels: int, out_channels: int, num_blocks: int):
        super().__init__()
        self.blocks = nn.LayerList()

        for i in range(num_blocks):
            if i == 0:
                self.blocks.append(HG_Block(in_channels, mid_channels, out_channels // 4))
            else:
                self.blocks.append(HG_Block(out_channels, mid_channels, out_channels // 4))

    def forward(self, x):
        for block in self.blocks:
            x = block(x)
        return x


class PP_HGNetV2_B4(nn.Layer):
    """PP-HGNetV2-B4 骨干网络

    轻量级图像分类骨干网络
    """

    def __init__(self, num_classes: int = 1000):
        super().__init__()

        # Stem
        self.stem = nn.Sequential(
            nn.Conv2D(3, 32, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(32),
            nn.ReLU(),
            nn.Conv2D(32, 32, kernel_size=3, stride=1, padding=1, bias_attr=False),
            nn.BatchNorm2D(32),
            nn.ReLU(),
            nn.Conv2D(32, 64, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(64),
            nn.ReLU(),
        )

        # Stage 1
        self.stage1 = nn.Sequential(
            nn.Conv2D(64, 128, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(128),
            nn.ReLU(),
            HG_Stage(128, 48, 128, num_blocks=1),
        )

        # Stage 2
        self.stage2 = nn.Sequential(
            nn.Conv2D(128, 256, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(256),
            nn.ReLU(),
            HG_Stage(256, 96, 256, num_blocks=1),
        )

        # Stage 3
        self.stage3 = nn.Sequential(
            nn.Conv2D(256, 512, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(512),
            nn.ReLU(),
            HG_Stage(512, 192, 512, num_blocks=3),
        )

        # Stage 4
        self.stage4 = nn.Sequential(
            nn.Conv2D(512, 1024, kernel_size=3, stride=2, padding=1, bias_attr=False),
            nn.BatchNorm2D(1024),
            nn.ReLU(),
            HG_Stage(1024, 384, 1024, num_blocks=2),
        )

        # Head
        self.gap = nn.AdaptiveAvgPool2D(1)
        self.fc = nn.Linear(1024, num_classes)

    def forward(self, x):
        # Stem
        x = self.stem(x)  # [B, 64, H/4, W/4]

        # Stage 1
        x = self.stage1(x)  # [B, 128, H/8, W/8]

        # Stage 2
        x = self.stage2(x)  # [B, 256, H/16, W/16]

        # Stage 3
        x = self.stage3(x)  # [B, 512, H/32, W/32]

        # Stage 4
        x = self.stage4(x)  # [B, 1024, H/32, W/32]

        # Global pooling
        x = self.gap(x)  # [B, 1024, 1, 1]
        x = paddle.flatten(x, 1)  # [B, 1024]

        # FC
        x = self.fc(x)  # [B, num_classes]

        return x


class MultiHeadClassificationModel(nn.Layer):
    """多头分类模型 - 用于舌诊多维度分类

    6个分类头：
    1. tongue_color: 舌色 (4类)
    2. coating_color: 苔色 (4类)
    3. tongue_shape: 舌形 (3类)
    4. coating_quality: 苔质 (3类)
    5. features: 特征 (4类)
    6. health: 健康状态 (2类)
    """

    def __init__(
        self,
        backbone: nn.Layer = None,
        feature_dim: int = 1024,
        head_configs: dict = None
    ):
        """
        Args:
            backbone: 骨干网络
            feature_dim: 特征维度
            head_configs: 各分类头配置
        """
        super().__init__()

        # 默认配置 - 与数据集匹配
        if head_configs is None:
            head_configs = {
                'tongue_color': 4,      # 淡白/淡红/红/紫
                'coating_color': 4,     # 白/黄/黑/花剥
                'tongue_shape': 3,      # 正常/胖大/瘦薄
                'coating_quality': 3,   # 薄/厚/腻
                'features': 4,          # 无/红点/裂纹/齿痕
                'organ': 4,             # 心肺/肝胆/脾胃/肾区
                'organ_graph': 4,        # 无/肝胆图/心肺图/肾区图
            }

        # 骨干网络
        if backbone is None:
            self.backbone = PP_HGNetV2_B4(num_classes=feature_dim)
        else:
            self.backbone = backbone

        # 特征提取层（移除最后的fc层）
        self.feature_extractor = nn.Sequential(
            nn.Linear(feature_dim, feature_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(feature_dim // 2, feature_dim // 4),
            nn.ReLU(),
            nn.Dropout(0.3),
        )

        # 多个分类头
        self.heads = nn.LayerDict()
        for head_name, num_classes in head_configs.items():
            self.heads[head_name] = nn.Linear(feature_dim // 4, num_classes)

        self.head_configs = head_configs
        self.feature_dim = feature_dim

    def forward(self, x, return_features=False):
        """
        Args:
            x: 输入图像 [B, 3, H, W]
            return_features: 是否返回特征

        Returns:
            如果 return_features=False: 各分类头的预测字典
            如果 return_features=True: (预测字典, 特征)
        """
        # 提取骨干特征
        features = self.backbone(x)

        # 特征提取
        embedding = self.feature_extractor(features)

        # 多头预测
        predictions = {}
        for head_name, head in self.heads.items():
            predictions[head_name] = head(embedding)

        if return_features:
            return predictions, embedding

        return predictions


class FocalLoss(nn.Layer):
    """Focal Loss 用于处理类别不平衡

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)

    Args:
        alpha: 平衡因子 (default: 0.25)
        gamma: 聚焦参数 (default: 2.0)
        reduction: 'mean', 'sum', 'none'
    """

    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, reduction: str = 'mean'):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):
        """
        Args:
            inputs: 预测值 [B, C]
            targets: 目标值 [B, C] (one-hot or multi-label)

        Returns:
            loss
        """
        # 确保输入在sigmoid后
        if inputs.min() < 0 or inputs.max() > 1:
            inputs = F.sigmoid(inputs)

        # 计算交叉熵
        bce = F.binary_cross_entropy(inputs, targets, reduction='none')

        # 计算p_t
        p_t = inputs * targets + (1 - inputs) * (1 - targets)

        # 计算alpha_t
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)

        # Focal Loss
        focal_loss = alpha_t * (1 - p_t) ** self.gamma * bce

        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss


class AsymmetricLoss(nn.Layer):
    """Asymmetric Loss 用于多标签分类

    专门处理正负样本不平衡

    Args:
        gamma_neg: 负样本的gamma
        gamma_pos: 正样本的gamma
        clip: 数值稳定裁剪
    """

    def __init__(self, gamma_neg: float = 4.0, gamma_pos: float = 1.0, clip: float = 0.05):
        super().__init__()
        self.gamma_neg = gamma_neg
        self.gamma_pos = gamma_pos
        self.clip = clip

    def forward(self, inputs, targets):
        """
        Args:
            inputs: 预测值 [B, C]
            targets: 目标值 [B, C]

        Returns:
            loss
        """
        # Sigmoid
        inputs = F.sigmoid(inputs)

        # Anti-symmetric
        xs_pos = inputs
        xs_neg = 1 - inputs

        # Basic BCE
        los_pos = targets * F.log(xs_pos.clip(min=self.clip))
        los_neg = (1 - targets) * F.log(xs_neg.clip(min=self.clip))

        # Asymmetric focusing
        if self.gamma_neg > 0 or self.gamma_pos > 0:
            xs_pos = xs_pos * targets
            xs_neg = xs_neg * (1 - targets)
            if self.gamma_pos > 0:
                los_pos = los_pos * (1 - xs_pos) ** self.gamma_pos
            if self.gamma_neg > 0:
                los_neg = los_neg * xs_neg ** self.gamma_neg

        loss = -(los_pos + los_neg).sum()

        return loss.mean()


def calculate_class_weights(distribution: dict) -> dict:
    """
    根据类别分布计算权重

    weight = 1 / sqrt(count)

    Args:
        distribution: 类别分布 {类别名: 数量}

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


if __name__ == "__main__":
    # 测试模型
    model = MultiHeadClassificationModel()
    print(f"Total parameters: {sum(p.numel().numpy() for p in model.parameters()):,}")

    # 测试前向传播
    x = paddle.randn([2, 3, 224, 224])
    outputs = model(x)

    print("\nMultiHeadClassificationModel created:")
    for head_name, logits in outputs.items():
        print(f"  {head_name}: {logits.shape}")

    # 测试损失
    targets = {
        head: paddle.randint(0, 2, logits.shape) for head, logits in outputs.items()
    }

    focal_loss = FocalLoss()
    total_loss = 0
    for head_name in outputs.keys():
        loss = focal_loss(outputs[head_name], targets[head_name])
        total_loss += loss
        print(f"  {head_name} loss: {loss.item():.4f}")

    print(f"\nTotal loss: {total_loss.item():.4f}")
