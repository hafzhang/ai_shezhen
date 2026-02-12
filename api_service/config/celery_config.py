#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Celery配置文件

Celery worker and beat configuration settings.
Defines task queues, schedules, and worker behavior.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
from pathlib import Path
from celery.schedules import crontab

from api_service.core.config import settings


# ============================================================================
# Broker & Backend Configuration
# ============================================================================

# Redis connection URLs
broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND


# ============================================================================
# Task Settings
# ============================================================================

task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "Asia/Shanghai"
enable_utc = True

# Task execution
task_always_eager = False  # Set to True for synchronous debugging
task_eager_propagates = True
task_ignore_result = False

# Task timeouts (seconds)
task_soft_time_limit = settings.CELERY_TASK_TIMEOUT
task_time_limit = settings.CELERY_TASK_TIMEOUT + 10

# Task reliability
task_acks_late = True  # Ack after task completes
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1  # Disable prefetch for fairness

# Result settings
result_expires = 3600  # Results expire after 1 hour
result_extended = True

# Worker settings
worker_concurrency = settings.CELERY_WORKER_CONCURRENCY
worker_max_tasks_per_child = 1000
worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# ============================================================================
# Retry Settings
# ============================================================================

task_default_max_retries = settings.CELERY_TASK_MAX_RETRIES
task_default_retry_delay = 1  # seconds
task_autoretry_for = (Exception,)  # Auto retry on any exception
task_retry_backoff = True  # Enable exponential backoff
task_retry_backoff_max = 10  # Max backoff delay in seconds
task_retry_jitter = True  # Add jitter to avoid thundering herd

# ============================================================================
# Task Annotations (Rate Limits, Options)
# ============================================================================

task_annotations = {
    # Rate limit LLM calls to control API costs
    "api_service.worker.tasks.llm_diagnosis_task": {
        "rate_limit": "10/m",  # 10 tasks per minute
        "time_limit": 30,  # 30 second hard limit
    },
    # Batch tasks have higher limits
    "api_service.worker.tasks.batch_segment_task": {
        "time_limit": 120,  # 2 minutes
    },
    "api_service.worker.tasks.batch_classify_task": {
        "time_limit": 120,  # 2 minutes
    },
}

# ============================================================================
# Task Queues
# ============================================================================

task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "segmentation": {
        "exchange": "segmentation",
        "routing_key": "segmentation",
    },
    "classification": {
        "exchange": "classification",
        "routing_key": "classification",
    },
    "diagnosis": {
        "exchange": "diagnosis",
        "routing_key": "diagnosis",
    },
    "llm": {
        "exchange": "llm",
        "routing_key": "llm",
    },
}

task_default_queue = "default"
task_default_exchange = "default"
task_default_routing_key = "default"

# ============================================================================
# Task Routes
# ============================================================================

task_routes = {
    "api_service.worker.tasks.segment_task": {"queue": "segmentation"},
    "api_service.worker.tasks.batch_segment_task": {"queue": "segmentation"},
    "api_service.worker.tasks.classify_task": {"queue": "classification"},
    "api_service.worker.tasks.batch_classify_task": {"queue": "classification"},
    "api_service.worker.tasks.diagnosis_task": {"queue": "diagnosis"},
    "api_service.worker.tasks.llm_diagnosis_task": {"queue": "llm"},
    "api_service.worker.tasks.cleanup_task": {"queue": "default"},
}

# ============================================================================
# Celery Beat Schedule (Periodic Tasks)
# ============================================================================

beat_schedule = {
    # Cleanup old task results every 6 hours
    "cleanup-old-results": {
        "task": "api_service.worker.tasks.cleanup_task",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
    },
    # Health check every minute
    "health-check": {
        "task": "api_service.worker.tasks.health_check_task",
        "schedule": crontab(minute="*"),  # Every minute
    },
}

# ============================================================================
# Monitoring & Events
# ============================================================================

worker_send_task_events = True
task_send_sent_event = True

# ============================================================================
# Security & Connection
# ============================================================================

broker_connection_retry_on_startup = True
broker_connection_retry = True
broker_connection_max_retries = 10
broker_connection_timeout = 5

# ============================================================================
# Task Tracking
# ============================================================================

task_track_started = True
task_send_sent_event = True


# ============================================================================
# Worker Optimization
# ============================================================================

# Disable prefetch for better task distribution
worker_prefetch_multiplier = 1

# Recycle workers periodically to prevent memory leaks
worker_max_tasks_per_child = 1000

# Enable optimization for CPU-bound tasks
worker_pool = "prefork"
worker_pool_restarts = True


# ============================================================================
# Development Settings
# ============================================================================

# Enable task events for monitoring (Flower)
worker_send_task_events = os.getenv("CELERY_SEND_EVENTS", "true").lower() == "true"

# Result backend
result_backend_transport_options = {
    "retry_policy": {
        "timeout": 5.0,
        "max_retries": 3,
    },
}
