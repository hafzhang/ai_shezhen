#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API限流中间件 - Token Bucket Algorithm

Token bucket rate limiter for API request throttling.
Uses Redis for distributed rate limiting across multiple API instances.

Author: Ralph Agent
Date: 2026-02-12
"""

import time
import asyncio
import hashlib
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
import logging

from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis import Redis
from redis.exceptions import RedisError

from api_service.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Rate limit exceeded exception"""
    def __init__(self, retry_after: Optional[float] = None):
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


class RateLimiter:
    """Base rate limiter interface"""

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, Optional[float]]:
        """
        Check if request is allowed

        Args:
            key: Unique identifier (IP, API key, user ID)
            limit: Max requests allowed
            window: Time window in seconds

        Returns:
            (is_allowed, retry_after_seconds)
        """
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    """In-memory rate limiter using sliding window"""

    def __init__(self):
        self._requests: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, Optional[float]]:
        async with self._lock:
            now = time.time()
            window_start = now - window

            # Get existing requests or initialize
            requests = self._requests.get(key, [])

            # Remove old requests outside the window
            requests = [req_time for req_time in requests if req_time > window_start]

            # Check if limit exceeded
            if len(requests) >= limit:
                # Calculate retry after (oldest request + window - now)
                oldest_in_window = min(requests)
                retry_after = oldest_in_window + window - now
                return False, retry_after

            # Add current request
            requests.append(now)
            self._requests[key] = requests
            return True, None


