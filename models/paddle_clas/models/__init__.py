#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PaddleClas Models Module

Exports:
    - PP_HGNetV2_B4: High-performance backbone for tongue classification
    - MultiHeadTongueModel: Complete multi-head classification model
    - MultiHeadClassifier: Multi-head classifier module
    - MultiTaskLoss: Multi-task loss function
    - HeadConfig: Head configuration dataclass
    - DEFAULT_HEAD_CONFIGS: Default head configurations for tongue diagnosis
    - create_backbone: Factory function for backbone creation
    - create_multi_head_model: Factory function for complete model creation

Author: Ralph Agent
Date: 2026-02-12
"""

# Backbone network
from models.paddle_clas.models.pphgnetv2 import (
    PP_HGNetV2_B4,
    create_backbone,
    count_parameters,
    print_model_info
)

# Multi-head classification
from models.paddle_clas.models.multi_head import (
    HeadConfig,
    DEFAULT_HEAD_CONFIGS,
    ClassificationHead,
    MultiHeadClassifier,
    MultiTaskLoss,
    MultiHeadTongueModel,
    create_multi_head_model,
    create_loss_fn,
    print_model_summary
)

__all__ = [
    # Backbone
    "PP_HGNetV2_B4",
    "create_backbone",
    "count_parameters",
    "print_model_info",

    # Multi-head
    "HeadConfig",
    "DEFAULT_HEAD_CONFIGS",
    "ClassificationHead",
    "MultiHeadClassifier",
    "MultiTaskLoss",
    "MultiHeadTongueModel",
    "create_multi_head_model",
    "create_loss_fn",
    "print_model_summary",
]
