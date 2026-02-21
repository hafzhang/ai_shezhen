#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Authentication Endpoints
AI舌诊智能诊断系统 - API v2 Authentication
Phase 2: Database & Auth - US-113, US-114

This module provides authentication API endpoints:
- POST /api/v2/auth/register - User registration
- POST /api/v2/auth/login - User login
- POST /api/v2/auth/refresh - Token refresh
- POST /api/v2/auth/logout - User logout

Usage:
    from api_service.app.api.v2 import auth
    app.include_router(auth.router, prefix="/api/v2/auth", tags=["Authentication"])
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api_service.app.api.deps import get_db
from api_service.app.api.v2.models import (
    UserRegister,
    UserLogin,
    TokenResponse,
    LoginResponse,
    RegisterResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutResponse,
    UserInfo,
    WeChatLoginRequest,
    DouyinLoginRequest,
)
from api_service.app.core.auth import (
    create_user,
    authenticate_user,
    check_phone_exists,
    check_email_exists,
    get_user_by_openid,
    check_openid_exists,
    update_user,
)
from api_service.app.core.security import (
    hash_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    is_token_expired,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from api_service.app.models.database import User, RefreshToken

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Access token expiration in seconds
ACCESS_TOKEN_EXPIRES_IN = ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ============================================================================
# Registration Endpoint
# ============================================================================

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """
    Register a new user account.

    This endpoint creates a new user account with phone number and password.
    The password is hashed before storage. Both access and refresh tokens are
    returned upon successful registration.

    Args:
        user_data: User registration data (phone, password, nickname, email)
        db: Database session

    Returns:
        RegisterResponse with access_token, refresh_token, and user info

    Raises:
        HTTPException 400: If phone or email already exists

    Example:
        POST /api/v2/auth/register
        {
            "phone": "13800138000",
            "password": "abc12345",
            "nickname": "张三",
            "email": "user@example.com"
        }
    """
    # Check if phone number already exists
    if check_phone_exists(db, phone=user_data.phone):
        logger.warning(f"Registration failed: Phone already exists - {user_data.phone}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已被注册",
        )

    # Check if email already exists (if provided)
    if user_data.email and check_email_exists(db, email=user_data.email):
        logger.warning(f"Registration failed: Email already exists - {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    # Create new user
    # Password is hashed inside create_user via hash_password
    nickname = user_data.nickname or user_data.phone  # Default to phone if no nickname
    new_user = create_user(
        db,
        phone=user_data.phone,
        email=user_data.email,
        password=user_data.password,
        nickname=nickname,
    )

    # Generate tokens
    access_token = create_access_token(data={"sub": str(new_user.id)})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})

    # Store refresh token in database
    db_refresh_token = RefreshToken(
        user_id=new_user.id,
        token=refresh_token,
        expires_at=datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh_token)
    db.commit()

    logger.info(f"User registered successfully: {new_user.id} ({new_user.phone})")

    return RegisterResponse(
        success=True,
        message="注册成功",
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo.model_validate(new_user),
    )


