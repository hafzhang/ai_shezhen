#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 History Endpoints
AI舌诊智能诊断系统 - History API v2
Phase 2: Data Persistence - US-123

This module provides diagnosis history query endpoints:
- GET /api/v2/history/diagnoses - Query diagnosis history with pagination
- GET /api/v2/history/statistics - Get health statistics
- GET /api/v2/history/trends - Get health trends over time

Usage:
    import uvicorn
    from api_service.app.api.v2.history import router

    app.include_router(router, prefix="/api/v2/history")
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_, case
from pydantic import BaseModel

from api_service.app.api.deps import get_db, get_current_user
from api_service.app.models.database import User, DiagnosisHistory
from api_service.app.api.v2.models import APIResponse

# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()


# ============================================================================
# Pydantic Models for History Endpoints
# ============================================================================

class DiagnosisHistoryItem(BaseModel):
    """Single diagnosis history item"""

    id: str
    user_id: Optional[str]
    created_at: str
    user_info: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None
    primary_syndrome: Optional[str] = None
    confidence: Optional[float] = None
    inference_time_ms: Optional[int] = None
    feedback: Optional[int] = None

    class Config:
        from_attributes = True


class DiagnosisListResponse(APIResponse):
    """Diagnosis list response with pagination"""

    total: int
    page: int
    page_size: int
    items: List[DiagnosisHistoryItem]


class StatisticsResponse(APIResponse):
    """Health statistics response"""

    total_diagnoses: int
    most_common_syndromes: List[Dict[str, Any]]
    most_common_features: Dict[str, List[Dict[str, Any]]]
    diagnosis_time_distribution: List[Dict[str, Any]]
    average_diagnosis_time_ms: Optional[float] = None


class TrendDataPoint(BaseModel):
    """Single trend data point"""

    date: str
    count: int
    syndromes: List[Dict[str, Any]]
    features: Dict[str, List[Dict[str, Any]]]


class TrendsResponse(APIResponse):
    """Health trends response"""

    period_days: int
    start_date: str
    end_date: str
    syndrome_trends: List[TrendDataPoint]
    feature_trends: Dict[str, List[TrendDataPoint]]


# ============================================================================
# GET /api/v2/history/diagnoses
# ============================================================================

