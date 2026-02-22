#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prometheus监控指标模块

Prometheus metrics exporter for FastAPI application.
Provides HTTP request metrics, business metrics, and system metrics.

Author: Ralph Agent
Date: 2026-02-12
"""

import time
import logging
from typing import Callable, Optional
from functools import wraps

from fastapi import Request, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    multiprocess,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Registry
# ============================================================================
# Use multiprocess registry for uwsgi/gunicorn workers
# Note: prometheus_client.multiprocess.is_multiprocess was removed in newer versions
# We'll use environment variable to check if multiprocess mode is enabled
import os
if os.environ.get('prometheus_multiproc_dir'):
    registry = CollectorRegistry()
else:
    registry = None  # Use default registry


# ============================================================================
# HTTP Request Metrics
# ============================================================================
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0),
    registry=registry
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=registry
)

http_response_size_bytes = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
    registry=registry
)


# ============================================================================
# Business Metrics - Model Inference
# ============================================================================
segmentation_requests_total = Counter(
    "segmentation_requests_total",
    "Total segmentation inference requests",
    ["status"],  # success, error
    registry=registry
)

segmentation_inference_duration_seconds = Histogram(
    "segmentation_inference_duration_seconds",
    "Segmentation inference latency",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=registry
)

classification_requests_total = Counter(
    "classification_requests_total",
    "Total classification inference requests",
    ["status"],
    registry=registry
)

classification_inference_duration_seconds = Histogram(
    "classification_inference_duration_seconds",
    "Classification inference latency",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5),
    registry=registry
)

diagnosis_requests_total = Counter(
    "diagnosis_requests_total",
    "Total diagnosis requests",
    ["type", "status"],  # type: llm, rule_based, end_to_end
    registry=registry

)

diagnosis_duration_seconds = Histogram(
    "diagnosis_duration_seconds",
    "Total diagnosis latency",
    ["type"],  # llm, rule_based, end_to_end
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=registry
)


# ============================================================================
# Business Metrics - LLM API
# ============================================================================
wenxin_api_requests_total = Counter(
    "wenxin_api_requests_total",
    "Total Wenxin API calls",
    ["status"],  # success, error, timeout
    registry=registry
)

wenxin_api_duration_seconds = Histogram(
    "wenxin_api_duration_seconds",
    "Wenxin API call latency",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=registry
)

wenxin_api_cost_total = Counter(
    "wenxin_api_cost_total",
    "Total Wenxin API cost in CNY",
    ["model"],  # ERNIE-Speed, etc.
    registry=registry
)

wenxin_api_tokens_total = Counter(
    "wenxin_api_tokens_total",
    "Total Wenxin API tokens consumed",
    ["type"],  # input, output
    registry=registry
)


# ============================================================================
# Business Metrics - Cache
# ============================================================================
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_type"],  # segment, classify, diagnosis
    registry=registry
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_type"],
    registry=registry
)

cache_size_items = Gauge(
    "cache_size_items",
    "Current cache size in items",
    ["cache_type"],
    registry=registry
)


# ============================================================================
# Business Metrics - Celery
# ============================================================================
celery_task_received_total = Counter(
    "celery_task_received_total",
    "Total Celery tasks received",
    ["task_name", "queue"],
    registry=registry
)

celery_task_started_total = Counter(
    "celery_task_started_total",
    "Total Celery tasks started",
    ["task_name", "queue"],
    registry=registry
)

celery_task_succeeded_total = Counter(
    "celery_task_succeeded_total",
    "Total Celery tasks succeeded",
    ["task_name", "queue"],
    registry=registry
)

celery_task_failed_total = Counter(
    "celery_task_failed_total",
    "Total Celery tasks failed",
    ["task_name", "queue", "exception"],
    registry=registry
)

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration",
    ["task_name", "queue"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
    registry=registry
)

celery_queue_length = Gauge(
    "celery_queue_length",
    "Current queue length",
    ["queue"],
    registry=registry
)

celery_active_tasks_count = Gauge(
    "celery_active_tasks_count",
    "Number of active tasks",
    registry=registry
)

celery_worker_concurrency = Gauge(
    "celery_worker_concurrency",
    "Worker concurrency limit",
    registry=registry
)


# ============================================================================
# System Metrics
# ============================================================================
model_loaded = Gauge(
    "model_loaded",
    "Model loaded status (1=loaded, 0=not loaded)",
    ["model_type"],  # segmentation, classification, pipeline
    registry=registry
)

redis_connection_status = Gauge(
    "redis_connection_status",
    "Redis connection status (1=connected, 0=disconnected)",
    registry=registry
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["name"],
    registry=registry

)

circuit_breaker_failure_count = Counter(
    "circuit_breaker_failure_count",
    "Circuit breaker failure count",
    ["name"],
    registry=registry
)


# ============================================================================
# Middleware
# ============================================================================
class PrometheusMiddleware:
    """FastAPI middleware for Prometheus metrics collection"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract method and path
        method = scope["method"]
        path = scope["path"]

        # Normalize path (replace IDs with placeholders)
        normalized_path = self._normalize_path(path)

        # Track in-progress requests
        http_requests_in_progress.labels(
            method=method,
            endpoint=normalized_path
        ).inc()

        start_time = time.time()

        # Wrapper for send to capture status code
        status_code = 200
        response_size = 0

        async def send_wrapper(message):
            nonlocal status_code, response_size
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                if "body" in message and message["body"]:
                    response_size = len(message["body"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            status_code = 500
            logger.error(f"Request error: {e}")
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time

            http_requests_total.labels(
                method=method,
                endpoint=normalized_path,
                status=str(status_code)
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=normalized_path
            ).observe(duration)

            http_response_size_bytes.labels(
                method=method,
                endpoint=normalized_path
            ).observe(response_size)

            http_requests_in_progress.labels(
                method=method,
                endpoint=normalized_path
            ).dec()

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing dynamic segments with placeholders"""
        # Skip metrics endpoint itself
        if path == "/metrics":
            return "/metrics"

        # Skip health check
        if path in ["/health", "/api/v1/health"]:
            return "/health"

        # Skip docs
        if path in ["/docs", "/redoc", "/openapi.json"]:
            return path

        # API v1 endpoints
        if path.startswith("/api/v1/"):
            parts = path.split("/")
            if len(parts) > 4:
                # Replace ID parameters
                return "/".join(parts[:4]) + "/{id}"
            return path

        # Static files
        if path.startswith("/static/"):
            return "/static/{file}"

        return path


# ============================================================================
# Metrics Endpoint
# ============================================================================
async def metrics_endpoint() -> Response:
    """FastAPI endpoint that returns Prometheus metrics"""
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
        headers={"Content-Type": CONTENT_TYPE_LATEST}
    )


# ============================================================================
# Helper Functions
# ============================================================================
def track_segmentation(status: str, duration: float):
    """Track segmentation inference metrics"""
    segmentation_requests_total.labels(status=status).inc()
    segmentation_inference_duration_seconds.observe(duration)


def track_classification(status: str, duration: float):
    """Track classification inference metrics"""
    classification_requests_total.labels(status=status).inc()
    classification_inference_duration_seconds.observe(duration)


def track_diagnosis(diagnosis_type: str, status: str, duration: float):
    """Track diagnosis metrics"""
    diagnosis_requests_total.labels(type=diagnosis_type, status=status).inc()
    diagnosis_duration_seconds.labels(type=diagnosis_type).observe(duration)


def track_wenxin_api(status: str, duration: float, cost: float = 0, input_tokens: int = 0, output_tokens: int = 0):
    """Track Wenxin API call metrics"""
    wenxin_api_requests_total.labels(status=status).inc()
    wenxin_api_duration_seconds.observe(duration)
    if cost > 0:
        wenxin_api_cost_total.labels(model="ERNIE-Speed").inc(cost)
    if input_tokens > 0:
        wenxin_api_tokens_total.labels(type="input").inc(input_tokens)
    if output_tokens > 0:
        wenxin_api_tokens_total.labels(type="output").inc(output_tokens)


def track_cache_hit(cache_type: str):
    """Track cache hit"""
    cache_hits_total.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str):
    """Track cache miss"""
    cache_misses_total.labels(cache_type=cache_type).inc()


def update_cache_size(cache_type: str, size: int):
    """Update cache size gauge"""
    cache_size_items.labels(cache_type=cache_type).set(size)


def update_model_status(model_type: str, loaded: bool):
    """Update model loaded status"""
    model_loaded.labels(model_type=model_type).set(1 if loaded else 0)


def update_redis_status(connected: bool):
    """Update Redis connection status"""
    redis_connection_status.set(1 if connected else 0)


def update_circuit_breaker_state(name: str, state: str):
    """Update circuit breaker state"""
    state_map = {"closed": 0, "open": 1, "half_open": 2}
    circuit_breaker_state.labels(name=name).set(state_map.get(state, 0))


def increment_circuit_breaker_failures(name: str):
    """Increment circuit breaker failure count"""
    circuit_breaker_failure_count.labels(name=name).inc()


# ============================================================================
# Decorators for tracking function calls
# ============================================================================
def track_endpoint(endpoint_name: str = None):
    """Decorator to track endpoint metrics"""
    def decorator(func: Callable) -> Callable:
        name = endpoint_name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                logger.error(f"Endpoint {name} error: {e}")
                raise
            finally:
                duration = time.time() - start_time
                http_requests_total.labels(
                    method="POST",
                    endpoint=name,
                    status=status
                ).inc()
                http_request_duration_seconds.labels(
                    method="POST",
                    endpoint=name
                ).observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                logger.error(f"Endpoint {name} error: {e}")
                raise
            finally:
                duration = time.time() - start_time
                http_requests_total.labels(
                    method="POST",
                    endpoint=name,
                    status=status
                ).inc()
                http_request_duration_seconds.labels(
                    method="POST",
                    endpoint=name
                ).observe(duration)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