class TokenBucketRateLimiter(RateLimiter):
    """
    Token bucket rate limiter with Redis backend

    Token bucket algorithm:
    - Bucket has maximum capacity (burst capacity)
    - Tokens are added at a fixed rate (refill rate)
    - Each request consumes one token
    - Requests are denied when bucket is empty
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        default_rate: int = 100,
        default_capacity: int = 100,
        prefix: str = "rate_limit"
    ):
        """
        Initialize token bucket rate limiter

        Args:
            redis_client: Redis client for distributed limiting
            default_rate: Tokens per second refill rate
            default_capacity: Maximum bucket capacity
            prefix: Redis key prefix
        """
        self.redis = redis_client
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self.prefix = prefix
        self.in_memory_fallback = InMemoryRateLimiter()

    def _get_redis_key(self, key: str) -> str:
        """Generate Redis key for rate limit"""
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return f"{self.prefix}:{safe_key}"

    async def is_allowed(
        self,
        key: str,
        limit: Optional[int] = None,
        window: Optional[int] = None
    ) -> tuple[bool, Optional[float]]:
        """
        Check if request is allowed using token bucket algorithm

        For compatibility with sliding window interface:
        - limit is treated as capacity (bucket size)
        - window is used to calculate refill rate (limit / window)

        Args:
            key: Unique identifier
            limit: Max requests (bucket capacity)
            window: Time window for rate calculation

        Returns:
            (is_allowed, retry_after_seconds)
        """
        capacity = limit or self.default_capacity
        rate_per_second = (limit / window) if window and limit else self.default_rate

        # Try Redis first
        if self.redis and self._is_redis_available():
            try:
                return await self._check_redis_token_bucket(key, capacity, rate_per_second)
            except RedisError as e:
                logger.warning(f"Redis rate limit failed, using in-memory fallback: {e}")
            except Exception as e:
                logger.error(f"Rate limiter error: {e}")
        else:
            logger.debug("Redis unavailable, using in-memory rate limiter")

        # Fallback to in-memory
        return await self.in_memory_fallback.is_allowed(key, capacity, window or 1)

    def _is_redis_available(self) -> bool:
        """Check if Redis is available"""
        try:
            self.redis.ping()
            return True
        except (RedisError, ConnectionError):
            return False

    async def _check_redis_token_bucket(
        self,
        key: str,
        capacity: int,
        rate_per_second: float
    ) -> tuple[bool, Optional[float]]:
        """
        Check token bucket in Redis

        Uses Lua script for atomic operations:
        - Get current tokens and last update time
        - Refill tokens based on elapsed time
        - Consume one token if available
        - Return whether request is allowed
        """
        redis_key = self._get_redis_key(key)

        # Lua script for atomic token bucket operations
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local tokens_to_consume = tonumber(ARGV[4])

        -- Get current state
        local current = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(current[1])
        local last_update = tonumber(current[2])

        -- Initialize if not exists
        if tokens == nil then
            tokens = capacity
            last_update = now
        end

        -- Refill tokens based on elapsed time
        local elapsed = now - last_update
        local tokens_to_add = math.floor(elapsed * rate)
        tokens = math.min(capacity, tokens + tokens_to_add)

        -- Check if enough tokens
        if tokens >= tokens_to_consume then
            -- Consume tokens
            tokens = tokens - tokens_to_consume
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            redis.call('EXPIRE', key, math.ceil(capacity / rate) + 10)
            return {1, tokens}  -- Allowed
        else
            -- Not enough tokens, calculate retry after
            local tokens_needed = tokens_to_consume - tokens
            local retry_after = tokens_needed / rate
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            redis.call('EXPIRE', key, math.ceil(capacity / rate) + 10)
            return {0, retry_after}  -- Denied
        end
        """

        try:
            # Execute Lua script
            result = self.redis.eval(
                lua_script,
                1,  # Number of keys
                redis_key,
                capacity,
                rate_per_second,
                time.time(),
                1  # tokens_to_consume
            )

            if result[0] == 1:
                return True, None  # Allowed
            else:
                return False, result[1]  # Denied, retry_after in seconds

        except RedisError as e:
            logger.error(f"Redis token bucket error: {e}")
            raise

    def reset(self, key: str) -> bool:
        """Reset rate limit for a specific key"""
        if self.redis:
            try:
                redis_key = self._get_redis_key(key)
                self.redis.delete(redis_key)
                return True
            except RedisError:
                return False
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting

    Applies rate limiting to all incoming requests based on IP address
    or custom key extraction function.
    """

    def __init__(
        self,
        app,
        rate_limiter: RateLimiter,
        key_extractor: Optional[Callable[[Request], str]] = None,
        default_limit: int = 100,
        default_window: int = 1,
        excluded_paths: Optional[list] = None
    ):
        """
        Initialize rate limit middleware

        Args:
            app: FastAPI application
            rate_limiter: Rate limiter instance
            key_extractor: Function to extract rate limit key from request
            default_limit: Default requests per window
            default_window: Default time window in seconds
            excluded_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.key_extractor = key_extractor or self._default_key_extractor
        self.default_limit = default_limit
        self.default_window = default_window
        self.excluded_paths = excluded_paths or ["/health", "/docs", "/redoc", "/openapi.json"]

    def _default_key_extractor(self, request: Request) -> str:
        """Extract client IP address for rate limiting"""
        # Try X-Forwarded-For header first (for proxy setups)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        # Try X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return f"ip:{real_ip}"

        # Fallback to client host
        if request.client:
            return f"ip:{request.client.host}"

        return "ip:unknown"

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter"""
        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Extract rate limit key
        key = self.key_extractor(request)

        # Check rate limit
        try:
            allowed, retry_after = await self.rate_limiter.is_allowed(
                key=key,
                limit=self.default_limit,
                window=self.default_window
            )

            if not allowed:
                logger.warning(f"Rate limit exceeded for {key}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": "rate_limit_exceeded",
                        "message": "请求过于频繁，请稍后再试",
                        "retry_after": retry_after
                    },
                    headers={
                        "Retry-After": str(int(retry_after)) if retry_after else "1",
                        "X-RateLimit-Limit": str(self.default_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time() + (retry_after or 1)))
                    }
                )

        except RateLimitError as e:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "message": "请求过于频繁，请稍后再试"
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Policy"] = f"{self.default_limit};w={self.default_window}"

        return response


# Global rate limiter instance
_rate_limiter: Optional[TokenBucketRateLimiter] = None


def get_rate_limiter() -> Optional[TokenBucketRateLimiter]:
    """Get global rate limiter instance"""
    global _rate_limiter
    return _rate_limiter


def init_rate_limiter(redis_client: Optional[Redis] = None) -> TokenBucketRateLimiter:
    """Initialize global rate limiter"""
    global _rate_limiter
    _rate_limiter = TokenBucketRateLimiter(
        redis_client=redis_client,
        default_rate=settings.RATE_LIMIT_PER_SECOND,
        default_capacity=settings.RATE_LIMIT_PER_SECOND
    )
    return _rate_limiter


# Dependency for route-level rate limiting
async def rate_limit_dependency(
    request: Request,
    limit: int = 100,
    window: int = 1
):
    """
    FastAPI dependency for route-level rate limiting

    Usage:
        @router.get("/protected")
        async def protected_route(
            _: None = Depends(rate_limit_dependency(limit=10, window=60))
        ):
            return {"message": "OK"}
    """
    rate_limiter = get_rate_limiter()
    if not rate_limiter:
        return  # Rate limiter not initialized

    # Extract key
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        key = f"ip:{forwarded.split(',')[0].strip()}"
    elif request.client:
        key = f"ip:{request.client.host}"
    else:
        return

    # Check limit
    allowed, retry_after = await rate_limiter.is_allowed(key, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "success": False,
                "error": "rate_limit_exceeded",
                "message": "请求过于频繁，请稍后再试",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(int(retry_after)) if retry_after else "1"}
        )
