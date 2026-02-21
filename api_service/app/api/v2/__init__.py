#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Package
AI舌诊智能诊断系统 - API v2
Phase 2: Database & Auth

This package contains API v2 endpoints for:
- Authentication (register, login, refresh, logout)
- User management
- Diagnosis history
- Health records
"""

from api_service.app.api.v2.models import *

__all__ = [
    # Export all models
    "UserRegister",
    "UserLogin",
    "RefreshRequest",
    "UserInfo",
    "TokenResponse",
    "APIResponse",
    "AuthResponse",
    "RegisterResponse",
    "LoginResponse",
    "RefreshResponse",
    "LogoutResponse",
]
