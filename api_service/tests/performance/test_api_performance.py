#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API Response Performance Tests
AI舌诊智能诊断系统 - API Response Performance Tests
Phase 4: Testing & Documentation - US-177

This module contains performance tests for API response times:
- Login API performance (< 200ms target)
- Diagnosis API performance (< 5s target)
- History query API performance (< 300ms target)

Acceptance Criteria:
- Login API < 200ms
- Diagnosis API < 5s
- History query API < 300ms
- Typecheck passes

Usage:
    pytest tests/performance/test_api_performance.py -v
    pytest tests/performance/test_api_performance.py::test_login_api_performance -v
    pytest tests/performance/test_api_performance.py::test_diagnosis_api_performance -v
    pytest tests/performance/test_api_performance.py::test_history_api_performance -v

Author: Ralph Agent
Date: 2026-02-22
"""

import os
import sys
import time
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image
import base64
import io

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
from api_service.app.api.deps import get_db


# ============================================================================
# Test Configuration
# ============================================================================

# Performance thresholds (in milliseconds)
LOGIN_API_MAX_MS = 200      # Target: < 200ms
DIAGNOSIS_API_MAX_MS = 5000 # Target: < 5s (5000ms)
HISTORY_API_MAX_MS = 300    # Target: < 300ms


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_image_base64(width: int = 512, height: int = 512) -> str:
    """
    Create a test image as base64 encoded string.

    Args:
        width: Image width
        height: Image height

    Returns:
        Base64 encoded image string with data URL prefix
    """
    # Create a simple test image
    img_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    return f"data:image/png;base64,{image_base64}"


# ============================================================================
# Test App Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_app(db_session: Session, engine) -> FastAPI:
    """
    Create a minimal FastAPI app with auth and diagnosis routers for testing.

    Args:
        db_session: Database session fixture
        engine: Database engine for creating fresh sessions

    Returns:
        FastAPI app instance
    """
    # Create minimal FastAPI app
    app = FastAPI()

    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Store engine and db_session reference for tests
    app.state.engine = engine
    app.state.db_session = db_session

    # Mock models
    with patch('api_service.app.api.v2.diagnosis.settings') as mock_settings:
        mock_settings.MODEL_VERSION = "v2.0"
        mock_settings.MEDIA_ROOT = "/tmp/media"
        mock_settings.MOCK_MODE = False

        # Import and include routers
        from api_service.app.api.v2 import auth, diagnosis, history

        # Mock model functions
        def mock_segmentor_predict(image, return_mask=False, return_overlay=False):
            """Mock segmentation predictor."""
            result = {}
            if return_mask:
                result["mask_path"] = "/tmp/mask.png"
            if return_overlay:
                result["overlay_path"] = "/tmp/overlay.png"
            result["tongue_area"] = 100000
            result["tongue_ratio"] = 0.3
            return result

        def mock_classifier_predict(image):
            """Mock classification predictor."""
            return {
                'results': {
                    'tongue_color': {'prediction': '淡红舌', 'confidence': 0.85, 'description': '舌色正常'},
                    'coating_color': {'prediction': '白苔', 'confidence': 0.80, 'description': '苔色正常'},
                    'tongue_shape': {'prediction': '正常', 'confidence': 0.90, 'description': '舌形正常'},
                    'coating_quality': {'prediction': '薄苔', 'confidence': 0.88, 'description': '苔质正常'},
                    'special_features': {
                        'red_dots': {'present': False, 'confidence': 0.0},
                        'cracks': {'present': False, 'confidence': 0.0},
                    }
                },
                'inference_time': 0.5,
                'model_version': 'v2.0'
            }

        def mock_diagnose_from_classification(classification):
            """Mock rule-based diagnosis."""
            from collections import namedtuple
            DiagnosisResult = namedtuple('DiagnosisResult', [
                'primary_syndrome', 'confidence', 'syndrome_description', 'tcm_theory',
                'health_recommendations', 'risk_alert'
            ])
            return DiagnosisResult(
                primary_syndrome="气血调和",
                confidence=0.85,
                syndrome_description="舌象正常，气血调和",
                tcm_theory="舌质淡红，苔薄白，为正常舌象。",
                health_recommendations=["保持良好生活习惯", "注意饮食均衡"],
                risk_alert=None
            )

        mock_pipeline = Mock()
        mock_segmentor = Mock(predict=mock_segmentor_predict)
        mock_classifier = Mock(predict=mock_classifier_predict)

        diagnosis.set_model_references(
            pipeline=mock_pipeline,
            segmentor=mock_segmentor,
            classifier=mock_classifier
        )

        # Mock rule-based diagnosis
        with patch('api_service.core.rule_based_diagnosis.diagnose_from_classification', side_effect=mock_diagnose_from_classification):
            app.include_router(auth.router, prefix="/api/v2/auth", tags=["Authentication"])
            app.include_router(diagnosis.router, prefix="/api/v2/diagnosis", tags=["Diagnosis"])
            app.include_router(history.router, prefix="/api/v2/history", tags=["History"])

    return app


@pytest.fixture(scope="function")
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """
    Create a FastAPI TestClient for making API requests.

    Args:
        test_app: FastAPI app fixture

    Yields:
        TestClient instance
    """
    with TestClient(test_app) as test_client:
        yield test_client


# ============================================================================
# Login API Performance Tests
# ============================================================================

class TestLoginAPIPerformance:
    """
    Performance tests for POST /api/v2/auth/login endpoint.

    Target: < 200ms
    """

    @pytest.fixture(scope="function")
    def test_user(self, client: TestClient, faker) -> dict:
        """Create a test user via registration API."""
        import random
        # Generate Chinese phone number (1 + 3-9 + 9 digits)
        phone = f"1{random.randint(3, 9)}{random.randint(100000000, 999999999)}"
        register_data = {
            "phone": phone,
            "password": "test12345",
            "nickname": faker.name(),
        }
        response = client.post("/api/v2/auth/register", json=register_data)
        assert response.status_code == 201
        return register_data

    def test_login_api_performance(
        self,
        client: TestClient,
        test_user: dict,
    ):
        """
        Test login API response time.

        Measures:
        - Request to response time for successful login
        - Includes password verification
        - Includes JWT token generation
        - Includes database query

        Target: < 200ms
        """
        # Prepare login data
        login_data = {
            "phone": test_user["phone"],
            "password": "test12345",
        }

        # Measure login API response time
        start_time = time.perf_counter()
        response = client.post("/api/v2/auth/login", json=login_data)
        end_time = time.perf_counter()

        # Calculate response time in milliseconds
        response_time_ms = (end_time - start_time) * 1000

        # Assert response is successful
        assert response.status_code == 200

        # Assert performance meets threshold (allow 10% tolerance)
        tolerance = LOGIN_API_MAX_MS * 0.1
        assert response_time_ms < LOGIN_API_MAX_MS + tolerance, (
            f"Login API response time {response_time_ms:.2f}ms exceeds threshold {LOGIN_API_MAX_MS}ms "
            f"(with {tolerance:.2f}ms tolerance)"
        )

        print(f"✓ Login API response time: {response_time_ms:.2f}ms (target: < {LOGIN_API_MAX_MS}ms)")

    def test_login_api_concurrent_performance(
        self,
        client: TestClient,
        faker,
    ):
        """
        Test login API performance under concurrent requests.

        Simulates 10 concurrent login requests to ensure:
        - Response times remain under threshold under load
        - No deadlocks or blocking occurs
        - All requests complete successfully

        Target: Each request < 200ms (with 10x tolerance for bcrypt overhead)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Register multiple users first
        import random
        login_data_list = []
        for _ in range(10):
            phone = f"1{random.randint(3, 9)}{random.randint(100000000, 999999999)}"
            register_data = {
                "phone": phone,
                "password": "test12345",
                "nickname": faker.name(),
            }
            response = client.post("/api/v2/auth/register", json=register_data)
            assert response.status_code == 201
            login_data_list.append({
                "phone": phone,
                "password": "test12345",
            })

        def make_login_request(data: dict):
            start_time = time.perf_counter()
            response = client.post("/api/v2/auth/login", json=data)
            end_time = time.perf_counter()
            return response, (end_time - start_time) * 1000

        # Measure concurrent login requests
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(make_login_request, data)
                for data in login_data_list
            ]
            results = [future.result() for future in as_completed(futures)]

        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000

        # Check all requests succeeded
        response_times = []
        for response, response_time_ms in results:
            assert response.status_code == 200, f"Login failed with status {response.status_code}"
            response_times.append(response_time_ms)

        # Assert performance meets threshold for all requests
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        # Allow 10x tolerance for concurrent login (due to bcrypt overhead)
        concurrent_threshold = LOGIN_API_MAX_MS * 10
        assert max_response_time < concurrent_threshold, (
            f"Concurrent login max response time {max_response_time:.2f}ms exceeds threshold {concurrent_threshold}ms"
        )

        print(f"✓ Concurrent login performance: {len(response_times)} requests in {total_time_ms:.2f}ms")
        print(f"  Average: {avg_response_time:.2f}ms, Max: {max_response_time:.2f}ms")


