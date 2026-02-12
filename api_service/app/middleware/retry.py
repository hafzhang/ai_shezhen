#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
指数退避重试机制

Exponential backoff retry mechanism for external service calls.
Prevents thundering herd problem and improves reliability.

Author: Ralph Agent
Date: 2026-02-12
"""

import time
import asyncio
import random
from typing import Optional, Callable, TypeVar, Tuple, List, Type, Any
from datetime import datetime
import logging

from fastapi import HTTPException, status
import httpx

logger = logging.getLogger(__name__)


T = TypeVar('T')


class RetryConfig:
    """Retry configuration"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        jitter_factor: float = 0.1,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        retryable_status_codes: Optional[List[int]] = None,
        backoff装饰器: bool = True
    ):
        """
        Initialize retry configuration

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay between retries (default: 10.0)
            exponential_base: Base for exponential backoff (default: 2.0)
            jitter: Add random jitter to prevent thundering herd (default: True)
            jitter_factor: Jitter randomness factor (default: 0.1)
            retryable_exceptions: Exception types that should trigger retry
            retryable_status_codes: HTTP status codes that should trigger retry
            backoff装饰器: Use exponential backoff (default: True)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.jitter_factor = jitter_factor
        self.backoff装饰器 = backoff装饰器

        # Default retryable exceptions
        self.retryable_exceptions = retryable_exceptions or (
            ConnectionError,
            TimeoutError,
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        )

        # Default retryable HTTP status codes
        self.retryable_status_codes = retryable_status_codes or [
            408,  # Request Timeout
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        ]

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt using exponential backoff

        Args:
            attempt: Retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        if not self.backoff装饰器:
            delay = self.base_delay
        else:
            # Exponential backoff: base_delay * (exponential_base ^ attempt)
            delay = self.base_delay * (self.exponential_base ** attempt)

        # Cap at max delay
        delay = min(delay, self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)

        # Ensure non-negative
        return max(0, delay)

    def is_retryable_exception(self, exception: Exception) -> bool:
        """Check if exception should trigger a retry"""
        return isinstance(exception, self.retryable_exceptions)

    def is_retryable_status_code(self, status_code: int) -> bool:
        """Check if HTTP status code should trigger a retry"""
        return status_code in self.retryable_status_codes


class RetryStats:
    """Statistics for retry operations"""

    def __init__(self):
        self.total_attempts = 0
        self.total_retries = 0
        self.total_successes = 0
        self.total_failures = 0
        self.total_delay_time = 0.0
        self.last_attempt_time: Optional[float] = None

    def record_attempt(self):
        """Record a retry attempt"""
        self.total_attempts += 1
        self.last_attempt_time = time.time()

    def record_retry(self, delay: float):
        """Record a retry with delay"""
        self.total_retries += 1
        self.total_delay_time += delay

    def record_success(self):
        """Record a successful attempt"""
        self.total_successes += 1

    def record_failure(self):
        """Record a final failure"""
        self.total_failures += 1

    def get_stats(self) -> dict:
        """Get statistics as dictionary"""
        return {
            "total_attempts": self.total_attempts,
            "total_retries": self.total_retries,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "total_delay_time": self.total_delay_time,
            "average_delay": self.total_delay_time / self.total_retries if self.total_retries > 0 else 0,
            "success_rate": self.total_successes / self.total_attempts if self.total_attempts > 0 else 0
        }


async def retry_with_exponential_backoff(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs
) -> T:
    """
    Execute function with exponential backoff retry

    Args:
        func: Function to call (can be sync or async)
        *args: Positional arguments for func
        config: Retry configuration
        on_retry: Callback function called on each retry
            Signature: (attempt: int, exception: Exception, delay: float) -> None
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Exception: The last exception if all retries are exhausted

    Example:
        async def fetch_data():
            return await httpx.get("https://api.example.com/data")

        result = await retry_with_exponential_backoff(
            fetch_data,
            config=RetryConfig(max_retries=3, base_delay=1.0)
        )
    """
    config = config or RetryConfig()
    last_exception = None
    stats = RetryStats()

    for attempt in range(config.max_retries + 1):
        stats.record_attempt()

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, func, *args, **kwargs)

            stats.record_success()
            logger.debug(f"Retry succeeded on attempt {attempt}")
            return result

        except Exception as e:
            last_exception = e

            # Check if exception is retryable
            if not config.is_retryable_exception(e):
                logger.debug(f"Non-retryable exception: {type(e).__name__}")
                raise

            # Check if this is the last attempt
            if attempt >= config.max_retries:
                stats.record_failure()
                logger.warning(
                    f"Retry exhausted after {config.max_retries} attempts. "
                    f"Final error: {type(e).__name__}: {e}"
                )
                raise

            # Calculate delay
            delay = config.calculate_delay(attempt)
            stats.record_retry(delay)

            # Call on_retry callback if provided
            if on_retry:
                try:
                    on_retry(attempt, e, delay)
                except Exception as callback_error:
                    logger.error(f"on_retry callback error: {callback_error}")

            # Log retry
            logger.info(
                f"Retry attempt {attempt + 1}/{config.max_retries} "
                f"after {delay:.2f}s delay. Error: {type(e).__name__}: {e}"
            )

            # Wait before retry
            await asyncio.sleep(delay)

    # Should never reach here
    stats.record_failure()
    raise last_exception


async def retry_http_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> httpx.Response:
    """
    Execute HTTP request with retry logic

    Args:
        client: httpx AsyncClient
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        config: Retry configuration
        **kwargs: Arguments for httpx request

    Returns:
        httpx.Response

    Raises:
        httpx.HTTPError: If request fails after all retries
    """
    config = config or RetryConfig()

    async def do_request():
        response = await client.request(method, url, **kwargs)

        # Check for retryable status codes
        if config.is_retryable_status_code(response.status_code):
            raise HTTPException(
                status_code=response.status_code,
                detail=f"HTTP {response.status_code}: {response.text}"
            )

        return response

    try:
        return await retry_with_exponential_backoff(
            do_request,
            config=config
        )
    except HTTPException as e:
        # Convert HTTPException from status code check back to response
        raise httpx.HTTPStatusError(
            message=e.detail,
            request=kwargs.get("content") or method,
            response=None
        ) from e


def retry_decorator(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Decorator for adding retry logic to functions

    Usage:
        @retry_decorator(max_retries=3, base_delay=1.0)
        async def call_external_api():
            return await httpx.get("https://api.example.com")
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=exceptions
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_exponential_backoff(
                func, *args, config=config, **kwargs
            )
        return wrapper
    return decorator


class RetryableHTTPClient:
    """
    HTTP client with built-in retry logic

    Wraps httpx.AsyncClient with automatic retry for failed requests.
    """

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        **client_kwargs
    ):
        """
        Initialize retryable HTTP client

        Args:
            retry_config: Retry configuration
            **client_kwargs: Arguments for httpx.AsyncClient
        """
        self.retry_config = retry_config or RetryConfig()
        self.client_kwargs = client_kwargs
        self._client: Optional[httpx.AsyncClient] = None
        self.stats = RetryStats()

    async def __aenter__(self):
        """Async context manager entry"""
        self._client = httpx.AsyncClient(**self.client_kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Execute HTTP request with retry"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        async def do_request():
            response = await self._client.request(method, url, **kwargs)

            if self.retry_config.is_retryable_status_code(response.status_code):
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=None,
                    response=response
                )

            return response

        return await retry_with_exponential_backoff(
            do_request,
            config=self.retry_config
        )

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request with retry"""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request with retry"""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> httpx.Response:
        """PUT request with retry"""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """DELETE request with retry"""
        return await self.request("DELETE", url, **kwargs)

    def get_stats(self) -> dict:
        """Get retry statistics"""
        return self.stats.get_stats()


# Global retry statistics
_global_retry_stats = RetryStats()


def get_global_retry_stats() -> dict:
    """Get global retry statistics"""
    return _global_retry_stats.get_stats()


def reset_global_retry_stats():
    """Reset global retry statistics"""
    global _global_retry_stats
    _global_retry_stats = RetryStats()
