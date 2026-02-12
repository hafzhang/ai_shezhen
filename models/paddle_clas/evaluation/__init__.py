#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Classification Model Evaluation Module

Provides comprehensive evaluation tools for multi-task tongue classification:
- Multi-label evaluation metrics (mAP, F1, precision, recall)
- Confusion matrix generation and visualization
- Per-class performance analysis
- Error analysis and case studies
- Feature contribution analysis

Author: Ralph Agent
Date: 2026-02-12
Task: task-3-8 - 分类模型评估与可解释性分析
"""

from .classification_evaluator import (
    ClassificationEvaluator,
    ClassificationResult,
    ErrorAnalyzer,
    FeatureContribution,
    GradCAM
)

__all__ = [
    'ClassificationEvaluator',
    'ClassificationResult',
    'ErrorAnalyzer',
    'FeatureContribution',
    'GradCAM'
]
