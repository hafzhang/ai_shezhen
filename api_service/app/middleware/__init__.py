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
]
