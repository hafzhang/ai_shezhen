#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Segmentation Evaluation Module

Comprehensive evaluation tools for tongue segmentation models.

Components:
- SegmentationEvaluator: Main evaluator for generating reports
- BoundaryMetrics: Boundary F1 score calculation
- ErrorAnalyzer: Error case categorization and analysis
- EvaluationResult: Data class for evaluation results

Usage:
    from models.paddle_seg.evaluation import SegmentationEvaluator

    evaluator = SegmentationEvaluator(num_classes=2)
    results = evaluator.evaluate(model, test_loader)
    report_path = evaluator.generate_report(results)
"""

from .segmentation_evaluator import (
    SegmentationEvaluator,
    BoundaryMetrics,
    ErrorAnalyzer,
    EvaluationResult,
    compute_inference_time,
)

__all__ = [
    'SegmentationEvaluator',
    'BoundaryMetrics',
    'ErrorAnalyzer',
    'EvaluationResult',
    'compute_inference_time',
]
