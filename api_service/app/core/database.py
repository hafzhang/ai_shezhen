"""
Database Configuration and Session Management
AI舌诊智能诊断系统 - Database Configuration
Phase 2: Database & Auth - US-107

This module provides:
- Database URL configuration from environment variable
- SQLAlchemy engine with connection pool settings
- Session factory with scoped_session
- get_db() dependency generator for FastAPI
- init_db() function for database initialization
- check_db_health() for health monitoring
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker, scoped_session

# Database URL from environment variable
# Supports both DATABASE_URL and ALEMBIC_DATABASE_URL for compatibility
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv(
        "ALEMBIC_DATABASE_URL",
        "postgresql://shezhen:shezhen_password@localhost:5432/shezhen_db"
    )
)

# Engine configuration
engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None
ScopedSession = None


def get_database_url() -> str:
    """
    Get the database URL from environment variables.

    Returns:
        Database connection URL

    Environment Variables:
        DATABASE_URL: Primary database URL
        ALEMBIC_DATABASE_URL: Fallback for Alembic compatibility
    """
    return DATABASE_URL


def create_db_engine(database_url: Optional[str] = None) -> Engine:
    """
    Create SQLAlchemy engine with connection pool configuration.

    Args:
        database_url: Database connection URL (uses DATABASE_URL env var if not provided)

    Returns:
        Configured SQLAlchemy Engine

    Pool Configuration:
        - pool_size: Number of connections to maintain
        - max_overflow: Additional connections beyond pool_size
        - pool_timeout: Seconds to wait before giving up on getting a connection
        - pool_recycle: Recycle connections after this many seconds
        - pool_pre_ping: Test connections before using them
    """
    url = database_url or get_database_url()

    return create_engine(
        url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Number of connections to maintain
        max_overflow=10,  # Allow up to 10 additional connections
        pool_timeout=30,  # Wait 30 seconds for connection
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=False,  # Set to True for SQL query logging
        future=True,  # Use SQLAlchemy 2.0 style
    )


def init_db(database_url: Optional[str] = None) -> Engine:
    """
    Initialize database engine and session factory.

    Call this function during application startup.

    Args:
        database_url: Database connection URL (optional)

    Returns:
        Configured SQLAlchemy Engine

    Example:
        from api_service.app.core.database import init_db

        engine = init_db()
    """
    global engine, SessionLocal, ScopedSession

    url = database_url or get_database_url()

    # Create engine
    engine = create_db_engine(url)

    # Create session factory
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,  # Use SQLAlchemy 2.0 style
    )

    # Create scoped session for thread safety
    ScopedSession = scoped_session(SessionLocal)

    return engine


def get_engine() -> Engine:
    """
    Get the current database engine.

    Returns:
        SQLAlchemy Engine

    Raises:
        RuntimeError: If database has not been initialized
    """
    global engine

    if engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_db() first."
        )

    return engine


def get_session_factory() -> sessionmaker:
    """
    Get the session factory.

    Returns:
        Session factory

    Raises:
        RuntimeError: If database has not been initialized
    """
    global SessionLocal

    if SessionLocal is None:
        raise RuntimeError(
            "Database session factory not initialized. Call init_db() first."
        )

    return SessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Automatically handles commit/rollback and session cleanup.

    Yields:
        Database Session

    Example:
        with get_db_session() as db:
            user = db.query(User).first()
    """
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session.

    Use this in FastAPI endpoint functions:
        @app.get("/users/{user_id}")
        def read_user(user_id: str, db: Session = Depends(get_db)):
            return db.query(User).filter(User.id == user_id).first()

    Yields:
        Database Session

    Note:
        Session is automatically closed after the request.
    """
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
    finally:
        session.close()


async def check_db_health() -> dict:
    """
    Check database connection health.

    Returns a dictionary with health status information.

    Returns:
        Health check dict with keys:
        - healthy: bool - Whether database is accessible
        - message: str - Status message
        - database: str - Database name from URL
        - error: str - Error message if unhealthy

    Example:
        @app.get("/health")
        async def health():
            db_health = await check_db_health()
            return {"status": "ok" if db_health["healthy"] else "error", "database": db_health}
    """
    try:
        eng = get_engine()

        # Execute simple test query
        with eng.connect() as conn:
            conn.execute(sa.text("SELECT 1"))

        # Extract database name from URL
        url = get_database_url()
        database_name = url.rstrip("/").split("/")[-1] if "/" in url else "unknown"

        return {
            "healthy": True,
            "message": "Database connection successful",
            "database": database_name,
        }

    except RuntimeError as e:
        return {
            "healthy": False,
            "message": "Database not initialized",
            "database": "unknown",
            "error": str(e),
        }
    except SQLAlchemyError as e:
        return {
            "healthy": False,
            "message": "Database connection failed",
            "database": "unknown",
            "error": str(e),
        }


def close_db():
    """
    Close all database connections.

    Call this during application shutdown.
    """
    global engine, SessionLocal, ScopedSession

    if ScopedSession is not None:
        ScopedSession.remove()
        ScopedSession = None

    if SessionLocal is not None:
        SessionLocal.close_all()
        SessionLocal = None

    if engine is not None:
        engine.dispose()
        engine = None


# Import SQLAlchemy text for queries
import sqlalchemy as sa


__all__ = [
    "DATABASE_URL",
    "get_database_url",
    "create_db_engine",
    "init_db",
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "get_db",
    "check_db_health",
    "close_db",
]
