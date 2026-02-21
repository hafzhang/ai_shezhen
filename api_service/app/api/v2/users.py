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
import hashlib
import base64
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr, field_validator
from sqlalchemy.orm import Session
from uuid import UUID

from api_service.app.api.deps import get_db, get_current_user
from api_service.app.models.database import User
from api_service.app.api.v2.models import APIResponse
from api_service.core.config import settings

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


# ============================================================================
# Avatar Upload Endpoints (US-130)
# ============================================================================

class AvatarUploadRequest(BaseModel):
    """Avatar upload request"""

    image_data: str = Field(..., description="Base64 encoded image data (without data URL prefix)")


class AvatarUploadResponse(APIResponse):
    """Avatar upload response"""

    avatar_url: str = Field(..., description="URL of the uploaded avatar")


class AvatarInfoResponse(APIResponse):
    """Avatar info response"""

    avatar_url: Optional[str] = None
    has_avatar: bool


# Helper function to save avatar image
def save_avatar_image(user_id: str, image_data: str) -> str:
    """
    Save avatar image to filesystem.

    Args:
        user_id: User UUID
        image_data: Base64 encoded image data (without data URL prefix)

    Returns:
        Relative URL path to the saved avatar
    """
    try:
        # Decode base64 image data
        image_bytes = base64.b64decode(image_data)

        # Calculate SHA-256 hash for unique filename
        file_hash = hashlib.sha256(image_bytes).hexdigest()[:16]

        # Create avatar filename
        filename = f"avatar_{user_id}_{file_hash}.png"

        # Create avatar directory if not exists
        avatar_dir = settings.BASE_DIR / settings.MEDIA_ROOT / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # Save image file
        file_path = avatar_dir / filename
        with open(file_path, "wb") as f:
            f.write(image_bytes)

        # Return relative URL path
        return f"/media/avatars/{filename}"

    except Exception as e:
        logger.error(f"Error saving avatar image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save avatar image: {str(e)}"
        )


@router.get("/me/avatar", response_model=AvatarInfoResponse, tags=["Users"])
async def get_avatar_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's avatar information.

    Returns whether the user has an avatar and the avatar URL.

    Args:
        current_user: Authenticated user (injected via dependency)

    Returns:
        AvatarInfoResponse with avatar URL and status

    Raises:
        HTTPException 401: If not authenticated
    """
    try:
        return AvatarInfoResponse(
            success=True,
            avatar_url=current_user.avatar_url,
            has_avatar=current_user.avatar_url is not None
        )
    except Exception as e:
        logger.error(f"Error getting avatar info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve avatar info: {str(e)}"
        )


@router.put("/me/avatar", response_model=AvatarUploadResponse, tags=["Users"])
async def upload_avatar(
    avatar_request: AvatarUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload or update current user's avatar.

    Accepts a base64 encoded image and saves it to the filesystem.
    The avatar URL is stored in the user's profile.

    Args:
        avatar_request: Avatar upload request with base64 image data
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        AvatarUploadResponse with avatar URL

    Raises:
        HTTPException 400: If image data is invalid
        HTTPException 401: If not authenticated
        HTTPException 500: If save fails

    Example:
        PUT /api/v2/users/me/avatar
        {
            "image_data": "iVBORw0KGgoAAAANSUhEUgAA..."
        }
    """
    try:
        # Remove data URL prefix if present
        image_data = avatar_request.image_data
        if image_data.startswith("data:"):
            # Extract base64 data after comma
            image_data = image_data.split(",", 1)[1]

        # Save avatar image
        avatar_url = save_avatar_image(str(current_user.id), image_data)

        # Update user's avatar_url
        current_user.avatar_url = avatar_url
        current_user.updated_at = datetime.now()
        db.commit()
        db.refresh(current_user)

        logger.info(f"Avatar uploaded for user: {current_user.id}")

        return AvatarUploadResponse(
            success=True,
            message="Avatar uploaded successfully",
            avatar_url=avatar_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar: {str(e)}"
        )


@router.delete("/me/avatar", response_model=APIResponse, tags=["Users"])
async def delete_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete current user's avatar.

    Removes the avatar URL from the user's profile.
    The image file is not deleted from filesystem.

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        APIResponse confirming deletion

    Raises:
        HTTPException 401: If not authenticated

    Example:
        DELETE /api/v2/users/me/avatar
    """
    try:
        # Clear avatar_url
        current_user.avatar_url = None
        current_user.updated_at = datetime.now()
        db.commit()

        logger.info(f"Avatar deleted for user: {current_user.id}")

        return APIResponse(
            success=True,
            message="Avatar deleted successfully"
        )

    except Exception as e:
        logger.error(f"Error deleting avatar: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete avatar: {str(e)}"
        )
