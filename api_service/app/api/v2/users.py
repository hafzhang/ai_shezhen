#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Users Endpoints
AI舌诊智能诊断系统 - Users API v2
Phase 2: Data Persistence - US-129

This module provides user management endpoints:
- GET /api/v2/users/me - Get current user info
- PUT /api/v2/users/me - Update current user info
- DELETE /api/v2/users/me - Delete account (soft delete)

Usage:
    import uvicorn
    from api_service.app.api.v2.users import router

    app.include_router(router, prefix="/api/v2/users")
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr, field_validator
from sqlalchemy.orm import Session
from uuid import UUID

from api_service.app.api.deps import get_db, get_current_user
from api_service.app.models.database import User
from api_service.app.api.v2.models import APIResponse

# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()


# ============================================================================
# Pydantic Models for User Management
# ============================================================================

class UserUpdate(BaseModel):
    """User update request"""

    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format if provided"""
        if v is not None:
            import re
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
                raise ValueError('邮箱格式不正确')
        return v


class UserInfoResponse(BaseModel):
    """User info response"""

    id: str
    phone: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    openid: Optional[str] = None
    openid_type: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserMeResponse(APIResponse):
    """Current user info response"""

    user: UserInfoResponse


class UserDeleteResponse(APIResponse):
    """User delete response"""

    message: str = "Account deleted successfully"


# ============================================================================
# GET /api/v2/users/me
# ============================================================================

@router.get("/me", response_model=UserMeResponse, tags=["Users"])
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information.

    Returns the profile information of the authenticated user.

    Args:
        current_user: Authenticated user (injected via dependency)

    Returns:
        UserMeResponse with user information

    Raises:
        HTTPException 401: If not authenticated

    Example:
        GET /api/v2/users/me
    """
    try:
        user_info = UserInfoResponse(
            id=str(current_user.id),
            phone=current_user.phone,
            email=current_user.email,
            nickname=current_user.nickname,
            avatar_url=current_user.avatar_url,
            openid=current_user.openid,
            openid_type=current_user.openid_type,
            created_at=current_user.created_at.isoformat(),
            updated_at=current_user.updated_at.isoformat()
        )

        return UserMeResponse(
            success=True,
            user=user_info
        )

    except Exception as e:
        logger.error(f"Error getting user info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user information: {str(e)}"
        )


# ============================================================================
# PUT /api/v2/users/me
# ============================================================================

@router.put("/me", response_model=UserMeResponse, tags=["Users"])
async def update_current_user_info(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update current user information.

    Updates the specified fields of the authenticated user's profile.
    At least one field must be provided for update.

    Args:
        user_update: Fields to update
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        UserMeResponse with updated user information

    Raises:
        HTTPException 400: If no fields provided or validation fails
        HTTPException 401: If not authenticated
        HTTPException 409: If email/phone already exists

    Example:
        PUT /api/v2/users/me
        {
            "nickname": "新昵称",
            "email": "new@example.com"
        }
    """
    try:
        # Check if at least one field is provided
        if all(v is None for v in [user_update.nickname, user_update.email, user_update.phone]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update"
            )

        # Check email uniqueness if being updated
        if user_update.email is not None:
            existing = db.query(User).filter(
                User.email == user_update.email,
                User.id != current_user.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered by another user"
                )

        # Check phone uniqueness if being updated
        if user_update.phone is not None:
            existing = db.query(User).filter(
                User.phone == user_update.phone,
                User.id != current_user.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number already registered by another user"
                )

        # Update fields if provided
        if user_update.nickname is not None:
            current_user.nickname = user_update.nickname

        if user_update.email is not None:
            current_user.email = user_update.email

        if user_update.phone is not None:
            current_user.phone = user_update.phone

        # Update updated_at timestamp
        current_user.updated_at = datetime.now()

        db.commit()
        db.refresh(current_user)

        logger.info(f"User info updated: id={current_user.id}")

        # Format response
        user_info = UserInfoResponse(
            id=str(current_user.id),
            phone=current_user.phone,
            email=current_user.email,
            nickname=current_user.nickname,
            avatar_url=current_user.avatar_url,
            openid=current_user.openid,
            openid_type=current_user.openid_type,
            created_at=current_user.created_at.isoformat(),
            updated_at=current_user.updated_at.isoformat()
        )

        return UserMeResponse(
            success=True,
            message="User information updated successfully",
            user=user_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user info: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user information: {str(e)}"
        )


# ============================================================================
# DELETE /api/v2/users/me
# ============================================================================

@router.delete("/me", response_model=UserDeleteResponse, tags=["Users"])
async def delete_current_user_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete current user account (soft delete).

    Soft deletes the authenticated user's account by setting the
    deleted_at timestamp. The account data is retained but marked
    as deleted for compliance purposes.

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        UserDeleteResponse confirming deletion

    Raises:
        HTTPException 401: If not authenticated

    Example:
        DELETE /api/v2/users/me
    """
    try:
        # Soft delete by setting deleted_at
        current_user.deleted_at = datetime.now()

        db.commit()

        logger.info(
            f"User account deleted (soft): id={current_user.id}, "
            f"phone={current_user.phone}"
        )

        return UserDeleteResponse(
            success=True,
            message="Account deleted successfully"
        )

    except Exception as e:
        logger.error(f"Error deleting user account: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )


__all__ = [
    "router",
]
