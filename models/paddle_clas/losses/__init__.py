#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi-Task Loss Functions for Tongue Diagnosis Classification

This module provides loss functions for multi-label tongue classification:
- FocalLoss: For handling class imbalance
- AsymmetricLoss: For multi-label tasks
- MultiTaskLoss: Combines losses from all heads with proper weighting

Author: Ralph Agent
Date: 2026-02-12
"""

from .focal_loss import FocalLoss
from .asymmetric_loss import AsymmetricLoss
from .multi_task_loss import MultiTaskLoss

__all__ = [
    'FocalLoss',
    'AsymmetricLoss',
    'MultiTaskLoss',
]
