"""
Pytest Configuration and Shared Fixtures
AI舌诊智能诊断系统 - Test Configuration
Phase 4: Testing & Documentation - US-171

This module provides shared fixtures for database model unit tests:
- Database engine and session fixtures
- Test data fixtures using Faker
- Model fixtures for CRUD testing
"""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock

import pytest
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api_service.app.models.database import (
    Base,
    User,
    RefreshToken,
    TongueImage,
    DiagnosisHistory,
    HealthRecord,
)


# ==============================================================================
# Test Database Configuration
# ==============================================================================

@pytest.fixture(scope="session")
def database_url() -> str:
    """
    Get test database URL.

    Uses SQLite in-memory database for fast, isolated tests.
    For PostgreSQL integration tests, set TEST_DATABASE_URL environment variable.

    Returns:
        Database connection URL
    """
    # Use TEST_DATABASE_URL if set (for PostgreSQL integration tests)
    if os.getenv("TEST_DATABASE_URL"):
        return os.getenv("TEST_DATABASE_URL")

    # Default to SQLite in-memory for fast unit tests
    return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine(database_url: str):
    """
    Create a test database engine.

    For SQLite in-memory, uses a single connection pool to ensure
    data persists across the test session.

    Args:
        database_url: Database connection URL

    Yields:
        SQLAlchemy Engine
    """
    # Create engine
    if database_url.startswith("sqlite"):
        # For SQLite, we need to handle type compatibility
        from sqlalchemy import event, func, text
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy.ext.compiler import compiles
        import uuid

        # Use poolclass=StaticPool for in-memory SQLite to persist across connections
        from sqlalchemy.pool import StaticPool
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )

        # Override UUID type for SQLite (store as strings)
        @compiles(UUID, "sqlite")
        def compile_uuid_sqlite(type_, compiler, **kw):
            # Store UUID as CHAR(36) in SQLite
            return "CHAR(36)"

        # Override ENUM type for SQLite (store as VARCHAR)
        @compiles(ENUM, "sqlite")
        def compile_enum_sqlite(type_, compiler, **kw):
            # For simplicity, just store as VARCHAR in tests
            return "VARCHAR(50)"

        # Override JSONB type for SQLite (store as TEXT/JSON)
        @compiles(JSONB, "sqlite")
        def compile_jsonb_sqlite(type_, compiler, **kw):
            # Store JSONB as TEXT in SQLite (SQLite has built-in JSON support)
            return "TEXT"

        # Override gen_random_uuid for SQLite (use random hex string)
        @compiles(func.gen_random_uuid, "sqlite")
        def compile_gen_random_uuid_sqlite(element, compiler, **kw):
            # Use lower(hex(randomblob(16))) for SQLite
            return "(lower(hex(randomblob(16))))"

        # Create a custom function to replace gen_random_uuid in DEFAULT clauses
        @event.listens_for(engine, "connect")
        def connect(dbapi_conn, connection_record):
            # Disable foreign keys in SQLite for tests
            # This avoids issues with deferred foreign key checking
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

            # Create our own gen_random_uuid function
            def gen_random_uuid():
                return str(uuid.uuid4())

            # Register the function with SQLite
            dbapi_conn.create_function("gen_random_uuid", 0, gen_random_uuid)

    else:
        engine = create_engine(database_url, future=True)

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Drop all tables after test session
    Base.metadata.drop_all(engine)

    # Dispose engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """
    Create a test database session.

    Each test gets a fresh session.
    Uses DELETE to clean up data after each test.

    Args:
        engine: SQLAlchemy Engine

    Yields:
        Database Session
    """
    # Create session with expire_on_commit=False to keep objects accessible after commit
    session = Session(bind=engine, future=True, expire_on_commit=False)

    yield session

    # Rollback any uncommitted changes
    try:
        session.rollback()
    except:
        pass

    # Close the session to clear the identity map
    session.close()

    # Create a new session for cleanup
    cleanup_session = Session(bind=engine, future=True)

    # Delete all data (in correct order due to foreign keys)
    from api_service.app.models.database import User, RefreshToken, DiagnosisHistory, HealthRecord, TongueImage
    cleanup_session.query(RefreshToken).delete(synchronize_session=False)
    cleanup_session.query(HealthRecord).delete(synchronize_session=False)
    cleanup_session.query(DiagnosisHistory).delete(synchronize_session=False)
    cleanup_session.query(TongueImage).delete(synchronize_session=False)
    cleanup_session.query(User).delete(synchronize_session=False)
    cleanup_session.commit()

    cleanup_session.close()


# ==============================================================================
# Faker Fixture
# ==============================================================================

@pytest.fixture(scope="function")
def faker() -> Faker:
    """
    Provide Faker instance for generating test data.

    Returns:
        Faker instance with Chinese locale
    """
    return Faker("zh_CN")


# ==============================================================================
# Model Fixtures - User
# ==============================================================================

@pytest.fixture(scope="function")
def user_data(faker: Faker) -> dict:
    """
    Generate valid user data for testing.

    Args:
        faker: Faker instance

    Returns:
        Dictionary with user fields
    """
    # Use actual bcrypt hash generation for valid password hashes
    # The password "testpassword" will be used in tests, so hash it here
    from api_service.app.core.security import hash_password
    password_hash = hash_password("testpassword")

    return {
        "phone": faker.phone_number(),
        "email": faker.email(),
        "nickname": faker.name(),
        "avatar_url": faker.url(),
        "password_hash": password_hash,
    }


@pytest.fixture(scope="function")
def user(db_session: Session, user_data: dict) -> User:
    """
    Create and persist a test user.

    Args:
        db_session: Database session
        user_data: User data dictionary

    Returns:
        User instance (committed to database)
    """
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()  # Commit to persist in database
    return user


@pytest.fixture(scope="function")
def wechat_user(db_session: Session, faker: Faker) -> User:
    """
    Create a WeChat mini-program user.

    Args:
        db_session: Database session
        faker: Faker instance

    Returns:
        User instance with WeChat OpenID
    """
    user = User(
        openid=faker.uuid4()[:50],
        openid_type="wechat",
        nickname=faker.name(),
    )
    db_session.add(user)
    db_session.commit()  # Commit to persist in database
    return user


# ==============================================================================
# Model Fixtures - RefreshToken
# ==============================================================================

@pytest.fixture(scope="function")
def refresh_token_data(faker: Faker) -> dict:
    """
    Generate valid refresh token data.

    Args:
        faker: Faker instance

    Returns:
        Dictionary with refresh token fields
    """
    from datetime import datetime, timedelta, timezone

    return {
        "token": faker.uuid4(),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    }


@pytest.fixture(scope="function")
def refresh_token(db_session: Session, user: User, refresh_token_data: dict) -> RefreshToken:
    """
    Create and persist a test refresh token.

    Args:
        db_session: Database session that commits
        user: User instance
        refresh_token_data: Refresh token data

    Returns:
        RefreshToken instance
    """
    token = RefreshToken(user_id=user.id, **refresh_token_data)
    db_session.add(token)
    db_session.flush()  # Flush for testing
    return token


# ==============================================================================
# Model Fixtures - TongueImage
# ==============================================================================

@pytest.fixture(scope="function")
def tongue_image_data(faker: Faker) -> dict:
    """
    Generate valid tongue image data.

    Args:
        faker: Faker instance

    Returns:
        Dictionary with tongue image fields
    """
    return {
        "file_hash": faker.sha256()[:64],
        "original_filename": faker.file_name(extension="jpg"),
        "storage_path": f"/tmp/tongue_images/{faker.uuid4()}.png",
        "width": 512,
        "height": 512,
        "file_size": faker.pyint(10000, 500000),
        "mime_type": "image/jpeg",
    }


@pytest.fixture(scope="function")
def tongue_image(db_session: Session, user: User, tongue_image_data: dict) -> TongueImage:
    """
    Create and persist a test tongue image.

    Args:
        db_session: Database session that commits
        user: User instance
        tongue_image_data: Tongue image data

    Returns:
        TongueImage instance
    """
    image = TongueImage(user_id=user.id, **tongue_image_data)
    db_session.add(image)
    db_session.flush()  # Flush for testing
    return image


@pytest.fixture(scope="function")
def anonymous_tongue_image(db_session: Session, tongue_image_data: dict) -> TongueImage:
    """
    Create an anonymous tongue image (no user).

    Args:
        db_session: Database session that commits
        tongue_image_data: Tongue image data

    Returns:
        TongueImage instance with user_id=None
    """
    image = TongueImage(user_id=None, **tongue_image_data)
    db_session.add(image)
    db_session.flush()  # Flush for testing
    return image


# ==============================================================================
# Model Fixtures - DiagnosisHistory
# ==============================================================================

@pytest.fixture(scope="function")
def diagnosis_data(faker: Faker) -> dict:
    """
    Generate valid diagnosis history data.

    Args:
        faker: Faker instance

    Returns:
        Dictionary with diagnosis fields
    """
    return {
        "user_info": {
            "age": faker.pyint(18, 80),
            "gender": faker.random_element(["male", "female"]),
            "chief_complaint": faker.sentence(),
        },
        "features": {
            "tongue_color": "red",
            "coating_color": "white",
            "tongue_shape": "normal",
            "moisture": "normal",
        },
        "results": {
            "syndrome": "肝胆湿热",
            "confidence": 0.85,
            "recommendations": ["清热利湿", "饮食清淡"],
        },
        "model_version": "v1.0",
        "inference_time_ms": faker.pyint(100, 2000),
    }


@pytest.fixture(scope="function")
def diagnosis(
    db_session: Session,
    user: User,
    tongue_image: TongueImage,
    diagnosis_data: dict,
) -> DiagnosisHistory:
    """
    Create and persist a test diagnosis.

    Args:
        db_session: Database session that commits
        user: User instance
        tongue_image: TongueImage instance
        diagnosis_data: Diagnosis data

    Returns:
        DiagnosisHistory instance
    """
    diagnosis = DiagnosisHistory(
        user_id=user.id,
        tongue_image_id=tongue_image.id,
        **diagnosis_data,
    )
    db_session.add(diagnosis)
    db_session.flush()  # Flush for testing
    return diagnosis


@pytest.fixture(scope="function")
def anonymous_diagnosis(
    db_session: Session,
    anonymous_tongue_image: TongueImage,
    diagnosis_data: dict,
) -> DiagnosisHistory:
    """
    Create an anonymous diagnosis (no user).

    Args:
        db_session: Database session that commits
        anonymous_tongue_image: TongueImage instance without user
        diagnosis_data: Diagnosis data

    Returns:
        DiagnosisHistory instance with user_id=None
    """
    diagnosis = DiagnosisHistory(
        user_id=None,
        tongue_image_id=anonymous_tongue_image.id,
        **diagnosis_data,
    )
    db_session.add(diagnosis)
    db_session.flush()  # Flush for testing
    return diagnosis


# ==============================================================================
# Model Fixtures - HealthRecord
# ==============================================================================

@pytest.fixture(scope="function")
def health_record_data(faker: Faker) -> dict:
    """
    Generate valid health record data.

    Args:
        faker: Faker instance

    Returns:
        Dictionary with health record fields
    """
    from datetime import date

    return {
        "record_type": "blood_pressure",
        "record_value": {
            "systolic": faker.pyint(90, 140),
            "diastolic": faker.pyint(60, 90),
            "unit": "mmHg",
        },
        "record_date": date.today(),
        "source": "user_input",
        "notes": faker.sentence(),
    }


@pytest.fixture(scope="function")
def health_record(
    db_session: Session,
    user: User,
    health_record_data: dict,
) -> HealthRecord:
    """
    Create and persist a test health record.

    Args:
        db_session: Database session that commits
        user: User instance
        health_record_data: Health record data

    Returns:
        HealthRecord instance
    """
    record = HealthRecord(user_id=user.id, **health_record_data)
    db_session.add(record)
    db_session.flush()  # Flush for testing
    return record


# ==============================================================================
# Helper Functions
# ==============================================================================

@pytest.fixture(scope="function")
def create_multiple_users(db_session: Session, faker: Faker, count: int = 5):
    """
    Create multiple test users.

    Args:
        db_session: Database session that commits
        faker: Faker instance
        count: Number of users to create

    Yields:
        List of User instances
    """
    from api_service.app.core.security import hash_password

    users = []
    for _ in range(count):
        user = User(
            phone=faker.phone_number(),
            nickname=faker.name(),
            password_hash=hash_password("testpassword"),
        )
        db_session.add(user)
        users.append(user)

    return users


@pytest.fixture(scope="function")
def create_multiple_diagnoses(
    db_session: Session,
    user: User,
    tongue_image: TongueImage,
    faker: Faker,
    count: int = 3,
):
    """
    Create multiple test diagnoses for a user.

    Args:
        db_session: Database session that commits
        user: User instance
        tongue_image: TongueImage instance
        faker: Faker instance
        count: Number of diagnoses to create

    Yields:
        List of DiagnosisHistory instances
    """
    diagnoses = []
    for _ in range(count):
        diagnosis = DiagnosisHistory(
            user_id=user.id,
            tongue_image_id=tongue_image.id,
            user_info={"age": faker.pyint(18, 80), "gender": "male"},
            features={"tongue_color": "red"},
            results={"syndrome": "脾胃虚弱", "confidence": faker.pyfloat(0.5, 0.95)},
            model_version="v1.0",
            inference_time_ms=faker.pyint(100, 2000),
        )
        db_session.add(diagnosis)
        diagnoses.append(diagnosis)

    return diagnoses