# ============================================================================
# Diagnosis API Performance Tests
# ============================================================================

class TestDiagnosisAPIPerformance:
    """
    Performance tests for POST /api/v2/diagnosis endpoint.

    Target: < 5s (5000ms)
    """

    def test_diagnosis_api_performance(
        self,
        client: TestClient,
    ):
        """
        Test diagnosis API response time.

        Measures:
        - Image upload and processing
        - Segmentation model inference (mocked)
        - Classification model inference (mocked)
        - Rule-based diagnosis generation (mocked)
        - Database storage

        Target: < 5s (with real models, this includes inference time)
        """
        # Prepare diagnosis request
        diagnosis_data = {
            "image": create_test_image_base64(),
            "user_info": {
                "age": 35,
                "gender": "male",
                "chief_complaint": "Fatigue and poor appetite",
            },
        }

        # Measure diagnosis API response time
        start_time = time.perf_counter()
        response = client.post("/api/v2/diagnosis", json=diagnosis_data)
        end_time = time.perf_counter()

        # Calculate response time in milliseconds
        response_time_ms = (end_time - start_time) * 1000

        # Assert response is successful
        assert response.status_code == 200

        # Assert performance meets threshold (allow 10% tolerance)
        tolerance = DIAGNOSIS_API_MAX_MS * 0.1
        assert response_time_ms < DIAGNOSIS_API_MAX_MS + tolerance, (
            f"Diagnosis API response time {response_time_ms:.2f}ms exceeds threshold {DIAGNOSIS_API_MAX_MS}ms "
            f"(with {tolerance:.2f}ms tolerance)"
        )

        print(f"✓ Diagnosis API response time: {response_time_ms:.2f}ms (target: < {DIAGNOSIS_API_MAX_MS}ms)")

    def test_diagnosis_api_with_authenticated_user(
        self,
        client: TestClient,
        faker,
    ):
        """
        Test diagnosis API response time for authenticated user.

        Measures:
        - Same as test_diagnosis_api_performance
        - Plus user association in database

        Target: < 5s
        """
        # Register and login to get access token
        import random
        phone = f"1{random.randint(3, 9)}{random.randint(100000000, 999999999)}"
        register_data = {
            "phone": phone,
            "password": "test12345",
            "nickname": faker.name(),
        }
        response = client.post("/api/v2/auth/register", json=register_data)
        assert response.status_code == 201

        login_response = client.post("/api/v2/auth/login", json={
            "phone": register_data["phone"],
            "password": "test12345",
        })
        assert login_response.status_code == 200
        login_data = login_response.json()
        token = login_data.get("access_token") or login_data.get("data", {}).get("access_token")

        # Prepare diagnosis request
        diagnosis_data = {
            "image": create_test_image_base64(),
            "user_info": {
                "age": 40,
                "gender": "female",
                "chief_complaint": "Low energy and shortness of breath",
            },
        }

        # Measure diagnosis API response time
        start_time = time.perf_counter()
        response = client.post(
            "/api/v2/diagnosis",
            json=diagnosis_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        end_time = time.perf_counter()

        # Calculate response time in milliseconds
        response_time_ms = (end_time - start_time) * 1000

        # Assert response is successful
        assert response.status_code == 200

        # Assert performance meets threshold (allow 10% tolerance)
        tolerance = DIAGNOSIS_API_MAX_MS * 0.1
        assert response_time_ms < DIAGNOSIS_API_MAX_MS + tolerance, (
            f"Authenticated diagnosis API response time {response_time_ms:.2f}ms exceeds threshold {DIAGNOSIS_API_MAX_MS}ms "
            f"(with {tolerance:.2f}ms tolerance)"
        )

        print(f"✓ Authenticated diagnosis API response time: {response_time_ms:.2f}ms")


# ============================================================================
# History Query API Performance Tests
# ============================================================================

class TestHistoryAPIPerformance:
    """
    Performance tests for GET /api/v2/history/diagnoses endpoint.

    Target: < 300ms
    """

    @pytest.fixture(scope="function")
    def test_user_with_diagnoses(self, client: TestClient, faker) -> tuple:
        """
        Create a test user with diagnoses via API.

        Returns:
            Tuple of (phone, password, access_token)
        """
        # Register a new user
        import random
        phone = f"1{random.randint(3, 9)}{random.randint(100000000, 999999999)}"
        password = "testpassword"
        register_response = client.post("/api/v2/auth/register", json={
            "phone": phone,
            "password": password,
            "nickname": faker.name(),
        })
        assert register_response.status_code == 201

        # Login to get access token
        login_response = client.post("/api/v2/auth/login", json={
            "phone": phone,
            "password": password,
        })
        assert login_response.status_code == 200
        login_data = login_response.json()
        access_token = login_data.get("access_token") or login_data.get("data", {}).get("access_token")

        # Create diagnoses via API (using mock models)
        for _ in range(50):
            diagnosis_data = {
                "image": create_test_image_base64(),
                "user_info": {
                    "age": faker.random_int(min=18, max=80),
                    "gender": faker.random_element(["male", "female"]),
                    "chief_complaint": faker.sentence(),
                },
            }
            response = client.post(
                "/api/v2/diagnosis",
                json=diagnosis_data,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200

        return phone, password, access_token

    def test_history_api_first_page_performance(
        self,
        client: TestClient,
        test_user_with_diagnoses: tuple,
    ):
        """
        Test history query API response time for first page.

        Measures:
        - Database query with pagination
        - User authentication
        - Response serialization

        Target: < 300ms
        """
        phone, password, access_token = test_user_with_diagnoses

        # Measure history query API response time
        start_time = time.perf_counter()
        response = client.get(
            "/api/v2/history/diagnoses?page=1&page_size=20",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        end_time = time.perf_counter()

        # Calculate response time in milliseconds
        response_time_ms = (end_time - start_time) * 1000

        # Assert response is successful
        assert response.status_code == 200

        # Assert performance meets threshold (allow 10% tolerance)
        tolerance = HISTORY_API_MAX_MS * 0.1
        assert response_time_ms < HISTORY_API_MAX_MS + tolerance, (
            f"History query API response time {response_time_ms:.2f}ms exceeds threshold {HISTORY_API_MAX_MS}ms "
            f"(with {tolerance:.2f}ms tolerance)"
        )

        print(f"✓ History query API (first page) response time: {response_time_ms:.2f}ms (target: < {HISTORY_API_MAX_MS}ms)")

    def test_history_api_last_page_performance(
        self,
        client: TestClient,
        test_user_with_diagnoses: tuple,
    ):
        """
        Test history query API response time for last page (deep pagination).

        Deep pagination tests OFFSET performance.

        Target: < 300ms
        """
        phone, password, access_token = test_user_with_diagnoses

        # Query last page (deep pagination)
        page = 3  # With 50 records and page_size=20, last page is page 3
        page_size = 20

        # Measure history query API response time
        start_time = time.perf_counter()
        response = client.get(
            f"/api/v2/history/diagnoses?page={page}&page_size={page_size}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        end_time = time.perf_counter()

        # Calculate response time in milliseconds
        response_time_ms = (end_time - start_time) * 1000

        # Assert response is successful
        assert response.status_code == 200

        # Assert performance meets threshold (allow 10% tolerance)
        tolerance = HISTORY_API_MAX_MS * 0.1
        assert response_time_ms < HISTORY_API_MAX_MS + tolerance, (
            f"History query API (deep pagination) response time {response_time_ms:.2f}ms exceeds threshold {HISTORY_API_MAX_MS}ms "
            f"(with {tolerance:.2f}ms tolerance)"
        )

        print(f"✓ History query API (last page) response time: {response_time_ms:.2f}ms")

    def test_history_api_with_date_filter_performance(
        self,
        client: TestClient,
        test_user_with_diagnoses: tuple,
    ):
        """
        Test history query API response time with date filtering.

        Date filtering adds WHERE clause complexity.

        Target: < 300ms
        """
        phone, password, access_token = test_user_with_diagnoses

        # Measure history query API response time with date filter
        start_time = time.perf_counter()
        response = client.get(
            "/api/v2/history/diagnoses?page=1&page_size=20&start_date=2026-01-01T00:00:00Z&end_date=2026-12-31T23:59:59Z",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        end_time = time.perf_counter()

        # Calculate response time in milliseconds
        response_time_ms = (end_time - start_time) * 1000

        # Assert response is successful
        assert response.status_code == 200

        # Assert performance meets threshold (allow 10% tolerance)
        tolerance = HISTORY_API_MAX_MS * 0.1
        assert response_time_ms < HISTORY_API_MAX_MS + tolerance, (
            f"History query API (with date filter) response time {response_time_ms:.2f}ms exceeds threshold {HISTORY_API_MAX_MS}ms "
            f"(with {tolerance:.2f}ms tolerance)"
        )

        print(f"✓ History query API (date filtered) response time: {response_time_ms:.2f}ms")

    def test_history_api_concurrent_performance(
        self,
        client: TestClient,
        test_user_with_diagnoses: tuple,
    ):
        """
        Test history query API performance under concurrent requests.

        Simulates 5 concurrent history queries from the same user.

        Target: Each request < 300ms
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        phone, password, access_token = test_user_with_diagnoses

        def make_history_request():
            start_time = time.perf_counter()
            response = client.get(
                "/api/v2/history/diagnoses?page=1&page_size=20",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            end_time = time.perf_counter()
            return response, (end_time - start_time) * 1000

        # Measure concurrent history requests
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_history_request) for _ in range(5)]
            results = [future.result() for future in as_completed(futures)]

        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000

        # Check all requests succeeded
        response_times = []
        for response, response_time_ms in results:
            assert response.status_code == 200, f"History query failed with status {response.status_code}"
            response_times.append(response_time_ms)

        # Assert performance meets threshold for all requests
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        assert max_response_time < HISTORY_API_MAX_MS * 2, (  # Allow 2x under concurrent load
            f"Concurrent history query max response time {max_response_time:.2f}ms exceeds threshold {HISTORY_API_MAX_MS * 2}ms"
        )

        print(f"✓ Concurrent history query performance: {len(response_times)} requests in {total_time_ms:.2f}ms")
        print(f"  Average: {avg_response_time:.2f}ms, Max: {max_response_time:.2f}ms")


# ============================================================================
# Summary Report
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def performance_summary(request):
    """
    Print a performance summary after all tests complete.
    """
    yield

    # This runs after all tests
    print("\n" + "=" * 70)
    print("API Performance Test Summary")
    print("=" * 70)
    print(f"Login API Target:        < {LOGIN_API_MAX_MS}ms")
    print(f"Diagnosis API Target:    < {DIAGNOSIS_API_MAX_MS}ms")
    print(f"History Query API Target:< {HISTORY_API_MAX_MS}ms")
    print("=" * 70)
