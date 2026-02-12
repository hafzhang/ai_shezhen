#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Celery异步任务队列模块

Celery worker module for background task processing.
Provides async task execution for segmentation, classification, and diagnosis.

Author: Ralph Agent
Date: 2026-02-12
"""

from .celery_app import celery_app, get_celery_app
from .tasks import (
    segment_task,
    classify_task,
    diagnosis_task,
    batch_segment_task,
    batch_classify_task,
    llm_diagnosis_task
)

__all__ = [
    "celery_app",
    "get_celery_app",
    "segment_task",
    "classify_task",
    "diagnosis_task",
    "batch_segment_task",
    "batch_classify_task",
    "llm_diagnosis_task",
]
