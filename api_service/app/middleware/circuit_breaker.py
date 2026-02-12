#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API熔断器中间件 - Circuit Breaker Pattern

Circuit breaker for external service calls (LLM API, database, etc.).
Prevents cascading failures and provides fallback behavior.

Author: Ralph Agent
Date: 2026-02-12
"""

import time
import asyncio
from enum import Enum
from typing import Optional, Dict, Any, Callable, TypeVar, Tuple
from datetime import datetime, timedelta
import logging

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

logger = logging.getLogger(__name__)


T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    def __init__(self, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        super().__init__("Circuit breaker is open")


class CircuitBreakerConfig:
    """Circuit breaker configuration"""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        half_open_max_calls: int = 3,
        half_open_timeout: int = 30,
        exceptions: tuple = (httpx.HTTPError, ConnectionError, TimeoutError),
        exclude_exceptions: tuple = ()
    ):
        """
        Initialize circuit breaker config

        Args:
            failure_threshold: Failures before opening circuit (default: 5)
            success_threshold: Successes before closing circuit (default: 2)
            timeout: Seconds before attempting recovery (default: 60)
            half_open_max_calls: Max calls in half-open state (default: 3)
            half_open_timeout: Timeout for half-open calls (default: 30)
            exceptions: Exception types that count as failures
            exclude_exceptions: Exceptions that don't count as failures
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        self.half_open_timeout = half_open_timeout
        self.exceptions = exceptions
        self.exclude_exceptions = exclude_exceptions


