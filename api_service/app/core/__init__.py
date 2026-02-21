"""
Core module for AI舌诊智能诊断系统 API service.

This module provides core functionality including:
- database: Database connection and session management
- security: JWT tokens and password hashing utilities
"""

from api_service.app.core.database import (
    DATABASE_URL,
    check_db_health,
    close_db,
    create_db_engine,
    get_db,
    get_database_url,
    get_db_session,
    get_engine,
    get_session_factory,
    init_db,
)
from api_service.app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expiration,
    hash_password,
    is_token_expired,
    verify_password,
    verify_token,
)

__all__ = [
    # Database exports
    "DATABASE_URL",
    "check_db_health",
    "close_db",
    "create_db_engine",
    "get_db",
    "get_database_url",
    "get_db_session",
    "get_engine",
    "get_session_factory",
    "init_db",
    # Security exports
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_token_expiration",
    "hash_password",
    "is_token_expired",
    "verify_password",
    "verify_token",
]