# ============================================================================
# Login Endpoint
# ============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user with phone number and password.

    This endpoint verifies user credentials and returns access/refresh tokens
    upon successful authentication.

    Args:
        login_data: Login credentials (phone, password)
        db: Database session

    Returns:
        LoginResponse with access_token, refresh_token, and user info

    Raises:
        HTTPException 401: If phone number not found or password is incorrect

    Example:
        POST /api/v2/auth/login
        {
            "phone": "13800138000",
            "password": "abc12345"
        }
    """
    # Authenticate user
    user = authenticate_user(db, phone=login_data.phone, password=login_data.password)

    if user is None:
        logger.warning(f"Login failed: Invalid credentials for {login_data.phone}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token in database
    # First, revoke any existing active refresh tokens for this user (optional security measure)
    from sqlalchemy import select
    from sqlalchemy import and_

    existing_tokens_stmt = select(RefreshToken).where(
        and_(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    existing_tokens = db.execute(existing_tokens_stmt).scalars().all()

    # Optional: Revoke old tokens for security (single session per user)
    for old_token in existing_tokens:
        old_token.revoked_at = datetime.now()

    # Add new refresh token
    db_refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh_token)
    db.commit()

    logger.info(f"User logged in successfully: {user.id} ({user.phone})")

    return LoginResponse(
        success=True,
        message="登录成功",
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo.model_validate(user),
    )


# ============================================================================
# Token Refresh Endpoint
# ============================================================================

@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db),
) -> RefreshResponse:
    """
    Refresh access token using a valid refresh token.

    This endpoint validates the refresh token and generates a new access token.
    The refresh token must be valid, not expired, and not revoked.

    Args:
        refresh_data: Refresh token
        db: Database session

    Returns:
        RefreshResponse with new access_token and expires_in

    Raises:
        HTTPException 401: If refresh token is invalid, expired, or revoked

    Example:
        POST /api/v2/auth/refresh
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    """
    refresh_token = refresh_data.refresh_token

    # Check if token is expired
    if is_token_expired(refresh_token):
        logger.warning("Token refresh failed: Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌已过期，请重新登录",
        )

    # Verify token and get payload
    payload = verify_token(refresh_token, token_type="refresh")
    if payload is None:
        logger.warning("Token refresh failed: Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    # Extract user ID from token
    user_id = payload.get("sub")
    if user_id is None:
        logger.warning("Token refresh failed: Token missing subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌格式错误",
        )

    # Check if refresh token exists in database and is not revoked
    from sqlalchemy import select

    token_stmt = select(RefreshToken).where(
        RefreshToken.token == refresh_token,
        RefreshToken.revoked_at.is_(None),
    )
    db_token = db.execute(token_stmt).scalar_one_or_none()

    if db_token is None:
        logger.warning(f"Token refresh failed: Token not found or revoked (user_id={user_id})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌已失效，请重新登录",
        )

    # Generate new access token
    new_access_token = create_access_token(data={"sub": user_id})

    logger.info(f"Token refreshed successfully for user_id: {user_id}")

    return RefreshResponse(
        success=True,
        message="令牌刷新成功",
        access_token=new_access_token,
        expires_in=ACCESS_TOKEN_EXPIRES_IN,
    )


# ============================================================================
# Logout Endpoint
# ============================================================================

@router.post("/logout", response_model=LogoutResponse)
async def logout(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_db),
) -> LogoutResponse:
    """
    Logout user by revoking their refresh token.

    This endpoint marks the refresh token as revoked. The client should
    discard both access and refresh tokens after logout.

    Args:
        refresh_data: Refresh token to revoke
        db: Database session

    Returns:
        LogoutResponse with success message

    Example:
        POST /api/v2/auth/logout
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
    """
    refresh_token = refresh_data.refresh_token

    # Find the refresh token in database
    from sqlalchemy import select

    token_stmt = select(RefreshToken).where(
        RefreshToken.token == refresh_token,
        RefreshToken.revoked_at.is_(None),
    )
    db_token = db.execute(token_stmt).scalar_one_or_none()

    if db_token is None:
        # Token not found or already revoked - still return success for idempotency
        logger.info("Logout attempted with non-existent or already revoked token")
        return LogoutResponse(
            success=True,
            message="退出登录成功",
        )

    # Revoke the token
    db_token.revoked_at = datetime.now()
    db.commit()

    logger.info(f"User logged out: revoked token for user_id {db_token.user_id}")

    return LogoutResponse(
        success=True,
        message="退出登录成功",
    )


# ============================================================================
# WeChat Mini-Program Login Endpoint (US-159)
# ============================================================================

@router.post("/wechat", response_model=LoginResponse)
async def wechat_login(
    wechat_data: WeChatLoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    WeChat mini-program login endpoint.

    This endpoint handles WeChat mini-program authentication:
    1. Receives WeChat login code from frontend (wx.login())
    2. Exchanges code for OpenID via WeChat API
    3. Finds or creates user account
    4. Returns JWT tokens

    Args:
        wechat_data: WeChat login data (code, optional nickname, optional avatar_url)
        db: Database session

    Returns:
        LoginResponse with access_token, refresh_token, and user info

    Raises:
        HTTPException 400: If WeChat API call fails
        HTTPException 500: If server error occurs

    Example:
        POST /api/v2/auth/wechat
        {
            "code": "0x1234567890",
            "nickname": "微信用户",
            "avatar_url": "https://..."
        }
    """
    # Import here to avoid circular imports
    from api_service.app.core.miniprogram import wechat_code2session

    try:
        # Exchange code for OpenID
        openid, session_key = wechat_code2session(wechat_data.code)
    except ValueError as e:
        logger.error(f"WeChat code2session failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信登录失败: {str(e)}",
        )

    # Check if user exists
    user = get_user_by_openid(db, openid=openid, openid_type="wechat")

    if user is None:
        # Create new user
        try:
            nickname = wechat_data.nickname or "微信用户"
            user = create_user(
                db,
                openid=openid,
                openid_type="wechat",
                nickname=nickname,
                avatar_url=wechat_data.avatar_url,
            )
            logger.info(f"New WeChat user created: {user.id} (openid={openid})")
        except Exception as e:
            logger.error(f"Failed to create WeChat user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建用户失败",
            )
    else:
        # Update existing user info if provided
        if wechat_data.nickname or wechat_data.avatar_url:
            user = update_user(
                db,
                user,
                nickname=wechat_data.nickname,
                avatar_url=wechat_data.avatar_url,
            )
            logger.info(f"WeChat user info updated: {user.id}")

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token in database
    # Revoke any existing active refresh tokens for this user
    from sqlalchemy import select
    from sqlalchemy import and_

    existing_tokens_stmt = select(RefreshToken).where(
        and_(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    existing_tokens = db.execute(existing_tokens_stmt).scalars().all()

    # Revoke old tokens for security
    for old_token in existing_tokens:
        old_token.revoked_at = datetime.now()

    # Add new refresh token
    db_refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh_token)
    db.commit()

    logger.info(f"WeChat user logged in: {user.id}")

    return LoginResponse(
        success=True,
        message="登录成功",
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo.model_validate(user),
    )


# ============================================================================
# Douyin Mini-Program Login Endpoint (US-160)
# ============================================================================

@router.post("/douyin", response_model=LoginResponse)
async def douyin_login(
    douyin_data: DouyinLoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    Douyin mini-program login endpoint.

    This endpoint handles Douyin mini-program authentication:
    1. Receives Douyin login code from frontend (tt.login())
    2. Exchanges code for OpenID via Douyin API
    3. Finds or creates user account
    4. Returns JWT tokens

    Args:
        douyin_data: Douyin login data (code, optional nickname, optional avatar_url)
        db: Database session

    Returns:
        LoginResponse with access_token, refresh_token, and user info

    Raises:
        HTTPException 400: If Douyin API call fails
        HTTPException 500: If server error occurs

    Example:
        POST /api/v2/auth/douyin
        {
            "code": "1234567890",
            "nickname": "抖音用户",
            "avatar_url": "https://..."
        }
    """
    # Import here to avoid circular imports
    from api_service.app.core.miniprogram import douyin_code2session

    try:
        # Exchange code for OpenID
        openid = douyin_code2session(douyin_data.code)
    except ValueError as e:
        logger.error(f"Douyin code2session failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"抖音登录失败: {str(e)}",
        )

    # Check if user exists
    user = get_user_by_openid(db, openid=openid, openid_type="douyin")

    if user is None:
        # Create new user
        try:
            nickname = douyin_data.nickname or "抖音用户"
            user = create_user(
                db,
                openid=openid,
                openid_type="douyin",
                nickname=nickname,
                avatar_url=douyin_data.avatar_url,
            )
            logger.info(f"New Douyin user created: {user.id} (openid={openid})")
        except Exception as e:
            logger.error(f"Failed to create Douyin user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建用户失败",
            )
    else:
        # Update existing user info if provided
        if douyin_data.nickname or douyin_data.avatar_url:
            user = update_user(
                db,
                user,
                nickname=douyin_data.nickname,
                avatar_url=douyin_data.avatar_url,
            )
            logger.info(f"Douyin user info updated: {user.id}")

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token in database
    # Revoke any existing active refresh tokens for this user
    from sqlalchemy import select
    from sqlalchemy import and_

    existing_tokens_stmt = select(RefreshToken).where(
        and_(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    existing_tokens = db.execute(existing_tokens_stmt).scalars().all()

    # Revoke old tokens for security
    for old_token in existing_tokens:
        old_token.revoked_at = datetime.now()

    # Add new refresh token
    db_refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh_token)
    db.commit()

    logger.info(f"Douyin user logged in: {user.id}")

    return LoginResponse(
        success=True,
        message="登录成功",
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserInfo.model_validate(user),
    )


__all__ = ["router"]
