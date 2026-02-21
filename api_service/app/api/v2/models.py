#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Pydantic Models
AI舌诊智能诊断系统 - API v2 Models
Phase 2: Database & Auth - US-117

This module defines Pydantic models for API v2 endpoints:
- Authentication models (register, login, token, refresh)
- User models (response, update)
- Response wrapper models

Usage:
    from api_service.app.api.v2.models import (
        UserRegister,
        UserLogin,
        TokenResponse,
        RefreshRequest,
    )

    # Validate user registration input
    user_data = UserRegister(
        phone="13800138000",
        password="securepass123",
        nickname="张三"
    )
"""

import re
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Authentication Request Models
# ============================================================================

class UserRegister(BaseModel):
    """
    User registration request model.

    Validates user registration input including phone number validation,
    password requirements, and optional email.

    Attributes:
        phone: Mobile phone number (Chinese format: 11 digits, starts with 1)
        password: User password (min 8 characters, letters + numbers)
        nickname: User display name (optional, defaults to phone number)
        email: User email address (optional)

    Example:
        >>> user = UserRegister(
        ...     phone="13800138000",
        ...     password="abc12345",
        ...     nickname="张三"
        ... )
    """

    phone: str = Field(
        ...,
        description="手机号（11位数字，以1开头）",
        min_length=11,
        max_length=11,
        pattern=r'^1[3-9]\d{9}$'
    )
    password: str = Field(
        ...,
        description="密码（至少8位，包含字母和数字）",
        min_length=8
    )
    nickname: Optional[str] = Field(
        None,
        description="昵称",
        max_length=50
    )
    email: Optional[str] = Field(
        None,
        description="邮箱地址"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        Validate Chinese mobile phone number format.

        Chinese mobile numbers:
        - Start with 1
        - Second digit is 3-9
        - Total 11 digits

        Args:
            v: Phone number string

        Returns:
            Validated phone number

        Raises:
            ValueError: If phone number format is invalid
        """
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确，请输入11位有效的手机号码')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength requirements.

        Password must:
        - Be at least 8 characters long
        - Contain both letters and numbers

        Args:
            v: Password string

        Returns:
            Validated password

        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(v) < 8:
            raise ValueError('密码长度至少为8位')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('密码必须包含字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate email format if provided.

        Args:
            v: Email string or None

        Returns:
            Validated email or None

        Raises:
            ValueError: If email format is invalid
        """
        if v is not None and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('邮箱格式不正确')
        return v


class UserLogin(BaseModel):
    """
    User login request model.

    Validates user login credentials.

    Attributes:
        phone: Mobile phone number (11 digits)
        password: User password

    Example:
        >>> login = UserLogin(phone="13800138000", password="abc12345")
    """

    phone: str = Field(
        ...,
        description="手机号",
        min_length=11,
        max_length=11
    )
    password: str = Field(
        ...,
        description="密码",
        min_length=1
    )


class RefreshRequest(BaseModel):
    """
    Token refresh request model.

    Used to obtain a new access token using a valid refresh token.

    Attributes:
        refresh_token: JWT refresh token string

    Example:
        >>> refresh = RefreshRequest(refresh_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    """

    refresh_token: str = Field(
        ...,
        description="刷新令牌",
        min_length=1
    )


# ============================================================================
# Authentication Response Models
# ============================================================================

class UserInfo(BaseModel):
    """
    User information response model.

    Contains basic user profile information returned after login/registration.

    Attributes:
        id: User UUID
        phone: User phone number (optional for mini-program users)
        email: User email (optional)
        nickname: User display name
        avatar_url: Profile image URL (optional)
        openid: OpenID for mini-program (optional)
        openid_type: OpenID provider type ("wechat" or "douyin", optional)

    Example:
        >>> user_info = UserInfo(
        ...     id="123e4567-e89b-12d3-a456-426614174000",
        ...     phone="13800138000",
        ...     nickname="张三"
        ... )
    """

    id: UUID = Field(..., description="用户ID")
    phone: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, description="昵称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    openid: Optional[str] = Field(None, description="OpenID（小程序用户）")
    openid_type: Optional[str] = Field(None, description="OpenID类型（wechat/douyin）")

    model_config = {
        "from_attributes": True  # Enable ORM mode for SQLAlchemy models
    }


class TokenResponse(BaseModel):
    """
    Token response model.

    Returned after successful login or registration.
    Contains access token, refresh token, and user info.

    Attributes:
        access_token: JWT access token (30 minutes validity)
        refresh_token: JWT refresh token (7 days validity)
        token_type: Token type (always "bearer")
        expires_in: Access token expiration time in seconds
        user: User information

    Example:
        >>> tokens = TokenResponse(
        ...     access_token="eyJhbGci...",
        ...     refresh_token="eyJhbGci...",
        ...     token_type="bearer",
        ...     expires_in=1800,
        ...     user=UserInfo(id=..., phone="13800138000", ...)
        ... )
    """

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(default=1800, description="访问令牌过期时间（秒）")
    user: UserInfo = Field(..., description="用户信息")


# ============================================================================
# Unified Response Models
# ============================================================================

class APIResponse(BaseModel):
    """
    Unified API response model for v2 endpoints.

    Provides consistent response structure across all v2 APIs.

    Attributes:
        success: Whether the request was successful
        message: Optional success message
        error: Optional error type/code
        detail: Optional error details

    Example:
        >>> response = APIResponse(success=True, message="操作成功")
    """

    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    error: Optional[str] = Field(None, description="错误类型")
    detail: Optional[str] = Field(None, description="错误详情")


class AuthResponse(APIResponse):
    """
    Authentication response model with optional data field.

    Extends APIResponse to include authentication-related data.

    Attributes:
        data: Optional data payload (e.g., TokenResponse for login/register)

    Example:
        >>> response = AuthResponse(
        ...     success=True,
        ...     message="登录成功",
        ...     data=TokenResponse(...)
        ... )
    """

    data: Optional[dict] = Field(None, description="响应数据")


# ============================================================================
# Response Wrapper Models
# ============================================================================

class RegisterResponse(APIResponse):
    """
    User registration response model.

    Returns tokens and user info after successful registration.

    Attributes:
        access_token: JWT access token
        refresh_token: JWT refresh token
        user: User information

    Example:
        >>> response = RegisterResponse(
        ...     success=True,
        ...     message="注册成功",
        ...     access_token="eyJhbGci...",
        ...     refresh_token="eyJhbGci...",
        ...     user=UserInfo(...)
        ... )
    """

    access_token: Optional[str] = Field(None, description="访问令牌")
    refresh_token: Optional[str] = Field(None, description="刷新令牌")
    user: Optional[UserInfo] = Field(None, description="用户信息")


class LoginResponse(APIResponse):
    """
    User login response model.

    Returns tokens and user info after successful login.

    Attributes:
        access_token: JWT access token
        refresh_token: JWT refresh token
        user: User information

    Example:
        >>> response = LoginResponse(
        ...     success=True,
        ...     message="登录成功",
        ...     access_token="eyJhbGci...",
        ...     refresh_token="eyJhbGci...",
        ...     user=UserInfo(...)
        ... )
    """

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    user: UserInfo = Field(..., description="用户信息")


class RefreshResponse(APIResponse):
    """
    Token refresh response model.

    Returns new access token after successful refresh.

    Attributes:
        access_token: New JWT access token
        expires_in: Access token expiration time in seconds

    Example:
        >>> response = RefreshResponse(
        ...     success=True,
        ...     message="令牌刷新成功",
        ...     access_token="eyJhbGci...",
        ...     expires_in=1800
        ... )
    """

    access_token: str = Field(..., description="新的访问令牌")
    expires_in: int = Field(default=1800, description="访问令牌过期时间（秒）")


class LogoutResponse(APIResponse):
    """
    User logout response model.

    Returns success message after logout.

    Attributes:
        message: Logout success message

    Example:
        >>> response = LogoutResponse(
        ...     success=True,
        ...     message="退出登录成功"
        ... )
    """

    message: str = Field(default="退出登录成功", description="响应消息")


__all__ = [
    # Request models
    "UserRegister",
    "UserLogin",
    "RefreshRequest",
    # Response models
    "UserInfo",
    "TokenResponse",
    "APIResponse",
    "AuthResponse",
    "RegisterResponse",
    "LoginResponse",
    "RefreshResponse",
    "LogoutResponse",
]
