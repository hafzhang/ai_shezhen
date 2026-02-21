#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Health Records Endpoints
AI舌诊智能诊断系统 - Health Records API v2
Phase 2: Data Persistence - US-128

This module provides health records management endpoints:
- GET /api/v2/health-records - List user's health records
- POST /api/v2/health-records - Create new health record
- PUT /api/v2/health-records/{id} - Update health record
- DELETE /api/v2/health-records/{id} - Delete health record

Usage:
    import uvicorn
    from api_service.app.api.v2.health_records import router

    app.include_router(router, prefix="/api/v2/health-records")
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from uuid import UUID

from api_service.app.api.deps import get_db, get_current_user
from api_service.app.models.database import User, HealthRecord, HealthRecordType
from api_service.app.api.v2.models import APIResponse

# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()


# ============================================================================
# Pydantic Models for Health Records
# ============================================================================

class HealthRecordType(str, Enum):
    """Health record type enum"""

    BLOOD_PRESSURE = "blood_pressure"
    HEART_RATE = "heart_rate"
    WEIGHT = "weight"
    HEIGHT = "height"
    TEMPERATURE = "temperature"
    BLOOD_SUGAR = "blood_sugar"
    SYMPTOMS = "symptoms"
    MEDICATION = "medication"
    LAB_RESULTS = "lab_results"
    OTHER = "other"


class HealthRecordCreate(BaseModel):
    """Health record creation request"""

    record_type: HealthRecordType = Field(..., description="Record type")
    record_value: Dict[str, Any] = Field(..., description="Record value (flexible JSON)")
    record_date: Optional[str] = Field(None, description="Record date (ISO 8601)")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional notes")


class HealthRecordUpdate(BaseModel):
    """Health record update request"""

    record_value: Optional[Dict[str, Any]] = Field(None, description="Record value (flexible JSON)")
    record_date: Optional[str] = Field(None, description="Record date (ISO 8601)")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional notes")


class HealthRecordItem(BaseModel):
    """Health record item"""

    id: str
    user_id: str
    record_type: str
    record_value: Dict[str, Any]
    record_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class HealthRecordListResponse(APIResponse):
    """Health records list response"""

    total: int
    items: List[HealthRecordItem]


class HealthRecordResponse(APIResponse):
    """Single health record response"""

    record: HealthRecordItem


# ============================================================================
# GET /api/v2/health-records
# ============================================================================

