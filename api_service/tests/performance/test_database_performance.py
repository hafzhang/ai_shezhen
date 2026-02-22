#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database Performance Tests
AI舌诊智能诊断系统 - Database Performance Tests
Phase 4: Testing & Documentation - US-176

This module contains performance tests for database queries:
- History query performance (< 100ms target)
- Statistics query performance (< 500ms target)
- Concurrent request handling (100 concurrent requests)

Acceptance Criteria:
- History query < 100ms
- Statistics query < 500ms
- 100 concurrent requests without blocking
- Typecheck passes

Usage:
    pytest tests/performance/test_database_performance.py -v
    pytest tests/performance/test_database_performance.py::test_history_query_performance -v
    pytest tests/performance/test_database_performance.py::test_concurrent_history_queries -v

Author: Ralph Agent
Date: 2026-02-22
"""

import os
import sys
import time
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from faker import Faker

# Import test fixtures from conftest
from api_service.tests.conftest import (
    database_url,
    engine as test_engine,
    db_session,
    faker as test_faker,
)

from api_service.app.models.database import (
    Base,
    User,
    DiagnosisHistory,
    TongueImage,
)
from api_service.app.core.security import hash_password


# ============================================================================
# Test Configuration
# ============================================================================

# Performance thresholds
HISTORY_QUERY_MAX_MS = 100  # Target: < 100ms
STATISTICS_QUERY_MAX_MS = 500  # Target: < 500ms
CONCURRENT_REQUESTS = 100  # Target: 100 concurrent requests

# Test data sizes
USER_COUNT = 10
DIAGNOSES_PER_USER = 50


# ============================================================================
# Performance Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def perf_session(engine):
    """
    Create a test database session for performance tests.

    Reuses the engine fixture from conftest which handles type compatibility.
    """
    from sqlalchemy.orm import Session
    session = Session(bind=engine, future=True, expire_on_commit=False)
    yield session
    session.close()


@pytest.fixture(scope="function")
def perf_test_data(perf_session, faker):
    """
    Create test data for performance tests.

    Creates:
    - Multiple users
    - Multiple diagnoses per user
    - Tongue images for each diagnosis
    """
    import random
    from sqlalchemy import text

    # Disable foreign key checks for faster bulk insert
    if perf_session.bind.dialect.name == "sqlite":
        perf_session.execute(text("PRAGMA foreign_keys=OFF"))

    users = []
    for _ in range(USER_COUNT):
        user = User(
            phone=faker.phone_number(),
            nickname=faker.name(),
            password_hash=hash_password("testpassword"),
        )
        perf_session.add(user)
        users.append(user)

    perf_session.flush()

    # Create diagnoses for each user
    syndromes = ["气血调和", "肝胆湿热", "脾胃虚弱", "肾气虚", "心肺气虚"]
    tongue_colors = ["red", "pale", "purple", "normal"]
    coating_colors = ["white", "yellow", "none", "thin"]

    total_diagnoses = 0
    for user in users:
        for _ in range(DIAGNOSES_PER_USER):
            # Create tongue image
            tongue_image = TongueImage(
                user_id=user.id,
                file_hash=faker.sha256()[:64],
                original_filename=faker.file_name(extension="jpg"),
                storage_path=f"/tmp/test/{faker.uuid4()}.png",
                width=512,
                height=512,
                file_size=random.randint(50000, 500000),
                mime_type="image/jpeg",
            )
            perf_session.add(tongue_image)
            perf_session.flush()

            # Create diagnosis with random date in last 30 days
            days_ago = random.randint(0, 30)
            created_at = datetime.now() - timedelta(days=days_ago)

            diagnosis = DiagnosisHistory(
                user_id=user.id,
                tongue_image_id=tongue_image.id,
                user_info={
                    "age": random.randint(18, 80),
                    "gender": random.choice(["male", "female"]),
                    "chief_complaint": faker.sentence(),
                },
                features={
                    "tongue_color": {
                        "prediction": random.choice(tongue_colors),
                        "confidence": round(random.uniform(0.6, 0.95), 2),
                    },
                    "coating_color": {
                        "prediction": random.choice(coating_colors),
                        "confidence": round(random.uniform(0.6, 0.95), 2),
                    },
                    "tongue_shape": {
                        "prediction": random.choice(["normal", "swollen", "thin"]),
                        "confidence": round(random.uniform(0.7, 0.95), 2),
                    },
                    "coating_quality": {
                        "prediction": random.choice(["thin", "thick", "none"]),
                        "confidence": round(random.uniform(0.7, 0.95), 2),
                    },
                    "health_status": {
                        "prediction": random.choice(["healthy", "sub_healthy", "unhealthy"]),
                        "confidence": round(random.uniform(0.6, 0.95), 2),
                    },
                },
                results={
                    "primary_syndrome": random.choice(syndromes),
                    "confidence": round(random.uniform(0.7, 0.95), 2),
                    "recommendations": [
                        random.choice(["清热利湿", "补气养血", "健脾益气", "疏肝理气"])
                    ],
                },
                model_version="v1.0",
                inference_time_ms=random.randint(100, 2000),
                created_at=created_at,
                updated_at=created_at,
            )
            perf_session.add(diagnosis)
            total_diagnoses += 1

    perf_session.commit()

    # Re-enable foreign keys
    if perf_session.bind.dialect.name == "sqlite":
        perf_session.execute(text("PRAGMA foreign_keys=ON"))

    return {
        "users": users,
        "total_diagnoses": total_diagnoses,
        "diagnoses_per_user": DIAGNOSES_PER_USER,
    }


# ============================================================================
# History Query Performance Tests
# ============================================================================

class TestHistoryQueryPerformance:
    """Test performance of history query endpoint."""

    def test_history_query_first_page_performance(self, perf_session, perf_test_data):
        """
        Test history query for first page performance.

        Target: < 100ms for paginated query.
        """
        user = perf_test_data["users"][0]

        from sqlalchemy import desc

        start_time = time.perf_counter()

        # Simulate the history query (first page, 20 items)
        query = perf_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.user_id == user.id
        )

        total = query.count()
        offset = 0
        page_size = 20
        items = query.order_by(desc(DiagnosisHistory.created_at)).offset(offset).limit(page_size).all()

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify results
        assert total == DIAGNOSES_PER_USER, f"Expected {DIAGNOSES_PER_USER} diagnoses, got {total}"
        assert len(items) == page_size, f"Expected {page_size} items, got {len(items)}"

        # Check performance
        assert elapsed_ms < HISTORY_QUERY_MAX_MS, (
            f"History query took {elapsed_ms:.2f}ms, "
            f"exceeds target of {HISTORY_QUERY_MAX_MS}ms"
        )

        print(f"✓ History query (first page): {elapsed_ms:.2f}ms (target: <{HISTORY_QUERY_MAX_MS}ms)")

    def test_history_query_last_page_performance(self, perf_session, perf_test_data):
        """
        Test history query for last page performance.

        Target: < 100ms even for deep pagination.
        """
        user = perf_test_data["users"][0]

        from sqlalchemy import desc

        start_time = time.perf_counter()

        # Simulate the history query (last page, need to skip many records)
        query = perf_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.user_id == user.id
        )

        total = query.count()
        page_size = 20
        last_page = (total // page_size) + 1
        offset = (last_page - 1) * page_size

        items = query.order_by(desc(DiagnosisHistory.created_at)).offset(offset).limit(page_size).all()

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify results
        assert len(items) <= page_size, f"Expected at most {page_size} items on last page"

        # Check performance (deep pagination should still be fast)
        assert elapsed_ms < HISTORY_QUERY_MAX_MS, (
            f"History query (last page) took {elapsed_ms:.2f}ms, "
            f"exceeds target of {HISTORY_QUERY_MAX_MS}ms"
        )

        print(f"✓ History query (last page): {elapsed_ms:.2f}ms (target: <{HISTORY_QUERY_MAX_MS}ms)")

    def test_history_query_with_date_filter_performance(self, perf_session, perf_test_data):
        """
        Test history query with date filter performance.

        Target: < 100ms for filtered queries.
        """
        user = perf_test_data["users"][0]

        from sqlalchemy import desc

        # Filter for last 7 days
        start_date = datetime.now() - timedelta(days=7)

        query_start = time.perf_counter()

        query = perf_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.user_id == user.id,
            DiagnosisHistory.created_at >= start_date
        )

        total = query.count()
        items = query.order_by(desc(DiagnosisHistory.created_at)).limit(20).all()

        query_end = time.perf_counter()
        elapsed_ms = (query_end - query_start) * 1000

        # Check performance
        assert elapsed_ms < HISTORY_QUERY_MAX_MS, (
            f"History query with date filter took {elapsed_ms:.2f}ms, "
            f"exceeds target of {HISTORY_QUERY_MAX_MS}ms"
        )

        print(f"✓ History query (date filtered): {elapsed_ms:.2f}ms (target: <{HISTORY_QUERY_MAX_MS}ms)")

    def test_history_query_with_jsonb_extraction_performance(self, perf_session, perf_test_data):
        """
        Test history query with JSONB field extraction performance.

        Simulates extracting primary_syndrome and confidence from results JSONB.
        """
        user = perf_test_data["users"][0]

        from sqlalchemy import desc

        start_time = time.perf_counter()

        # Query with JSONB extraction
        query = perf_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.user_id == user.id
        )

        items = query.order_by(desc(DiagnosisHistory.created_at)).limit(20).all()

        # Extract JSONB fields (as done in history.py)
        formatted_items = []
        for item in items:
            primary_syndrome = None
            confidence = None
            if item.results:
                primary_syndrome = item.results.get("primary_syndrome")
                confidence = item.results.get("confidence")

            formatted_items.append({
                "id": str(item.id),
                "primary_syndrome": primary_syndrome,
                "confidence": confidence,
            })

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify extraction worked
        assert len(formatted_items) == 20
        assert all(item["primary_syndrome"] for item in formatted_items)

        # Check performance
        assert elapsed_ms < HISTORY_QUERY_MAX_MS, (
            f"History query with JSONB extraction took {elapsed_ms:.2f}ms, "
            f"exceeds target of {HISTORY_QUERY_MAX_MS}ms"
        )

        print(f"✓ History query (JSONB extraction): {elapsed_ms:.2f}ms (target: <{HISTORY_QUERY_MAX_MS}ms)")


# ============================================================================
# Statistics Query Performance Tests
# ============================================================================

class TestStatisticsQueryPerformance:
    """Test performance of statistics query endpoint."""

    def test_statistics_query_performance(self, perf_session, perf_test_data):
        """
        Test statistics query performance.

        Target: < 500ms for aggregated statistics.
        """
        user = perf_test_data["users"][0]

        from sqlalchemy import func, and_, desc

        start_time = time.perf_counter()

        # Total diagnoses
        total = perf_session.query(func.count(DiagnosisHistory.id)).filter(
            DiagnosisHistory.user_id == user.id
        ).scalar()

        # Most common syndromes (JSONB aggregation)
        # Note: SQLite doesn't support JSONB has_key, so we filter differently
        syndromes = perf_session.query(
            DiagnosisHistory.results['primary_syndrome'].astext.label('syndrome'),
            func.count().label('count')
        ).filter(
            and_(
                DiagnosisHistory.user_id == user.id,
                DiagnosisHistory.results.isnot(None)
            )
        ).group_by(
            DiagnosisHistory.results['primary_syndrome'].astext
        ).order_by(
            desc('count')
        ).limit(10).all()

        # Average diagnosis time
        avg_time = perf_session.query(
            func.avg(DiagnosisHistory.inference_time_ms)
        ).filter(
            DiagnosisHistory.user_id == user.id
        ).scalar()

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify results
        assert total == DIAGNOSES_PER_USER
        assert len(syndromes) > 0
        assert avg_time is not None

        # Check performance
        assert elapsed_ms < STATISTICS_QUERY_MAX_MS, (
            f"Statistics query took {elapsed_ms:.2f}ms, "
            f"exceeds target of {STATISTICS_QUERY_MAX_MS}ms"
        )

        print(f"✓ Statistics query: {elapsed_ms:.2f}ms (target: <{STATISTICS_QUERY_MAX_MS}ms)")

    def test_statistics_query_with_date_distribution_performance(self, perf_session, perf_test_data):
        """
        Test statistics query with date distribution performance.

        Tests the query for diagnosis time distribution by day.
        """
        user = perf_test_data["users"][0]

        from sqlalchemy import func, and_, desc

        thirty_days_ago = datetime.now() - timedelta(days=30)

        start_time = time.perf_counter()

        # Diagnosis time distribution (by day for last 30 days)
        time_dist = perf_session.query(
            func.date(DiagnosisHistory.created_at).label('date'),
            func.count().label('count')
        ).filter(
            and_(
                DiagnosisHistory.user_id == user.id,
                DiagnosisHistory.created_at >= thirty_days_ago
            )
        ).group_by(
            func.date(DiagnosisHistory.created_at)
        ).order_by(
            func.date(DiagnosisHistory.created_at)
        ).all()

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify results
        assert len(time_dist) > 0

        # Check performance
        assert elapsed_ms < STATISTICS_QUERY_MAX_MS, (
            f"Statistics query (date distribution) took {elapsed_ms:.2f}ms, "
            f"exceeds target of {STATISTICS_QUERY_MAX_MS}ms"
        )

        print(f"✓ Statistics query (date distribution): {elapsed_ms:.2f}ms (target: <{STATISTICS_QUERY_MAX_MS}ms)")


# ============================================================================
# Concurrent Request Tests
# ============================================================================

class TestConcurrentRequests:
    """Test concurrent request handling without blocking."""

    def test_concurrent_history_queries(self, engine, perf_test_data):
        """
        Test 100 concurrent history queries.

        Target: All requests complete without blocking/timeout.

        Note: SQLite has threading limitations, so we use a lock for safety.
        For PostgreSQL, no lock is needed and true concurrency is tested.
        """
        import threading
        from sqlalchemy.orm import Session
        from sqlalchemy import desc

        user = perf_test_data["users"][0]

        # SQLite requires serialized access due to threading limitations
        db_lock = threading.Lock() if engine.dialect.name == "sqlite" else None

        def run_query(user_id, index):
            """Run a single history query."""
            # Create a new session for each thread
            session = Session(bind=engine, future=True)

            try:
                if db_lock:
                    with db_lock:
                        query = session.query(DiagnosisHistory).filter(
                            DiagnosisHistory.user_id == user_id
                        )
                        items = query.order_by(desc(DiagnosisHistory.created_at)).limit(20).all()
                else:
                    query = session.query(DiagnosisHistory).filter(
                        DiagnosisHistory.user_id == user_id
                    )
                    items = query.order_by(desc(DiagnosisHistory.created_at)).limit(20).all()

                # Simulate JSONB extraction
                formatted = []
                for item in items:
                    formatted.append({
                        "id": str(item.id),
                        "primary_syndrome": item.results.get("primary_syndrome") if item.results else None,
                    })

                return len(formatted)
            finally:
                session.close()

        start_time = time.perf_counter()

        # Run concurrent queries
        # Use fewer workers for SQLite to avoid threading issues
        workers = 10 if engine.dialect.name == "sqlite" else CONCURRENT_REQUESTS
        test_requests = 20 if engine.dialect.name == "sqlite" else CONCURRENT_REQUESTS

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(run_query, user.id, i)
                for i in range(test_requests)
            ]

            results = [
                future.result(timeout=30)
                for future in as_completed(futures)
            ]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify all requests completed
        assert len(results) == test_requests, (
            f"Expected {test_requests} results, got {len(results)}"
        )

        # Verify all queries returned data
        assert all(result == 20 for result in results), (
            f"Not all queries returned expected data"
        )

        # Calculate average query time
        avg_query_ms = elapsed_ms / test_requests

        if engine.dialect.name == "sqlite":
            print(f"✓ {test_requests} concurrent queries (SQLite with lock): {elapsed_ms:.2f}ms total")
        else:
            print(f"✓ {test_requests} concurrent queries: {elapsed_ms:.2f}ms total")
        print(f"  Average per query: {avg_query_ms:.2f}ms")

        # For SQLite, just verify completion without blocking check
        if engine.dialect.name != "sqlite":
            # Verify no blocking (concurrent should be faster than sequential)
            assert elapsed_ms < HISTORY_QUERY_MAX_MS * test_requests, (
                f"Concurrent queries took {elapsed_ms:.2f}ms, "
                f"which suggests blocking (expected < {HISTORY_QUERY_MAX_MS * test_requests}ms)"
            )

    def test_concurrent_statistics_queries(self, engine, perf_test_data):
        """
        Test 50 concurrent statistics queries.

        Target: All requests complete without blocking/timeout.

        Note: SQLite has threading limitations, so we use a lock for safety.
        For PostgreSQL, no lock is needed and true concurrency is tested.
        """
        import threading
        from sqlalchemy.orm import Session
        from sqlalchemy import func

        user = perf_test_data["users"][0]

        # SQLite requires serialized access due to threading limitations
        db_lock = threading.Lock() if engine.dialect.name == "sqlite" else None

        def run_statistics_query(user_id, index):
            """Run a single statistics query."""
            session = Session(bind=engine, future=True)

            try:
                if db_lock:
                    with db_lock:
                        total = session.query(func.count(DiagnosisHistory.id)).filter(
                            DiagnosisHistory.user_id == user_id
                        ).scalar()
                else:
                    total = session.query(func.count(DiagnosisHistory.id)).filter(
                        DiagnosisHistory.user_id == user_id
                    ).scalar()

                return total
            finally:
                session.close()

        start_time = time.perf_counter()

        # Use fewer workers for SQLite to avoid threading issues
        workers = 5 if engine.dialect.name == "sqlite" else 50
        test_requests = 10 if engine.dialect.name == "sqlite" else 50

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(run_statistics_query, user.id, i)
                for i in range(test_requests)
            ]

            results = [
                future.result(timeout=30)
                for future in as_completed(futures)
            ]

        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000

        # Verify all requests completed
        assert len(results) == test_requests

        # Verify all queries returned data
        assert all(result == DIAGNOSES_PER_USER for result in results)

        avg_query_ms = elapsed_ms / test_requests

        if engine.dialect.name == "sqlite":
            print(f"✓ {test_requests} concurrent statistics queries (SQLite with lock): {elapsed_ms:.2f}ms total")
        else:
            print(f"✓ {test_requests} concurrent statistics queries: {elapsed_ms:.2f}ms total")
        print(f"  Average per query: {avg_query_ms:.2f}ms")


# ============================================================================
# Performance Summary Report
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def performance_report():
    """Generate performance summary report."""
    yield

    # Report is generated during test execution via print statements
    print("\n" + "=" * 70)
    print("DATABASE PERFORMANCE TEST SUMMARY")
    print("=" * 70)
    print(f"History Query Target: < {HISTORY_QUERY_MAX_MS}ms")
    print(f"Statistics Query Target: < {STATISTICS_QUERY_MAX_MS}ms")
    print(f"Concurrent Requests: {CONCURRENT_REQUESTS}")
    print("=" * 70)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run database performance tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--target", choices=["all", "history", "statistics", "concurrent"],
                       default="all", help="Test target")
    args = parser.parse_args()

    pytest_args = ["-v", __file__]

    if args.target == "history":
        pytest_args.extend(["-k", "HistoryQuery"])
    elif args.target == "statistics":
        pytest_args.extend(["-k", "StatisticsQuery"])
    elif args.target == "concurrent":
        pytest_args.extend(["-k", "Concurrent"])

    sys.exit(pytest.main(pytest_args))
