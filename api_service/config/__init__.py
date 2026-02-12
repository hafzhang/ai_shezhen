#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置模块

Configuration module for Celery and other services.

Author: Ralph Agent
Date: 2026-02-12
"""

from .celery_config import (
    broker_url,
    result_backend,
    task_routes,
    task_queues,
    beat_schedule,
    task_annotations,
)

__all__ = [
    "broker_url",
    "result_backend",
    "task_routes",
    "task_queues",
    "beat_schedule",
    "task_annotations",
]