@router.get("", response_model=HealthRecordListResponse, tags=["Health Records"])
async def get_health_records(
    record_type: Optional[HealthRecordType] = Query(None, description="Filter by record type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's health records.

    Returns a list of health records for the authenticated user.
    Can be filtered by record type.

    Args:
        record_type: Optional filter by record type
        limit: Maximum number of records to return
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        HealthRecordListResponse with list of records

    Raises:
        HTTPException 401: If not authenticated

    Example:
        GET /api/v2/health-records?record_type=blood_pressure&limit=20
    """
    try:
        # Build query
        query = db.query(HealthRecord).filter(
            HealthRecord.user_id == current_user.id
        )

        # Apply record type filter if provided
        if record_type:
            query = query.filter(HealthRecord.record_type == record_type.value)

        # Order by created_at DESC (newest first) and limit
        records = query.order_by(desc(HealthRecord.created_at)).limit(limit).all()

        # Get total count
        total = query.count()

        # Format response items
        formatted_items = [
            HealthRecordItem(
                id=str(record.id),
                user_id=str(record.user_id),
                record_type=record.record_type,
                record_value=record.record_value,
                record_date=record.record_date.isoformat() if record.record_date else None,
                notes=record.notes,
                created_at=record.created_at.isoformat(),
                updated_at=record.updated_at.isoformat()
            )
            for record in records
        ]

        return HealthRecordListResponse(
            success=True,
            total=total,
            items=formatted_items
        )

    except Exception as e:
        logger.error(f"Error getting health records: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve health records: {str(e)}"
        )


# ============================================================================
# POST /api/v2/health-records
# ============================================================================

@router.post("", response_model=HealthRecordResponse, tags=["Health Records"], status_code=status.HTTP_201_CREATED)
async def create_health_record(
    record: HealthRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new health record.

    Creates a new health record for the authenticated user.
    The record_value is a flexible JSON structure that can contain
    any data relevant to the record type.

    Args:
        record: Health record creation data
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        HealthRecordResponse with created record

    Raises:
        HTTPException 400: If record data is invalid
        HTTPException 401: If not authenticated

    Example:
        POST /api/v2/health-records
        {
            "record_type": "blood_pressure",
            "record_value": {"systolic": 120, "diastolic": 80, "unit": "mmHg"},
            "record_date": "2026-02-21T10:00:00Z",
            "notes": "Measured in the morning"
        }
    """
    try:
        # Parse record_date if provided
        record_date = None
        if record.record_date:
            try:
                record_date = datetime.fromisoformat(record.record_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid record_date format. Use ISO 8601 format (e.g., 2026-01-01T00:00:00Z)"
                )

        # Create health record
        health_record = HealthRecord(
            user_id=current_user.id,
            record_type=record.record_type.value,
            record_value=record.record_value,
            record_date=record_date,
            notes=record.notes
        )

        db.add(health_record)
        db.commit()
        db.refresh(health_record)

        logger.info(
            f"Health record created: id={health_record.id}, "
            f"user={current_user.id}, type={record.record_type.value}"
        )

        # Format response
        formatted_record = HealthRecordItem(
            id=str(health_record.id),
            user_id=str(health_record.user_id),
            record_type=health_record.record_type,
            record_value=health_record.record_value,
            record_date=health_record.record_date.isoformat() if health_record.record_date else None,
            notes=health_record.notes,
            created_at=health_record.created_at.isoformat(),
            updated_at=health_record.updated_at.isoformat()
        )

        return HealthRecordResponse(
            success=True,
            message="Health record created successfully",
            record=formatted_record
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating health record: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create health record: {str(e)}"
        )


# ============================================================================
# PUT /api/v2/health-records/{id}
# ============================================================================

@router.put("/{record_id}", response_model=HealthRecordResponse, tags=["Health Records"])
async def update_health_record(
    record_id: str,
    record_update: HealthRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing health record.

    Updates the specified fields of a health record.
    Only the owner of the record can update it.

    Args:
        record_id: UUID of the health record
        record_update: Fields to update
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        HealthRecordResponse with updated record

    Raises:
        HTTPException 400: If record_id format is invalid
        HTTPException 401: If not authenticated
        HTTPException 403: If record belongs to another user
        HTTPException 404: If record not found

    Example:
        PUT /api/v2/health-records/123e4567-e89b-12d3-a456-426614174000
        {
            "record_value": {"systolic": 118, "diastolic": 78, "unit": "mmHg"},
            "notes": "Updated measurement"
        }
    """
    try:
        # Validate UUID format
        try:
            record_uuid = UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid record ID format. Must be a valid UUID."
            )

        # Query health record
        health_record = db.query(HealthRecord).filter(
            HealthRecord.id == record_uuid
        ).first()

        if health_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Health record not found"
            )

        # Verify ownership
        if health_record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this record"
            )

        # Update fields if provided
        if record_update.record_value is not None:
            health_record.record_value = record_update.record_value

        if record_update.record_date is not None:
            try:
                health_record.record_date = datetime.fromisoformat(
                    record_update.record_date.replace('Z', '+00:00')
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid record_date format. Use ISO 8601 format."
                )

        if record_update.notes is not None:
            health_record.notes = record_update.notes

        db.commit()
        db.refresh(health_record)

        logger.info(
            f"Health record updated: id={health_record.id}, "
            f"user={current_user.id}"
        )

        # Format response
        formatted_record = HealthRecordItem(
            id=str(health_record.id),
            user_id=str(health_record.user_id),
            record_type=health_record.record_type,
            record_value=health_record.record_value,
            record_date=health_record.record_date.isoformat() if health_record.record_date else None,
            notes=health_record.notes,
            created_at=health_record.created_at.isoformat(),
            updated_at=health_record.updated_at.isoformat()
        )

        return HealthRecordResponse(
            success=True,
            message="Health record updated successfully",
            record=formatted_record
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating health record: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update health record: {str(e)}"
        )


# ============================================================================
# DELETE /api/v2/health-records/{id}
# ============================================================================

@router.delete("/{record_id}", response_model=APIResponse, tags=["Health Records"])
async def delete_health_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a health record.

    Permanently deletes the specified health record.
    Only the owner of the record can delete it.

    Args:
        record_id: UUID of the health record
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        APIResponse confirming deletion

    Raises:
        HTTPException 400: If record_id format is invalid
        HTTPException 401: If not authenticated
        HTTPException 403: If record belongs to another user
        HTTPException 404: If record not found

    Example:
        DELETE /api/v2/health-records/123e4567-e89b-12d3-a456-426614174000
    """
    try:
        # Validate UUID format
        try:
            record_uuid = UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid record ID format. Must be a valid UUID."
            )

        # Query health record
        health_record = db.query(HealthRecord).filter(
            HealthRecord.id == record_uuid
        ).first()

        if health_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Health record not found"
            )

        # Verify ownership
        if health_record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this record"
            )

        # Delete record
        db.delete(health_record)
        db.commit()

        logger.info(
            f"Health record deleted: id={record_id}, "
            f"user={current_user.id}"
        )

        return APIResponse(
            success=True,
            message="Health record deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting health record: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete health record: {str(e)}"
        )


__all__ = [
    "router",
]
