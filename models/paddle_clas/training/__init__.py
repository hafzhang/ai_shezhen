"""
Training module for PaddleClas tongue classification

This module provides:
- CurriculumLearning: Progressive training strategy
- DynamicClassWeightScheduler: Adaptive class weighting
- GradientAccumulator: Stable training with small batches
- CurriculumTrainingConfig: Complete training configuration
- train: Main training script with 60 epochs, CosineAnnealingWarmRestarts, early stopping
"""

from .curriculum_learning import (
    CurriculumScheduler,
    DynamicClassWeightScheduler,
    GradientAccumulator,
    CurriculumTrainingConfig,
    create_default_config
)

__all__ = [
    "CurriculumScheduler",
    "DynamicClassWeightScheduler",
    "GradientAccumulator",
    "CurriculumTrainingConfig",
    "create_default_config"
]