class CircuitBreaker:
    """
    Circuit breaker implementation

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit tripped, requests fail fast
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker

        Args:
            name: Circuit breaker name for logging/metrics
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        # State tracking
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

        # Timing
        self.last_failure_time: Optional[float] = None
        self.last_state_change: Optional[float] = None

        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0

        logger.info(f"Circuit breaker '{name}' initialized: {self.state.value}")

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.timeout

    def _record_success(self):
        """Record a successful call"""
        self.success_count += 1
        self.total_successes += 1
        self.last_state_change = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                # Close circuit after enough successes
                logger.info(f"Circuit breaker '{self.name}' closing after {self.success_count} successes")
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_calls = 0
            else:
                logger.debug(f"Circuit breaker '{self.name}' half-open success: {self.success_count}/{self.config.success_threshold}")
        else:
            # Reset failure count in closed state
            self.failure_count = 0

    def _record_failure(self, exception: Exception):
        """Record a failed call"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        self.last_state_change = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Immediately reopen on failure in half-open state
            logger.warning(f"Circuit breaker '{self.name}' reopening on half-open failure")
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            self.half_open_calls = 0
        elif self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                # Trip circuit
                logger.warning(
                    f"Circuit breaker '{self.name}' tripped after "
                    f"{self.failure_count} failures"
                )
                self.state = CircuitBreakerState.OPEN
                self.failure_count = 0
                self.success_count = 0

    def _is_excluded_exception(self, exception: Exception) -> bool:
        """Check if exception should be excluded from failure counting"""
        return isinstance(exception, self.config.exclude_exceptions)

    def _is_failure_exception(self, exception: Exception) -> bool:
        """Check if exception should be counted as a failure"""
        if self._is_excluded_exception(exception):
            return False
        return isinstance(exception, self.config.exceptions)

    async def call(
        self,
        func: Callable[..., T],
        *args,
        fallback: Optional[Callable[..., T]] = None,
        **kwargs
    ) -> T:
        """
        Execute function through circuit breaker

        Args:
            func: Function to call (can be sync or async)
            fallback: Fallback function if circuit is open
            *args, **kwargs: Arguments for func

        Returns:
            Result of func or fallback

        Raises:
            CircuitBreakerOpenError: If circuit is open and no fallback
            Exception: If func raises an exception
        """
        self.total_calls += 1

        # Check if circuit is open
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                # Transition to half-open to test recovery
                logger.info(f"Circuit breaker '{self.name}' transitioning to half-open")
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                self.success_count = 0
            else:
                # Circuit is still open
                retry_after = self.config.timeout - (time.time() - self.last_failure_time)
                logger.debug(f"Circuit breaker '{self.name}' is open, retry after {retry_after:.1f}s")

                # Use fallback if provided
                if fallback:
                    return await self._call_fallback(fallback, *args, **kwargs)

                raise CircuitBreakerOpenError(retry_after=retry_after)

        # Check half-open call limit
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                logger.warning(f"Circuit breaker '{self.name}' half-open call limit reached")
                if fallback:
                    return await self._call_fallback(fallback, *args, **kwargs)
                raise CircuitBreakerOpenError()

        # Execute the function
        try:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1

            result = await self._execute_function(func, *args, **kwargs)
            self._record_success()
            return result

        except Exception as e:
            if self._is_failure_exception(e):
                self._record_failure(e)

                # If circuit is now open, try fallback
                if self.state == CircuitBreakerState.OPEN and fallback:
                    return await self._call_fallback(fallback, *args, **kwargs)

                if self.state == CircuitBreakerState.OPEN:
                    raise CircuitBreakerOpenError(
                        retry_after=float(self.config.timeout)
                    ) from e
                raise
            else:
                # Non-failure exception, pass through
                raise

    async def _execute_function(self, func: Callable, *args, **kwargs):
        """Execute sync or async function"""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)

    async def _call_fallback(self, fallback: Callable, *args, **kwargs):
        """Execute fallback function"""
        logger.info(f"Circuit breaker '{self.name}' using fallback")
        if asyncio.iscoroutinefunction(fallback):
            return await fallback(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, fallback, *args, **kwargs)

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        retry_after = None
        if self.state == CircuitBreakerState.OPEN and self.last_failure_time:
            retry_after = max(0, self.config.timeout - (time.time() - self.last_failure_time))

        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "retry_after": retry_after,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": self.total_failures / self.total_calls if self.total_calls > 0 else 0
        }

    def reset(self):
        """Manually reset circuit breaker to closed state"""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time = None
        self.last_state_change = time.time()


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding circuit breaker functionality to routes

    Note: This middleware tracks failures but doesn't block requests by itself.
    The actual circuit breaking should be applied to external service calls
    using the CircuitBreaker class or circuit_breaker_dependency.
    """

    def __init__(
        self,
        app,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        super().__init__(app)
        self.circuit_breaker = circuit_breaker

    async def dispatch(self, request: Request, call_next):
        """Process request and track failures"""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log error for circuit breaker tracking
            if self.circuit_breaker:
                self.circuit_breaker._record_failure(e)
            raise


# Global circuit breakers for common services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str = "default",
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name

    Args:
        name: Circuit breaker name
        config: Configuration for new circuit breakers

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def init_circuit_breakers():
    """Initialize default circuit breakers for common services"""
    # LLM API circuit breaker
    _circuit_breakers["wenxin_api"] = CircuitBreaker(
        name="wenxin_api",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout=60,
            exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
            exclude_exceptions=(ValueError,)  # Validation errors shouldn't trip
        )
    )

    # Redis circuit breaker
    _circuit_breakers["redis"] = CircuitBreaker(
        name="redis",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout=30,
            exceptions=(ConnectionError, TimeoutError)
        )
    )

    logger.info(f"Initialized {len(_circuit_breakers)} circuit breakers")


# Circuit breaker decorator
def circuit_breaker(
    name: str = "default",
    fallback: Optional[Callable] = None,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for applying circuit breaker to a function

    Usage:
        @circuit_breaker(name="wenxin_api", fallback=fallback_handler)
        async def call_wenxin_api(prompt):
            return await wenxin_client.call(prompt)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            cb = get_circuit_breaker(name)
            try:
                return await cb.call(func, *args, fallback=fallback, **kwargs)
            except CircuitBreakerOpenError:
                if fallback:
                    return await fallback(*args, **kwargs)
                raise
        return wrapper
    return decorator


# Dependency for endpoint-level circuit breaking
async def circuit_breaker_dependency(
    breaker_name: str = "default"
):
    """
    FastAPI dependency for endpoint-level circuit breaking

    Usage:
        @router.get("/protected")
        async def protected_route(
            _: None = Depends(circuit_breaker_dependency(breaker_name="wenxin_api"))
        ):
            return {"message": "OK"}
    """
    cb = get_circuit_breaker(breaker_name)

    if cb.state == CircuitBreakerState.OPEN:
        retry_after = cb.config.timeout - (time.time() - (cb.last_failure_time or 0))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "error": "service_unavailable",
                "message": "服务暂时不可用，请稍后再试",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(int(retry_after)) if retry_after else "60"}
        )


# Circuit breaker state endpoint
async def get_circuit_breaker_states() -> Dict[str, Any]:
    """Get all circuit breaker states for monitoring"""
    return {
        "circuit_breakers": [
            cb.get_state() for cb in _circuit_breakers.values()
        ],
        "timestamp": datetime.now().isoformat()
    }
