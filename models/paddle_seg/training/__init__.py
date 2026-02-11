#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Training module for tongue segmentation.

This module provides:
- HardExampleMiner: Online hard example mining for selecting difficult samples
- HardExampleDataset: Dataset wrapper for augmented hard examples
- ProgressiveTrainingStrategy: Progressive training (detail branch first, then joint)

task-2-4: 难例挖掘与重训练
"""

from .hard_example_mining import (
    HardExampleMiner,
    HardExampleDataset,
    ProgressiveTrainingStrategy,
    visualize_hard_examples,
    compute_hard_example_metrics,
)

__all__ = [
    'HardExampleMiner',
    'HardExampleDataset',
    'ProgressiveTrainingStrategy',
    'visualize_hard_examples',
    'compute_hard_example_metrics',
]
