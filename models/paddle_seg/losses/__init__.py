#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Loss Functions for Tongue Segmentation

Exports:
    - CombinedLoss: Main combined loss function
    - DiceLoss: Dice loss for segmentation
    - BoundaryLoss: Boundary-aware loss
    - calculate_class_weights_from_dataset: Utility for computing class weights
"""

from .combined_loss import (
    CombinedLoss,
    DiceLoss,
    BoundaryLoss,
    calculate_class_weights_from_dataset
)

__all__ = [
    'CombinedLoss',
    'DiceLoss',
    'BoundaryLoss',
    'calculate_class_weights_from_dataset'
]
