#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Celery应用配置模块

Celery application configuration and setup.
Configures broker, backend, and task settings.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from celery import Celery
from celery.schedules import crontab

from api_service.core.config import settings


# Redis connection URLs
broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND


def create_celery_app() -> Celery:
    """Create and configure Celery application"""

    app = Celery(
        "shezhen_worker",
        broker=broker_url,
        backend=result_backend,
        include=[
            "api_service.worker.tasks",
        ]
    )

    # Configure Celery settings
    app.conf.update(
        # Task settings
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,

        # Task execution settings
        task_always_eager=False,  # Set to True for debugging (synchronous execution)
        task_eager_propagates=True,
        task_ignore_result=False,

        # Task timeout and retry settings
        task_soft_time_limit=settings.CELERY_TASK_TIMEOUT,
        task_time_limit=settings.CELERY_TASK_TIMEOUT + 10,
        task_acks_late=True,  # Ack after task completes (for reliability)
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # Disable prefetch for fairness

        # Task result settings
        result_expires=3600,  # Results expire after 1 hour
        result_extended=True,

        # Worker settings
        worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
        worker_max_tasks_per_child=1000,  # Recycle worker after N tasks

        # Retry settings
        task_default_max_retries=settings.CELERY_TASK_MAX_RETRIES,
        task_default_retry_delay=1,  # Delay between retries in seconds
        task_autoretry_for=(Exception,),  # Auto retry on any exception
        task_retry_backoff=True,  # Enable exponential backoff
        task_retry_backoff_max=10,  # Max backoff delay
        task_retry_jitter=True,  # Add jitter to avoid thundering herd

        # Rate limiting
        task_annotations={
            "api_service.worker.tasks.llm_diagnosis_task": {
                "rate_limit": "10/m",  # Limit LLM calls to 10 per minute
            },
        },

        # Celery Beat settings (for periodic tasks)
        beat_schedule={
            "cleanup-old-results": {
                "task": "api_service.worker.tasks.cleanup_task",
                "schedule": crontab(hour="*/6"),  # Every 6 hours
            },
        },

        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,

        # Security
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
    )

    return app


# Global Celery app instance
celery_app: Optional[Celery] = None


def get_celery_app() -> Celery:
    """Get or create Celery application instance"""
    global celery_app
    if celery_app is None:
        celery_app = create_celery_app()
    return celery_app


# Create default instance
celery_app = get_celery_app()


def get_active_task_count() -> int:
    """Get count of active tasks (for monitoring)"""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        active = inspect.active()
        if active:
            return sum(len(tasks) for tasks in active.values())
        return 0
    except Exception:
        return 0


def get_worker_stats() -> dict:
    """Get worker statistics (for health check)"""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        registered = inspect.registered()

        return {
            "workers": len(stats) if stats else 0,
            "total_tasks_processed": sum(
                s.get("total", {}).values()[0] if s.get("total") else 0
                for s in (stats.values() if stats else [])
            ),
            "registered_tasks": list(registered.values())[0] if registered else [],
        }
    except Exception as e:
        return {"error": str(e), "workers": 0}


if __name__ == "__main__":
    # For testing: print Celery app configuration
    app = get_celery_app()
    print(f"Celery broker: {broker_url}")
    print(f"Celery backend: {result_backend}")
    print(f"Registered tasks: {app.tasks}")