@router.get("/diagnoses", response_model=DiagnosisListResponse, tags=["History"])
async def get_diagnosis_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    start_date: Optional[str] = Query(None, description="Filter start date (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="Filter end date (ISO 8601)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's diagnosis history with pagination and filtering.

    This endpoint returns a paginated list of diagnosis records for the
    authenticated user. Results are ordered by creation time (newest first).

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        start_date: Optional start date filter (ISO 8601 format)
        end_date: Optional end date filter (ISO 8601 format)
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        DiagnosisListResponse with paginated items

    Raises:
        HTTPException 400: If date format is invalid
        HTTPException 401: If not authenticated

    Example:
        GET /api/v2/history/diagnoses?page=1&page_size=20&start_date=2026-01-01
    """
    try:
        # Build query
        query = db.query(DiagnosisHistory).filter(
            DiagnosisHistory.user_id == current_user.id
        )

        # Apply date filters if provided
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(DiagnosisHistory.created_at >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use ISO 8601 format (e.g., 2026-01-01T00:00:00Z)"
                )

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(DiagnosisHistory.created_at <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use ISO 8601 format (e.g., 2026-01-01T00:00:00Z)"
                )

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        items = query.order_by(desc(DiagnosisHistory.created_at)).offset(offset).limit(page_size).all()

        # Format response items
        formatted_items = []
        for item in items:
            # Extract primary_syndrome and confidence from results JSONB
            primary_syndrome = None
            confidence = None
            if item.results:
                primary_syndrome = item.results.get("primary_syndrome")
                confidence = item.results.get("confidence")

            formatted_items.append(DiagnosisHistoryItem(
                id=str(item.id),
                user_id=str(item.user_id) if item.user_id else None,
                created_at=item.created_at.isoformat(),
                user_info=item.user_info,
                features=item.features,
                primary_syndrome=primary_syndrome,
                confidence=confidence,
                inference_time_ms=item.inference_time_ms,
                feedback=item.feedback
            ))

        return DiagnosisListResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            items=formatted_items
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting diagnosis history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve diagnosis history: {str(e)}"
        )


# ============================================================================
# GET /api/v2/history/statistics
# ============================================================================

@router.get("/statistics", response_model=StatisticsResponse, tags=["History"])
async def get_diagnosis_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get health statistics for the current user.

    Returns aggregated statistics including:
    - Total diagnosis count
    - Most common syndromes
    - Most common tongue features
    - Diagnosis time distribution
    - Average diagnosis time

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        StatisticsResponse with aggregated statistics

    Raises:
        HTTPException 401: If not authenticated

    Example:
        GET /api/v2/history/statistics
    """
    try:
        # Total diagnoses
        total = db.query(func.count(DiagnosisHistory.id)).filter(
            DiagnosisHistory.user_id == current_user.id
        ).scalar()

        if total == 0:
            return StatisticsResponse(
                success=True,
                total_diagnoses=0,
                most_common_syndromes=[],
                most_common_features={},
                diagnosis_time_distribution=[],
                average_diagnosis_time_ms=None
            )

        # Most common syndromes (extract from results JSONB)
        # PostgreSQL JSONB query: results->>'primary_syndrome'
        syndromes = db.query(
            DiagnosisHistory.results['primary_syndrome'].astext.label('syndrome'),
            func.count().label('count')
        ).filter(
            and_(
                DiagnosisHistory.user_id == current_user.id,
                DiagnosisHistory.results.isnot(None),
                DiagnosisHistory.results.has_key('primary_syndrome')
            )
        ).group_by(
            DiagnosisHistory.results['primary_syndrome'].astext
        ).order_by(
            desc('count')
        ).limit(10).all()

        most_common_syndromes = [
            {"syndrome": row.syndrome, "count": row.count}
            for row in syndromes
        ]

        # Most common features by dimension
        feature_dimensions = [
            "tongue_color", "coating_color", "tongue_shape",
            "coating_quality", "health_status"
        ]

        most_common_features = {}
        for dimension in feature_dimensions:
            # Query: features->dimension->>'prediction'
            features = db.query(
                DiagnosisHistory.features[dimension]['prediction'].astext.label('prediction'),
                func.count().label('count')
            ).filter(
                and_(
                    DiagnosisHistory.user_id == current_user.id,
                    DiagnosisHistory.features.isnot(None),
                    DiagnosisHistory.features.has_key(dimension)
                )
            ).group_by(
                DiagnosisHistory.features[dimension]['prediction'].astext
            ).order_by(
                desc('count')
            ).limit(5).all()

            most_common_features[dimension] = [
                {"prediction": row.prediction, "count": row.count}
                for row in features
            ]

        # Diagnosis time distribution (by day for last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)

        time_dist = db.query(
            func.date(DiagnosisHistory.created_at).label('date'),
            func.count().label('count')
        ).filter(
            and_(
                DiagnosisHistory.user_id == current_user.id,
                DiagnosisHistory.created_at >= thirty_days_ago
            )
        ).group_by(
            func.date(DiagnosisHistory.created_at)
        ).order_by(
            func.date(DiagnosisHistory.created_at)
        ).all()

        diagnosis_time_distribution = [
            {"date": str(row.date), "count": row.count}
            for row in time_dist
        ]

        # Average diagnosis time
        avg_time = db.query(
            func.avg(DiagnosisHistory.inference_time_ms)
        ).filter(
            and_(
                DiagnosisHistory.user_id == current_user.id,
                DiagnosisHistory.inference_time_ms.isnot(None)
            )
        ).scalar()

        return StatisticsResponse(
            success=True,
            total_diagnoses=total,
            most_common_syndromes=most_common_syndromes,
            most_common_features=most_common_features,
            diagnosis_time_distribution=diagnosis_time_distribution,
            average_diagnosis_time_ms=round(avg_time, 2) if avg_time else None
        )

    except Exception as e:
        logger.error(f"Error getting diagnosis statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


# ============================================================================
# GET /api/v2/history/trends
# ============================================================================

@router.get("/trends", response_model=TrendsResponse, tags=["History"])
async def get_diagnosis_trends(
    period_days: int = Query(30, ge=7, le=365, description="Analysis period in days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get health trends over time for the current user.

    Returns trend data showing how syndromes and features change over time.

    Args:
        period_days: Number of days to analyze (7-365)
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        TrendsResponse with time-series trend data

    Raises:
        HTTPException 401: If not authenticated

    Example:
        GET /api/v2/history/trends?period_days=30
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Get diagnoses in the period, grouped by day
        diagnoses = db.query(DiagnosisHistory).filter(
            and_(
                DiagnosisHistory.user_id == current_user.id,
                DiagnosisHistory.created_at >= start_date,
                DiagnosisHistory.created_at <= end_date
            )
        ).order_by(DiagnosisHistory.created_at).all()

        if not diagnoses:
            return TrendsResponse(
                success=True,
                period_days=period_days,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                syndrome_trends=[],
                feature_trends={}
            )

        # Group by date
        from collections import defaultdict

        syndrome_by_date = defaultdict(lambda: defaultdict(int))
        features_by_date = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        for d in diagnoses:
            date_str = d.created_at.date().isoformat()

            # Count syndromes
            if d.results and d.results.get("primary_syndrome"):
                syndrome = d.results["primary_syndrome"]
                syndrome_by_date[date_str][syndrome] += 1

            # Count features
            if d.features:
                for dimension in ["tongue_color", "coating_color", "tongue_shape", "coating_quality", "health_status"]:
                    if dimension in d.features and d.features[dimension].get("prediction"):
                        prediction = d.features[dimension]["prediction"]
                        features_by_date[dimension][date_str][prediction] += 1

        # Build syndrome trend data points
        syndrome_trends = []
        for date_str in sorted(syndrome_by_date.keys()):
            syndromes = [
                {"syndrome": s, "count": c}
                for s, c in sorted(syndrome_by_date[date_str].items(), key=lambda x: -x[1])
            ]
            syndrome_trends.append(TrendDataPoint(
                date=date_str,
                count=sum(syndrome_by_date[date_str].values()),
                syndromes=syndromes
            ))

        # Build feature trend data points
        feature_trends = {}
        for dimension in features_by_date.keys():
            trend_points = []
            for date_str in sorted(features_by_date[dimension].keys()):
                predictions = [
                    {"prediction": p, "count": c}
                    for p, c in sorted(features_by_date[dimension][date_str].items(), key=lambda x: -x[1])
                ]
                trend_points.append(TrendDataPoint(
                    date=date_str,
                    count=sum(features_by_date[dimension][date_str].values()),
                    syndromes=[]  # Not used for features
                ))
                # Replace syndromes with predictions
                trend_points[-1] = TrendDataPoint(
                    date=date_str,
                    count=sum(features_by_date[dimension][date_str].values()),
                    syndromes=predictions  # Reuse field for predictions
                )
            feature_trends[dimension] = trend_points

        return TrendsResponse(
            success=True,
            period_days=period_days,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            syndrome_trends=syndrome_trends,
            feature_trends=feature_trends
        )

    except Exception as e:
        logger.error(f"Error getting diagnosis trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trends: {str(e)}"
        )


__all__ = [
    "router",
]
