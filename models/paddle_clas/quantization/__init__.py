#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Classification Model Quantization Module

Provides FP16 and INT8 quantization for PP-HGNetV2-B4 multi-label
classification models.

Classes:
    - ClassificationQuantizer: Main quantization class
    - QuantizationConfig: Configuration for quantization

Functions:
    - create_model(): Create a new classification model
    - PP_HGNetV2_B4: Backbone network
    - MultiHeadClassificationModel: Multi-head classifier

Usage:
    from models.paddle_clas.quantization import ClassificationQuantizer, QuantizationConfig

    config = QuantizationConfig()
    quantizer = ClassificationQuantizer(config)
    report = quantizer.quantize_fp16(model_path, output_path)
"""

from .quantize_model import (
    ClassificationQuantizer,
    QuantizationConfig,
    create_model,
    PP_HGNetV2_B4,
    MultiHeadClassificationModel,
    CalibrationDataset
)

__all__ = [
    "ClassificationQuantizer",
    "QuantizationConfig",
    "create_model",
    "PP_HGNetV2_B4",
    "MultiHeadClassificationModel",
    "CalibrationDataset"
]

__version__ = "1.0.0"
__author__ = "Ralph Agent"
__date__ = "2026-02-12"
