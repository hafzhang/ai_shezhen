"""
SQLAlchemy ORM Models - Database Tables
AI舌诊智能诊断系统 - Database Models
Phase 2: Database & Auth - US-108

This module defines SQLAlchemy ORM models for all database tables:
- User: User accounts (supports WeChat/Douyin mini-program and traditional login)
- RefreshToken: JWT refresh tokens storage
- TongueImage: Tongue image storage (supports anonymous uploads)
- DiagnosisHistory: Diagnosis results with JSONB fields
- HealthRecord: User health records with JSONB values

Usage:
    from api_service.app.models import User, Base

    # Create new user
    user = User(
        phone="13800138000",
        nickname="张三",
        password_hash="$2b$12$..."
    )

    # Query users
    from api_service.app.core.database import get_db_session
    with get_db_session() as db:
        user = db.query(User).filter(User.phone == "13800138000").first()
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Provides common functionality for all models:
    - Declarative base from SQLAlchemy 2.0
    - Common query methods can be added here
    """

    pass


# Create ENUM types for OpenIDType (must match migration)
OpenIDTypeEnum = ENUM(
    "wechat",
    "douyin",
    name="openidtype",
    create_type=True,
)


class OpenIDType(str, Enum):
    """
    OpenID provider type enum.

    Used for type hints in the User model.
    Matches the database enum type 'openidtype'.
    """

    WECHAT = "wechat"
    DOUYIN = "douyin"


# Create ENUM types for HealthRecordType (must match migration)
HealthRecordTypeEnum = ENUM(
    "blood_pressure",
    "heart_rate",
    "weight",
    "height",
    "temperature",
    "blood_sugar",
    "symptoms",
    "medication",
    "lab_results",
    "other",
    name="healthrecordtype",
    create_type=True,
)


class HealthRecordType(str, Enum):
    """
    Health record type enum.

    Used for type hints in the HealthRecord model.
    Matches the database enum type 'healthrecordtype'.
    """

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


