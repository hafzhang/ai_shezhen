#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI Dependency Injection Module
AI舌诊智能诊断系统 - API Dependencies
Phase 2: Database & Auth - US-112

This module provides FastAPI dependencies for:
- Database session injection
- JWT token authentication
- Current user retrieval
- Optional authentication (anonymous support)

Usage:
    from fastapi import Depends
    from api_service.app.api.deps import get_db, get_current_user, get_optional_user
    from api_service.app.models.database import User

    @app.get("/protected")
    def protected_endpoint(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
        return {"user_id": current_user.id}

    @app.get("/public")
    def public_endpoint(
        db: Session = Depends(get_db),
        user: Optional[User] = Depends(get_optional_user)
    ):
        return {"authenticated": user is not None}
"""

import logging
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from api_service.app.core.database import get_db as database_get_db
from api_service.app.core.security import verify_token, is_token_expired
from api_service.app.models.database import User
from api_service.app.core.auth import get_user_by_id

# Configure logging
logger = logging.getLogger(__name__)

# OAuth2 scheme for token extraction
# The tokenUrl should point to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v2/auth/login",
    auto_error=False  # Don't auto-error for missing tokens (allows optional auth)
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session injection.

    This dependency provides a database session to endpoint functions.
    The session is automatically closed after the request completes.

    Args:
        None (uses dependency injection)

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/users")
        def list_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    Note:
        The session is automatically committed/rolled back and closed
        by the context manager in database.get_db()
    """
    yield from database_get_db()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency to get the currently authenticated user from JWT token.

    This dependency:
    1. Extracts the JWT token from the Authorization header
    2. Verifies the token signature and expiration
    3. Retrieves the user from the database
    4. Raises HTTPException if authentication fails

    Args:
        token: JWT access token (auto-extracted by OAuth2PasswordBearer)
        db: Database session (injected via get_db dependency)

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: 401 if token is missing, invalid, expired, or user not found

    Example:
        @app.get("/me")
        def get_profile(current_user: User = Depends(get_current_user)):
            return {"nickname": current_user.nickname}

    Note:
        This dependency requires authentication. For optional authentication,
        use get_optional_user() instead.
    """
    # Check if token was provided
    if token is None:
        logger.warning("Authentication failed: No token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is expired
    if is_token_expired(token):
        logger.warning("Authentication failed: Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token and get payload
    payload = verify_token(token, token_type="access")
    if payload is None:
        logger.warning("Authentication failed: Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        logger.warning("Authentication failed: Token missing subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve user from database
    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        logger.warning(f"Authentication failed: User not found (id={user_id})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"User authenticated: {user.id} ({user.phone or user.openid})")
    return user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    FastAPI dependency to get the current user, allowing anonymous access.

    This dependency is similar to get_current_user() but does not raise
    an exception if authentication fails. Instead, it returns None when:
    - No token is provided
    - Token is invalid
    - Token is expired
    - User not found

    This is useful for endpoints that work for both authenticated and
    anonymous users (e.g., diagnosis endpoint).

    Args:
        token: JWT access token (optional, auto-extracted by OAuth2PasswordBearer)
        db: Database session (injected via get_db dependency)

    Returns:
        Optional[User]: The authenticated user object, or None if not authenticated

    Example:
        @app.post("/api/v2/diagnosis")
        def create_diagnosis(
            data: DiagnosisRequest,
            db: Session = Depends(get_db),
            user: Optional[User] = Depends(get_optional_user)
        ):
            diagnosis = perform_diagnosis(data)
            if user:
                diagnosis.user_id = user.id
            return diagnosis

    Note:
        When using this dependency, check if the return value is None
        to determine if the request is authenticated.
    """
    # If no token provided, return None
    if token is None:
        return None

    # Check if token is expired
    if is_token_expired(token):
        logger.debug("Optional auth: Token expired, returning None")
        return None

    # Verify token and get payload
    payload = verify_token(token, token_type="access")
    if payload is None:
        logger.debug("Optional auth: Invalid token, returning None")
        return None

    # Extract user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        logger.debug("Optional auth: Token missing subject, returning None")
        return None

    # Retrieve user from database
    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        logger.debug(f"Optional auth: User not found (id={user_id}), returning None")
        return None

    logger.debug(f"Optional auth: User authenticated: {user.id}")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    FastAPI dependency to get the current active (non-deleted) user.

    This dependency extends get_current_user() to additionally check
    that the user account is active (not soft deleted).

    Args:
        current_user: Authenticated user (injected via get_current_user)

    Returns:
        User: The authenticated and active user object

    Raises:
        HTTPException: 400 if the user account has been deleted

    Example:
        @app.get("/profile")
        def get_profile(user: User = Depends(get_current_active_user)):
            return {"nickname": user.nickname}

    Note:
        This is typically used instead of get_current_user() for most
        endpoints to ensure soft-deleted users cannot access the system.
    """
    # Check if user is soft deleted (deleted_at is not None)
    if current_user.deleted_at is not None:
        logger.warning(f"Active user check failed: User {current_user.id} is deleted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user - account has been deleted"
        )

    return current_user


async def get_current_active_optional_user(
    user: Optional[User] = Depends(get_optional_user),
) -> Optional[User]:
    """
    FastAPI dependency to get optional active user.

    This dependency extends get_optional_user() to additionally check
    that if a user is authenticated, their account is active.

    Args:
        user: Optional authenticated user (injected via get_optional_user)

    Returns:
        Optional[User]: The authenticated and active user object, or None

    Example:
        @app.post("/api/v2/diagnosis")
        def create_diagnosis(
            data: DiagnosisRequest,
            db: Session = Depends(get_db),
            user: Optional[User] = Depends(get_current_active_optional_user)
        ):
            diagnosis = perform_diagnosis(data)
            if user:
                diagnosis.user_id = user.id
            return diagnosis

    Note:
        This returns None if:
        - No token provided
        - Token invalid/expired
        - User not found
        - User account is deleted
    """
    # If no user provided, return None
    if user is None:
        return None

    # Check if user is soft deleted
    if user.deleted_at is not None:
        logger.debug(f"Optional active user: User {user.id} is deleted, returning None")
        return None

    return user


__all__ = [
    "get_db",
    "get_current_user",
    "get_optional_user",
    "get_current_active_user",
    "get_current_active_optional_user",
    "oauth2_scheme",
]
