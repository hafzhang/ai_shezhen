#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mini-Program Authentication Helper Module
AI舌诊智能诊断系统 - Mini-Program Authentication
Phase 3: uni-app Frontend - US-159, US-160

This module provides helper functions for mini-program authentication:
- WeChat mini-program code2session (code to openid/session_key)
- Douyin mini-program code2session
- OpenID extraction and validation

Usage:
    from api_service.app.core.miniprogram import (
        wechat_code2session,
        douyin_code2session,
    )

    # Exchange WeChat code for OpenID
    openid, session_key = wechat_code2session("0x1234567890")
"""

import logging
import httpx
from typing import Tuple, Optional
from api_service.app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# WeChat Mini-Program Authentication
# ============================================================================

def wechat_code2session(code: str) -> Tuple[str, Optional[str]]:
    """
    Exchange WeChat login code for OpenID and session_key.

    Calls WeChat's code2session API to exchange the temporary login code
    for user's OpenID and session_key. The OpenID is unique per user per app.

    Args:
        code: Login code from wx.login()

    Returns:
        Tuple of (openid, session_key) - session_key may be None if error

    Raises:
        HTTPException: If API call fails or returns invalid response

    WeChat API Documentation:
        https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2session.html

    Example:
        >>> openid, session_key = wechat_code2session("0x1234567890")
        >>> print(f"User OpenID: {openid}")
    """
    # WeChat code2session API endpoint
    url = "https://api.weixin.qq.com/sns/jscode2session"

    # Build request parameters
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code"
    }

    try:
        # Make synchronous HTTP request (using httpx)
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # Check for API errors
        if "errcode" in data and data["errcode"] != 0:
            error_msg = data.get("errmsg", "Unknown error")
            logger.error(f"WeChat API error: {data['errcode']} - {error_msg}")
            raise ValueError(f"WeChat API error: {error_msg}")

        # Extract OpenID and session_key
        openid = data.get("openid")
        session_key = data.get("session_key")

        if not openid:
            logger.error("WeChat API response missing openid")
            raise ValueError("Invalid response from WeChat API: missing openid")

        logger.info(f"WeChat code2session successful for openid: {openid}")
        return openid, session_key

    except httpx.HTTPStatusError as e:
        logger.error(f"WeChat API HTTP error: {e.response.status_code}")
        raise ValueError(f"WeChat API request failed: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"WeChat API request error: {e}")
        raise ValueError("Failed to connect to WeChat API")
    except Exception as e:
        logger.error(f"WeChat code2session error: {e}")
        raise


# ============================================================================
# Douyin Mini-Program Authentication
# ============================================================================

def douyin_code2session(code: str) -> str:
    """
    Exchange Douyin login code for OpenID.

    Calls Douyin's code2session API to exchange the temporary login code
    for user's OpenID. The OpenID is unique per user per app.

    Args:
        code: Login code from tt.login()

    Returns:
        OpenID string

    Raises:
        HTTPException: If API call fails or returns invalid response

    Douyin API Documentation:
        https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/server/interface-login

    Example:
        >>> openid = douyin_code2session("1234567890")
        >>> print(f"User OpenID: {openid}")
    """
    # Douyin code2session API endpoint
    url = "https://developer.toutiao.com/api/apps/jscode2session"

    # Build request parameters
    params = {
        "appid": settings.douyin_appid,
        "secret": settings.douyin_secret,
        "code": code,
        "anonymous_code": ""  # Optional anonymous code
    }

    try:
        # Make synchronous HTTP request
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # Check for API errors
        if "errno" in data and data["errno"] != 0:
            error_msg = data.get("errmsg", "Unknown error")
            logger.error(f"Douyin API error: {data['errno']} - {error_msg}")
            raise ValueError(f"Douyin API error: {error_msg}")

        # Extract OpenID
        openid = data.get("openid")

        if not openid:
            logger.error("Douyin API response missing openid")
            raise ValueError("Invalid response from Douyin API: missing openid")

        logger.info(f"Douyin code2session successful for openid: {openid}")
        return openid

    except httpx.HTTPStatusError as e:
        logger.error(f"Douyin API HTTP error: {e.response.status_code}")
        raise ValueError(f"Douyin API request failed: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Douyin API request error: {e}")
        raise ValueError("Failed to connect to Douyin API")
    except Exception as e:
        logger.error(f"Douyin code2session error: {e}")
        raise


__all__ = [
    "wechat_code2session",
    "douyin_code2session",
]
