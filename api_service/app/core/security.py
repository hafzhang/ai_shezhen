#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Security Utilities Module - JWT and Password Handling

This module provides cryptographic utilities for the AI舌诊智能诊断系统:
- Password hashing and verification using bcrypt
- JWT access token and refresh token generation
- JWT token decoding and validation

Usage:
    from api_service.app.core.security import (
        hash_password,
        verify_password,
        create_access_token,
        create_refresh_token,
        decode_token,
    )

    # Hash a password
    hashed = hash_password("mypassword")

    # Verify a password
    is_valid = verify_password("mypassword", hashed)

    # Create tokens
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})

    # Decode a token
    payload = decode_token(token)
"""

import datetime
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from api_service.core.config import settings


# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# JWT configuration
# Access token expires in 30 minutes
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
# Refresh token expires in 7 days
REFRESH_TOKEN_EXPIRE_DAYS: int = 7

# JWT algorithm and secret key
# In production, SECRET_KEY should be set in environment variables
SECRET_KEY: str = getattr(settings, "SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM: str = "HS256"


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Example:
        >>> hashed = hash_password("mypassword")
        >>> isinstance(hashed, str)
        True
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("mypassword")
        >>> verify_password("mypassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[datetime.timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Access tokens are short-lived (30 minutes by default) and are used
    to authenticate API requests.

    Args:
        data: Payload data to encode in the token (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time delta
            If not provided, uses ACCESS_TOKEN_EXPIRE_MINUTES (30 minutes)

    Returns:
        Encoded JWT access token string

    Example:
        >>> token = create_access_token(data={"sub": "user-123"})
        >>> isinstance(token, str)
        True
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "type": "access",  # Token type identifier
    })

    # Encode JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[datetime.timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens are long-lived (7 days by default) and are used
    to obtain new access tokens without requiring re-authentication.

    Args:
        data: Payload data to encode in the token (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time delta
            If not provided, uses REFRESH_TOKEN_EXPIRE_DAYS (7 days)

    Returns:
        Encoded JWT refresh token string

    Example:
        >>> token = create_refresh_token(data={"sub": "user-123"})
        >>> isinstance(token, str)
        True
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode.update({
        "exp": expire,
        "type": "refresh",  # Token type identifier
    })

    # Encode JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload if valid, None if invalid/expired

    Raises:
        JWTError: If token is invalid or malformed

    Example:
        >>> token = create_access_token(data={"sub": "user-123"})
        >>> payload = decode_token(token)
        >>> payload["sub"]
        'user-123'
        >>> payload["type"]
        'access'
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify a JWT token and check its type.

    Args:
        token: JWT token string to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded token payload if valid and correct type, None otherwise

    Example:
        >>> access_token = create_access_token(data={"sub": "user-123"})
        >>> verify_token(access_token, "access")["sub"]
        'user-123'
        >>> verify_token(access_token, "refresh") is None
        True
    """
    payload = decode_token(token)
    if payload is None:
        return None

    # Check token type
    if payload.get("type") != token_type:
        return None

    return payload


def get_token_expiration(token: str) -> Optional[datetime.datetime]:
    """
    Get the expiration datetime from a JWT token.

    Args:
        token: JWT token string

    Returns:
        Expiration datetime if token is valid, None otherwise

    Example:
        >>> token = create_access_token(data={"sub": "user-123"})
        >>> exp = get_token_expiration(token)
        >>> exp > datetime.datetime.now(datetime.timezone.utc)
        True
    """
    payload = decode_token(token)
    if payload is None:
        return None

    exp_timestamp = payload.get("exp")
    if exp_timestamp is None:
        return None

    return datetime.datetime.fromtimestamp(exp_timestamp, tz=datetime.timezone.utc)


def is_token_expired(token: str) -> bool:
    """
    Check if a JWT token is expired.

    Args:
        token: JWT token string

    Returns:
        True if token is expired or invalid, False if still valid

    Example:
        >>> # Create a token that expires immediately
        >>> token = create_access_token(
        ...     data={"sub": "user-123"},
        ...     expires_delta=datetime.timedelta(seconds=-1)
        ... )
        >>> is_token_expired(token)
        True
    """
    exp = get_token_expiration(token)
    if exp is None:
        return True

    now = datetime.datetime.now(datetime.timezone.utc)
    return exp < now
