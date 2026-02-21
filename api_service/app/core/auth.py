#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Authentication Business Logic Module
AI舌诊智能诊断系统 - Authentication Business Logic
Phase 2: Database & Auth - US-111

This module provides authentication business logic functions:
- User authentication (phone/password)
- User creation and registration
- User lookup by phone or OpenID (mini-programs)
- Password hashing and verification integration

Usage:
    from api_service.app.core.auth import (
        authenticate_user,
        create_user,
        get_user_by_phone,
        get_user_by_openid,
    )

    # Authenticate a user
    user = authenticate_user(db, phone="13800138000", password="password123")

    # Create a new user
    user = create_user(db, phone="13800138000", password="password123", nickname="张三")

    # Look up users
    user = get_user_by_phone(db, phone="13800138000")
    user = get_user_by_openid(db, openid="oxxxxxx", openid_type="wechat")
"""

import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from api_service.app.models.database import User
from api_service.app.core.security import hash_password, verify_password


def authenticate_user(db: Session, phone: str, password: str) -> Optional[User]:
    """
    Authenticate a user with phone number and password.

    Verifies user credentials by:
    1. Finding user by phone number
    2. Checking if account is active (not soft deleted)
    3. Verifying password against stored hash

    Args:
        db: Database session
        phone: User's phone number
        password: Plain text password to verify

    Returns:
        User object if authentication successful, None otherwise

    Example:
        >>> user = authenticate_user(db, phone="13800138000", password="password123")
        >>> if user:
        ...     print(f"Authenticated: {user.nickname}")
        ... else:
        ...     print("Authentication failed")
    """
    # Query user by phone number
    stmt = select(User).where(
        User.phone == phone,
        User.deleted_at.is_(None)  # Only active accounts
    )
    result = db.execute(stmt)
    user = result.scalar_one_or_none()

    # Return None if user not found
    if user is None:
        return None

    # Verify password
    if not verify_password(password, user.password_hash):
        return None

    return user


def create_user(
    db: Session,
    *,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    nickname: Optional[str] = None,
    openid: Optional[str] = None,
    openid_type: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> User:
    """
    Create a new user account.

    Supports multiple registration methods:
    - Phone registration (phone + password)
    - Email registration (email + password)
    - Mini-program registration (openid + openid_type)

    Args:
        db: Database session
        phone: Phone number (unique)
        email: Email address (unique)
        password: Plain text password (will be hashed)
        nickname: User display name
        openid: WeChat/Douyin OpenID
        openid_type: OpenID provider type ("wechat" or "douyin")
        avatar_url: Profile avatar URL

    Returns:
        Created User object

    Raises:
        ValueError: If neither phone/email nor openid is provided
        ValueError: If password not provided for phone/email registration

    Example:
        >>> # Phone registration
        >>> user = create_user(
        ...     db,
        ...     phone="13800138000",
        ...     password="password123",
        ...     nickname="张三"
        ... )

        >>> # WeChat mini-program registration
        >>> user = create_user(
        ...     db,
        ...     openid="oxxxxxx",
        ...     openid_type="wechat",
        ...     nickname="微信用户"
        ... )
    """
    # Validate required fields
    has_password_auth = phone is not None or email is not None
    has_miniprogram_auth = openid is not None and openid_type is not None

    if not has_password_auth and not has_miniprogram_auth:
        raise ValueError(
            "Must provide either phone/email or openid+openid_type"
        )

    # Password is required for phone/email registration
    if has_password_auth and password is None:
        raise ValueError(
            "Password is required for phone/email registration"
        )

    # Hash password if provided
    password_hash = None
    if password is not None:
        password_hash = hash_password(password)

    # Create new user
    user = User(
        phone=phone,
        email=email,
        password_hash=password_hash,
        nickname=nickname,
        openid=openid,
        openid_type=openid_type,
        avatar_url=avatar_url,
    )

    # Add to database
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    """
    Get a user by phone number.

    Args:
        db: Database session
        phone: User's phone number

    Returns:
        User object if found, None otherwise

    Example:
        >>> user = get_user_by_phone(db, phone="13800138000")
        >>> if user:
        ...     print(f"Found user: {user.nickname}")
    """
    stmt = select(User).where(
        User.phone == phone,
        User.deleted_at.is_(None)  # Only active accounts
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Get a user by email address.

    Args:
        db: Database session
        email: User's email address

    Returns:
        User object if found, None otherwise

    Example:
        >>> user = get_user_by_email(db, email="user@example.com")
        >>> if user:
        ...     print(f"Found user: {user.nickname}")
    """
    stmt = select(User).where(
        User.email == email,
        User.deleted_at.is_(None)  # Only active accounts
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def get_user_by_openid(
    db: Session,
    openid: str,
    openid_type: str,
) -> Optional[User]:
    """
    Get a user by OpenID for mini-program authentication.

    Supports WeChat and Douyin mini-programs.

    Args:
        db: Database session
        openid: User's OpenID from mini-program
        openid_type: OpenID provider type ("wechat" or "douyin")

    Returns:
        User object if found, None otherwise

    Example:
        >>> # WeChat user
        >>> user = get_user_by_openid(db, openid="oxxxxxx", openid_type="wechat")

        >>> # Douyin user
        >>> user = get_user_by_openid(db, openid="douyin_xxx", openid_type="douyin")
    """
    stmt = select(User).where(
        User.openid == openid,
        User.openid_type == openid_type,
        User.deleted_at.is_(None)  # Only active accounts
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def get_user_by_id(db: Session, user_id: UUID | str) -> Optional[User]:
    """
    Get a user by UUID.

    Args:
        db: Database session
        user_id: User's UUID (as UUID or string)

    Returns:
        User object if found, None otherwise

    Example:
        >>> from uuid import UUID
        >>> user_id = UUID("123e4567-e89b-12d3-a456-426614174000")
        >>> user = get_user_by_id(db, user_id=user_id)
    """
    # Convert string to UUID if needed
    if isinstance(user_id, str):
        try:
            user_id = UUID(user_id)
        except ValueError:
            return None

    stmt = select(User).where(
        User.id == user_id,
        User.deleted_at.is_(None)  # Only active accounts
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def update_user(
    db: Session,
    user: User,
    *,
    nickname: Optional[str] = None,
    avatar_url: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> User:
    """
    Update user profile information.

    Args:
        db: Database session
        user: User object to update
        nickname: New nickname
        avatar_url: New avatar URL
        email: New email address
        phone: New phone number

    Returns:
        Updated User object

    Example:
        >>> user = get_user_by_id(db, user_id)
        >>> updated_user = update_user(db, user, nickname="新昵称")
    """
    # Update fields if provided
    if nickname is not None:
        user.nickname = nickname
    if avatar_url is not None:
        user.avatar_url = avatar_url
    if email is not None:
        user.email = email
    if phone is not None:
        user.phone = phone

    # Update timestamp
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    db.refresh(user)

    return user


def change_password(
    db: Session,
    user: User,
    new_password: str,
) -> User:
    """
    Change user password.

    Args:
        db: Database session
        user: User object
        new_password: New plain text password

    Returns:
        Updated User object

    Example:
        >>> user = get_user_by_id(db, user_id)
        >>> updated_user = change_password(db, user, new_password="newpass123")
    """
    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    db.refresh(user)

    return user


def soft_delete_user(db: Session, user: User) -> User:
    """
    Soft delete a user account.

    Marks the account as deleted without actually removing it from the database.
    The user can still be referenced by related records.

    Args:
        db: Database session
        user: User object to delete

    Returns:
        Updated User object with deleted_at set

    Example:
        >>> user = get_user_by_id(db, user_id)
        >>> deleted_user = soft_delete_user(db, user)
    """
    user.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    db.refresh(user)

    return user


def check_phone_exists(db: Session, phone: str) -> bool:
    """
    Check if a phone number is already registered.

    Args:
        db: Database session
        phone: Phone number to check

    Returns:
        True if phone number exists, False otherwise

    Example:
        >>> if check_phone_exists(db, phone="13800138000"):
        ...     print("Phone number already registered")
    """
    stmt = select(User.id).where(
        User.phone == phone,
        User.deleted_at.is_(None)
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none() is not None


def check_email_exists(db: Session, email: str) -> bool:
    """
    Check if an email address is already registered.

    Args:
        db: Database session
        email: Email address to check

    Returns:
        True if email exists, False otherwise

    Example:
        >>> if check_email_exists(db, email="user@example.com"):
        ...     print("Email already registered")
    """
    stmt = select(User.id).where(
        User.email == email,
        User.deleted_at.is_(None)
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none() is not None


def check_openid_exists(
    db: Session,
    openid: str,
    openid_type: str,
) -> bool:
    """
    Check if an OpenID is already registered.

    Args:
        db: Database session
        openid: OpenID to check
        openid_type: OpenID provider type

    Returns:
        True if OpenID exists, False otherwise

    Example:
        >>> if check_openid_exists(db, openid="oxxxxxx", openid_type="wechat"):
        ...     print("WeChat user already registered")
    """
    stmt = select(User.id).where(
        User.openid == openid,
        User.openid_type == openid_type,
        User.deleted_at.is_(None)
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none() is not None


__all__ = [
    "authenticate_user",
    "create_user",
    "get_user_by_phone",
    "get_user_by_email",
    "get_user_by_openid",
    "get_user_by_id",
    "update_user",
    "change_password",
    "soft_delete_user",
    "check_phone_exists",
    "check_email_exists",
    "check_openid_exists",
]
