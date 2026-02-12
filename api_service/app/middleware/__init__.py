#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API中间件模块

Middleware components for rate limiting, circuit breaking, and request handling.

Author: Ralph Agent
Date: 2026-02-12
"""

from api_service.app.middleware.rate_limiter import (
    RateLimiter,
    TokenBucketRateLimiter,
    RateLimitError,
    get_rate_limiter,
    rate_limit_dependency
)

from api_service.app.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    get_circuit_breaker,
    circuit_breaker_dependency,
    get_circuit_breaker_states
)

from api_service.app.middleware.retry import (
    RetryConfig,
    RetryStats,
    retry_with_exponential_backoff,
    retry_decorator,
    RetryableHTTPClient,
    get_global_retry_stats
)

from api_service.app.middleware.prometheus_metrics import (
    PrometheusMiddleware,
    metrics_endpoint,
    track_segmentation,
    track_classification,
    track_diagnosis,
    track_wenxin_api,
    track_cache_hit,
    track_cache_miss,
    update_cache_size,
    update_model_status,
    update_redis_status,
    update_circuit_breaker_state,
    increment_circuit_breaker_failures,
    track_endpoint,
    # Prometheus metrics for direct access
    http_requests_total,
    http_request_duration_seconds,
    segmentation_requests_total,
    classification_requests_total,
    diagnosis_requests_total,
    wenxin_api_requests_total,
    cache_hits_total,
    cache_misses_total,
)

__all__ = [
    "RateLimiter",
    "TokenBucketRateLimiter",
    "RateLimitError",
    "get_rate_limiter",
    "rate_limit_dependency",
    "CircuitBreaker",
    "CircuitBreakerState",
    "CircuitBreakerOpenError",
    "get_circuit_breaker",
    "circuit_breaker_dependency",
    "get_circuit_breaker_states",
    "RetryConfig",
    "RetryStats",
    "retry_with_exponential_backoff",
    "retry_decorator",
    "RetryableHTTPClient",
    "get_global_retry_stats",
    # Prometheus exports
    "PrometheusMiddleware",
    "metrics_endpoint",
    "track_segmentation",
    "track_classification",
    "track_diagnosis",
    "track_wenxin_api",
    "track_cache_hit",
    "track_cache_miss",
    "update_cache_size",
    "update_model_status",
    "update_redis_status",
    "update_circuit_breaker_state",
    "increment_circuit_breaker_failures",
    "track_endpoint",
]