class User(Base):
    """
    User accounts table.

    Supports multiple authentication methods:
    - WeChat mini-program (openid + openid_type)
    - Douyin mini-program (openid + openid_type)
    - Traditional phone login (phone + password_hash)
    - Email login (email + password_hash)

    Attributes:
        id: UUID primary key (auto-generated)
        openid: WeChat/Douyin openid (nullable)
        openid_type: OpenID provider type (wechat/douyin)
        phone: Phone number (unique, nullable)
        email: Email address (unique, nullable)
        nickname: User display name
        avatar_url: Profile avatar image URL
        password_hash: Bcrypt password hash (nullable for mini-program users)
        created_at: Account creation timestamp
        updated_at: Last update timestamp
        deleted_at: Soft delete timestamp (NULL if active)

    Relationships:
        refresh_tokens: List of refresh tokens for this user
        tongue_images: List of tongue images uploaded by this user
        diagnoses: List of diagnosis history for this user
        health_records: List of health records for this user
    """

    __tablename__ = "users"
    __table_args__ = (
        {"comment": "User accounts table - supports WeChat/Douyin mini-program and traditional login"}
    )

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # OpenID fields for mini-program authentication
    openid: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="WeChat/Douyin openid"
    )
    openid_type: Mapped[Optional[str]] = mapped_column(
        OpenIDTypeEnum, nullable=True, comment="OpenID provider type"
    )

    # Traditional login fields
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True, comment="Phone number"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, comment="Email address"
    )

    # Profile fields
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="User nickname"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Avatar image URL"
    )

    # Password field
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Bcrypt password hash"
    )

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    tongue_images: Mapped[list["TongueImage"]] = relationship(
        "TongueImage",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    diagnoses: Mapped[list["DiagnosisHistory"]] = relationship(
        "DiagnosisHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    health_records: Mapped[list["HealthRecord"]] = relationship(
        "HealthRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation of User for debugging."""
        auth_info = []
        if self.phone:
            auth_info.append(f"phone={self.phone}")
        if self.email:
            auth_info.append(f"email={self.email}")
        if self.openid:
            auth_info.append(f"openid_type={self.openid_type}")

        auth_str = ", ".join(auth_info) if auth_info else "no_auth"

        return (
            f"<User(id={self.id}, nickname={self.nickname}, "
            f"{auth_str}, deleted={self.deleted_at is not None})>"
        )

    def is_active(self) -> bool:
        """Check if user account is active (not soft deleted)."""
        return self.deleted_at is None

    def has_password_auth(self) -> bool:
        """Check if user has password authentication enabled."""
        return self.password_hash is not None

    def has_miniprogram_auth(self) -> bool:
        """Check if user has mini-program authentication enabled."""
        return self.openid is not None and self.openid_type is not None


class RefreshToken(Base):
    """
    JWT refresh tokens storage.

    Stores refresh tokens for JWT authentication flow.
    Tokens are automatically revoked when user is deleted (CASCADE).

    Attributes:
        id: UUID primary key (auto-generated)
        user_id: Foreign key to users table
        token: JWT refresh token hash (unique)
        expires_at: Token expiration timestamp
        revoked_at: Token revocation timestamp (NULL if active)
        created_at: Token creation timestamp

    Relationships:
        user: User who owns this token
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        {"comment": "JWT refresh tokens storage - supports token refresh flow"}
    )

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign key to users
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to users table",
    )

    # Token fields
    token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="JWT refresh token hash"
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Token expiration timestamp",
    )
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token revocation timestamp (NULL if active)",
    )

    # Timestamp
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation of RefreshToken for debugging."""
        return (
            f"<RefreshToken(id={self.id}, user_id={self.user_id}, "
            f"expires={self.expires_at}, revoked={self.revoked_at is not None})>"
        )

    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        return self.revoked_at is None and self.expires_at > now

    def revoke(self) -> None:
        """Mark token as revoked."""
        self.revoked_at = datetime.datetime.now(datetime.timezone.utc)


class TongueImage(Base):
    """
    Tongue image storage.

    Stores uploaded tongue images with metadata.
    Supports anonymous uploads (user_id is nullable).

    Attributes:
        id: UUID primary key (auto-generated)
        user_id: Foreign key to users table (NULL for anonymous)
        file_hash: SHA-256 hash of the image file (unique for deduplication)
        original_filename: Original uploaded filename
        storage_path: Path to stored image file
        width: Image width in pixels
        height: Image height in pixels
        file_size: File size in bytes
        mime_type: MIME type (e.g., image/jpeg)
        is_processed: Whether image has been processed by ML models
        segmentation_path: Path to segmentation mask file
        classification_path: Path to classification result file
        created_at: Upload timestamp
        updated_at: Last update timestamp
        deleted_at: Soft delete timestamp

    Relationships:
        user: User who uploaded this image (NULL for anonymous)
        diagnoses: Diagnosis records that use this image
    """

    __tablename__ = "tongue_images"
    __table_args__ = (
        {"comment": "Tongue image storage - supports anonymous and authenticated uploads"}
    )

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign key to users (nullable for anonymous uploads)
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key to users table (NULL for anonymous)",
    )

    # File metadata
    file_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="SHA-256 hash of the image file"
    )
    original_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Original uploaded filename"
    )
    storage_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Path to stored image file"
    )

    # Image dimensions
    width: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Image width in pixels"
    )
    height: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Image height in pixels"
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="File size in bytes"
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="MIME type (e.g., image/jpeg)"
    )

    # Processing flags
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
        comment="Whether image has been processed",
    )
    segmentation_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Path to segmentation mask file"
    )
    classification_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Path to classification result file"
    )

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="tongue_images",
        lazy="selectin",
    )

    diagnoses: Mapped[list["DiagnosisHistory"]] = relationship(
        "DiagnosisHistory",
        back_populates="tongue_image",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation of TongueImage for debugging."""
        return (
            f"<TongueImage(id={self.id}, user_id={self.user_id}, "
            f"file_hash={self.file_hash[:8]}..., is_processed={self.is_processed})>"
        )


class DiagnosisHistory(Base):
    """
    Diagnosis history storage.

    Stores diagnosis results with flexible JSONB fields.
    Supports anonymous diagnoses (user_id is nullable).

    Attributes:
        id: UUID primary key (auto-generated)
        user_id: Foreign key to users table (NULL for anonymous)
        tongue_image_id: Foreign key to tongue_images table
        user_info: User input data (age, gender, chief_complaint) as JSONB
        features: Extracted tongue features (6-dimension classification) as JSONB
        results: Diagnosis results (syndrome, confidence, recommendations) as JSONB
        model_version: Model version used for diagnosis
        inference_time_ms: Inference time in milliseconds
        feedback: User feedback (1=helpful, -1=not helpful, NULL=no feedback)
        feedback_comment: User feedback comment
        created_at: Diagnosis timestamp
        updated_at: Last update timestamp

    Relationships:
        user: User who owns this diagnosis (NULL for anonymous)
        tongue_image: Tongue image used for diagnosis
    """

    __tablename__ = "diagnosis_history"
    __table_args__ = (
        {"comment": "Diagnosis history - stores all diagnosis results with JSONB data"}
    )

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key to users table (NULL for anonymous)",
    )
    tongue_image_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tongue_images.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to tongue_images table",
    )

    # JSONB fields for flexible data storage
    user_info: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="User input data (age, gender, chief_complaint)"
    )
    features: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Extracted tongue features (6-dimension classification)",
    )
    results: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Diagnosis results (syndrome, confidence, recommendations)",
    )

    # Model metadata
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Model version used for diagnosis"
    )
    inference_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Inference time in milliseconds"
    )

    # Feedback tracking
    feedback: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="User feedback (1=helpful, -1=not helpful, NULL=no feedback)",
    )
    feedback_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="User feedback comment"
    )

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="diagnoses",
        lazy="selectin",
    )
    tongue_image: Mapped["TongueImage"] = relationship(
        "TongueImage",
        back_populates="diagnoses",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation of DiagnosisHistory for debugging."""
        syndrome = self.results.get("syndrome") if self.results else None
        return (
            f"<DiagnosisHistory(id={self.id}, user_id={self.user_id}, "
            f"syndrome={syndrome}, model={self.model_version})>"
        )


class HealthRecord(Base):
    """
    User health records storage.

    Stores medical and health data with flexible JSONB values.

    Attributes:
        id: UUID primary key (auto-generated)
        user_id: Foreign key to users table
        record_type: Type of health record (enum)
        record_value: Health record data as JSONB
        record_date: Date of the health record (if applicable)
        source: Record source (user_input, device_import, etc.)
        notes: Additional notes or comments
        created_at: Record creation timestamp
        updated_at: Last update timestamp
        deleted_at: Soft delete timestamp

    Relationships:
        user: User who owns this health record
    """

    __tablename__ = "health_records"
    __table_args__ = (
        {"comment": "User health records - stores medical and health data with flexible JSONB values"}
    )

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign key to users
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to users table",
    )

    # Record type enum
    record_type: Mapped[str] = mapped_column(
        HealthRecordTypeEnum, nullable=False, comment="Type of health record"
    )

    # JSONB field for flexible data storage
    record_value: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Health record data (flexible JSONB structure)",
    )

    # Additional metadata
    record_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date, nullable=True, comment="Date of the health record (if applicable)"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Record source (user_input, device_import, etc.)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Additional notes or comments"
    )

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"
    )

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="health_records",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """Return string representation of HealthRecord for debugging."""
        return (
            f"<HealthRecord(id={self.id}, user_id={self.user_id}, "
            f"type={self.record_type}, date={self.record_date})>"
        )
