"""
SQLAlchemy ORM Models
AI舌诊智能诊断系统 - Database Models
Phase 2: Database & Auth - US-108

This module contains SQLAlchemy ORM models for all database tables:
- User: User accounts table
- RefreshToken: JWT refresh tokens storage
- TongueImage: Tongue image storage
- DiagnosisHistory: Diagnosis results storage
- HealthRecord: User health records storage

All models inherit from Base declarative base and support:
- UUID primary keys
- Automatic timestamps
- Soft delete support
- JSONB fields for flexible data storage
"""

from api_service.app.models.database import (
    Base,
    DiagnosisHistory,
    HealthRecord,
    RefreshToken,
    TongueImage,
    User,
)

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "TongueImage",
    "DiagnosisHistory",
    "HealthRecord",
]
