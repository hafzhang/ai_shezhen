#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnosis API Integration Tests
AI舌诊智能诊断系统 - Diagnosis API Tests
Phase 4: Testing & Documentation - US-173

Tests for diagnosis API endpoints:
- POST /api/v2/diagnosis - Create diagnosis (anonymous & authenticated)
- GET /api/v2/diagnosis/{id} - Get diagnosis detail
- POST /api/v2/diagnosis/{id}/feedback - Submit feedback
- GET /api/v2/history/diagnoses - Query diagnosis history
- GET /api/v2/history/statistics - Get health statistics
- GET /api/v2/history/trends - Get health trends

Test Coverage:
- Anonymous diagnosis flow
- Authenticated user diagnosis flow
- History query with pagination and filtering
- Feedback submission
- Statistics and trends
- Error handling for invalid inputs
"""

import base64
import datetime
import io
from typing import Generator
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID

import pytest
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from PIL import Image

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api_service.app.models.database import User, DiagnosisHistory, TongueImage
from api_service.app.api.deps import get_db, get_current_user, get_optional_user
from api_service.app.api.v2.models import DiagnosisRequest, UserInfoRequest


# ==============================================================================
# Helper Functions
# ==============================================================================

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


def create_valid_diagnosis_request(user_info: dict = None) -> dict:
    """
    Create a valid diagnosis request payload.

    Args:
        user_info: Optional user information dict

    Returns:
        Valid diagnosis request dictionary
    """
    if user_info is None:
        user_info = {"age": 35, "gender": "male", "chief_complaint": "最近感觉疲劳"}

    return {
        "image": create_test_image_base64(),
        "user_info": user_info,
        "enable_llm_diagnosis": True,
        "enable_rule_fallback": True
    }


# ==============================================================================
# Mock Model Functions
# ==============================================================================

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
                'teeth_marks': {'present': False, 'confidence': 0.0}
            },
            'health_status': {'prediction': '健康舌', 'confidence': 0.87, 'description': '健康状态'}
        }
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
        tcm_theory="中医理论",
        health_recommendations={
            "diet": ["保持均衡饮食"],
            "lifestyle": ["保持规律作息"],
            "emotional": ["保持心情愉悦"]
        },
        risk_alert=None
    )


# ==============================================================================
# Minimal FastAPI App for Testing
# ==============================================================================

@pytest.fixture(scope="function")
def test_app(db_session: Session) -> FastAPI:
    """
    Create a minimal FastAPI app with diagnosis routers for testing.

    Args:
        db_session: Database session fixture

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

    # Mock models
    with patch('api_service.app.api.v2.diagnosis.settings') as mock_settings:
        mock_settings.MODEL_VERSION = "v2.0"
        mock_settings.MEDIA_ROOT = "/tmp/media"
        mock_settings.MOCK_MODE = False

        # Import and include routers
        from api_service.app.api.v2 import diagnosis, history

        # Mock model functions
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


@pytest.fixture(scope="function")
def auth_headers(user: User) -> dict:
    """
    Create authentication headers for a user.

    Args:
        user: User fixture

    Returns:
        Dictionary with Authorization header
    """
    from api_service.app.core.security import create_access_token
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {access_token}"}


# ==============================================================================
# Anonymous Diagnosis Tests
# ==============================================================================

class TestAnonymousDiagnosis:
    """Test anonymous diagnosis flow."""

    @pytest.mark.integration
    def test_anonymous_diagnosis_success(self, client: TestClient):
        """
        Test successful anonymous diagnosis.

        Given: Valid diagnosis request without authentication
        When: POST /api/v2/diagnosis is called
        Then: Diagnosis is created with user_id=None
        """
        request_data = create_valid_diagnosis_request()

        response = client.post("/api/v2/diagnosis", json=request_data)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert "diagnosis_id" in data
        assert data["user_id"] is None  # Anonymous diagnosis
        assert "segmentation" in data
        assert "classification" in data
        assert "diagnosis" in data
        assert "inference_time_ms" in data

        # Assert classification structure
        classification = data["classification"]
        assert "tongue_color" in classification
        assert "coating_color" in classification
        assert "tongue_shape" in classification
        assert "coating_quality" in classification
        assert "special_features" in classification
        assert "health_status" in classification

        # Assert diagnosis structure
        diagnosis = data["diagnosis"]
        assert "primary_syndrome" in diagnosis
        assert "confidence" in diagnosis
        assert "syndrome_analysis" in diagnosis
        assert "health_recommendations" in diagnosis

    @pytest.mark.integration
    def test_anonymous_diagnosis_without_user_info(self, client: TestClient):
        """
        Test anonymous diagnosis without user info.

        Given: Valid diagnosis request without user_info
        When: POST /api/v2/diagnosis is called
        Then: Diagnosis is created successfully
        """
        request_data = {
            "image": create_test_image_base64(),
            "enable_llm_diagnosis": True
        }

        response = client.post("/api/v2/diagnosis", json=request_data)

        # Assert response status
        assert response.status_code == 200

        # Assert diagnosis created
        data = response.json()
        assert data["success"] is True
        assert "diagnosis_id" in data

    @pytest.mark.integration
    def test_anonymous_diagnosis_with_invalid_image(self, client: TestClient):
        """
        Test diagnosis with invalid image data fails.

        Given: Diagnosis request with invalid base64 image
        When: POST /api/v2/diagnosis is called
        Then: 400 error is returned
        """
        request_data = {
            "image": "not-a-valid-base64-image",
            "user_info": {"age": 35}
        }

        response = client.post("/api/v2/diagnosis", json=request_data)

        # Assert error response
        assert response.status_code == 400

    @pytest.mark.integration
    def test_anonymous_diagnosis_stores_tongue_image(self, client: TestClient, db_session: Session):
        """
        Test anonymous diagnosis stores tongue image.

        Given: Valid anonymous diagnosis request
        When: POST /api/v2/diagnosis is called
        Then: TongueImage and DiagnosisHistory records are created
        """
        request_data = create_valid_diagnosis_request()

        response = client.post("/api/v2/diagnosis", json=request_data)
        assert response.status_code == 200

        data = response.json()
        diagnosis_id = data["diagnosis_id"]

        # Check database records
        from uuid import UUID
        diagnosis_uuid = UUID(diagnosis_id)

        diagnosis = db_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.id == diagnosis_uuid
        ).first()

        assert diagnosis is not None
        assert diagnosis.user_id is None  # Anonymous
        assert diagnosis.tongue_image_id is not None
        assert diagnosis.features is not None
        assert diagnosis.results is not None


# ==============================================================================
# Authenticated Diagnosis Tests
# ==============================================================================

class TestAuthenticatedDiagnosis:
    """Test authenticated user diagnosis flow."""

    @pytest.mark.integration
    def test_authenticated_diagnosis_success(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test successful authenticated diagnosis.

        Given: Valid diagnosis request with authentication
        When: POST /api/v2/diagnosis is called
        Then: Diagnosis is created with user_id
        """
        request_data = create_valid_diagnosis_request()

        response = client.post("/api/v2/diagnosis", json=request_data, headers=auth_headers)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert "diagnosis_id" in data
        assert data["user_id"] == str(user.id)
        assert "segmentation" in data
        assert "classification" in data
        assert "diagnosis" in data

    @pytest.mark.integration
    def test_authenticated_diagnosis_stores_user_info(self, client: TestClient, user: User, auth_headers: dict, db_session: Session):
        """
        Test authenticated diagnosis stores user info.

        Given: Diagnosis request with user_info
        When: POST /api/v2/diagnosis is called
        Then: User info is stored in database
        """
        user_info = {
            "age": 42,
            "gender": "female",
            "chief_complaint": "经常失眠"
        }
        request_data = create_valid_diagnosis_request(user_info)

        response = client.post("/api/v2/diagnosis", json=request_data, headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        diagnosis_id = data["diagnosis_id"]

        # Check database
        from uuid import UUID
        diagnosis_uuid = UUID(diagnosis_id)

        diagnosis = db_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.id == diagnosis_uuid
        ).first()

        assert diagnosis is not None
        assert diagnosis.user_id == user.id
        assert diagnosis.user_info["age"] == 42
        assert diagnosis.user_info["gender"] == "female"
        assert diagnosis.user_info["chief_complaint"] == "经常失眠"

    @pytest.mark.integration
    def test_diagnosis_reuses_existing_image(self, client: TestClient, user: User, auth_headers: dict, db_session: Session, faker):
        """
        Test diagnosis reuses existing tongue image.

        Given: Same image uploaded twice
        When: POST /api/v2/diagnosis is called twice
        Then: Same tongue_image_id is used (deduplication by hash)
        """
        request_data = create_valid_diagnosis_request()

        # First diagnosis
        response1 = client.post("/api/v2/diagnosis", json=request_data, headers=auth_headers)
        assert response1.status_code == 200

        # Second diagnosis with same image
        response2 = client.post("/api/v2/diagnosis", json=request_data, headers=auth_headers)
        assert response2.status_code == 200

        # Check that same tongue image was used
        data1 = response1.json()
        data2 = response2.json()

        # Query diagnosis records
        from uuid import UUID
        diagnosis1 = db_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.id == UUID(data1["diagnosis_id"])
        ).first()
        diagnosis2 = db_session.query(DiagnosisHistory).filter(
            DiagnosisHistory.id == UUID(data2["diagnosis_id"])
        ).first()

        assert diagnosis1.tongue_image_id == diagnosis2.tongue_image_id


# ==============================================================================
# Diagnosis Detail Tests
# ==============================================================================

class TestDiagnosisDetail:
    """Test GET /api/v2/diagnosis/{id} endpoint."""

    @pytest.mark.integration
    def test_get_own_diagnosis_success(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test getting own diagnosis detail.

        Given: Authenticated user with existing diagnosis
        When: GET /api/v2/diagnosis/{id} is called
        Then: Complete diagnosis information is returned
        """
        response = client.get(f"/api/v2/diagnosis/{diagnosis.id}", headers=auth_headers)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert data["id"] == str(diagnosis.id)
        assert data["user_id"] == str(user.id)
        assert "tongue_image_id" in data
        assert "created_at" in data
        assert "user_info" in data
        assert "classification" in data
        assert "diagnosis" in data

    @pytest.mark.integration
    def test_get_diagnosis_invalid_uuid_format(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test getting diagnosis with invalid UUID format fails.

        Given: Invalid UUID string
        When: GET /api/v2/diagnosis/{id} is called
        Then: 400 error is returned
        """
        response = client.get("/api/v2/diagnosis/not-a-valid-uuid", headers=auth_headers)

        # Assert error response
        assert response.status_code == 400

    @pytest.mark.integration
    def test_get_diagnosis_not_found(self, client: TestClient, user: User, auth_headers: dict, faker):
        """
        Test getting non-existent diagnosis fails.

        Given: Valid UUID but no matching diagnosis
        When: GET /api/v2/diagnosis/{id} is called
        Then: 404 error is returned
        """
        fake_uuid = faker.uuid4()
        response = client.get(f"/api/v2/diagnosis/{fake_uuid}", headers=auth_headers)

        # Assert error response
        assert response.status_code == 404

    @pytest.mark.integration
    def test_get_other_user_diagnosis_forbidden(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, db_session: Session, faker):
        """
        Test getting another user's diagnosis is forbidden.

        Given: Diagnosis belonging to user A
        When: User B tries to access it
        Then: 403 error is returned
        """
        # Create another user
        from api_service.app.core.security import hash_password
        other_user = User(
            phone=faker.phone_number(),
            nickname=faker.name(),
            password_hash=hash_password("testpassword"),
        )
        db_session.add(other_user)
        db_session.commit()

        # Get auth headers for other user
        from api_service.app.core.security import create_access_token
        access_token = create_access_token(data={"sub": str(other_user.id)})
        other_headers = {"Authorization": f"Bearer {access_token}"}

        # Try to access original user's diagnosis
        response = client.get(f"/api/v2/diagnosis/{diagnosis.id}", headers=other_headers)

        # Assert forbidden
        assert response.status_code == 403

    @pytest.mark.integration
    def test_get_anonymous_diagnosis_without_auth(self, client: TestClient, anonymous_diagnosis: DiagnosisHistory):
        """
        Test getting anonymous diagnosis without authentication.

        Given: Anonymous diagnosis (user_id=None)
        When: GET /api/v2/diagnosis/{id} is called without auth
        Then: 401 error is returned (authentication required)
        """
        response = client.get(f"/api/v2/diagnosis/{anonymous_diagnosis.id}")

        # Assert unauthorized (endpoint requires authentication)
        assert response.status_code == 401


# ==============================================================================
# Feedback Tests
# ==============================================================================

class TestDiagnosisFeedback:
    """Test POST /api/v2/diagnosis/{id}/feedback endpoint."""

    @pytest.mark.integration
    def test_submit_positive_feedback_success(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test submitting positive feedback.

        Given: Valid diagnosis record
        When: POST /api/v2/diagnosis/{id}/feedback with feedback=1
        Then: Feedback is stored successfully
        """
        feedback_data = {"feedback": 1, "comment": "诊断准确"}

        response = client.post(
            f"/api/v2/diagnosis/{diagnosis.id}/feedback",
            json=feedback_data,
            headers=auth_headers
        )

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Feedback submitted successfully"
        assert data["feedback"] == 1

    @pytest.mark.integration
    def test_submit_negative_feedback_success(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test submitting negative feedback.

        Given: Valid diagnosis record
        When: POST /api/v2/diagnosis/{id}/feedback with feedback=-1
        Then: Feedback is stored successfully
        """
        feedback_data = {"feedback": -1, "comment": "诊断不准确"}

        response = client.post(
            f"/api/v2/diagnosis/{diagnosis.id}/feedback",
            json=feedback_data,
            headers=auth_headers
        )

        # Assert response status
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["feedback"] == -1

    @pytest.mark.integration
    def test_submit_feedback_without_comment(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test submitting feedback without comment.

        Given: Valid diagnosis record
        When: POST /api/v2/diagnosis/{id}/feedback with only feedback value
        Then: Feedback is stored successfully
        """
        feedback_data = {"feedback": 1}

        response = client.post(
            f"/api/v2/diagnosis/{diagnosis.id}/feedback",
            json=feedback_data,
            headers=auth_headers
        )

        # Assert response status
        assert response.status_code == 200

    @pytest.mark.integration
    def test_submit_feedback_invalid_value(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test submitting feedback with invalid value fails.

        Given: Valid diagnosis record
        When: POST /api/v2/diagnosis/{id}/feedback with invalid feedback value
        Then: 422 validation error is returned
        """
        feedback_data = {"feedback": 5}  # Invalid, must be -1, 0, or 1

        response = client.post(
            f"/api/v2/diagnosis/{diagnosis.id}/feedback",
            json=feedback_data,
            headers=auth_headers
        )

        # Assert validation error
        assert response.status_code == 422

    @pytest.mark.integration
    def test_submit_feedback_to_other_user_diagnosis_forbidden(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, db_session: Session, faker):
        """
        Test submitting feedback to other user's diagnosis is forbidden.

        Given: Diagnosis belonging to user A
        When: User B tries to submit feedback
        Then: 403 error is returned
        """
        # Create another user
        from api_service.app.core.security import hash_password
        other_user = User(
            phone=faker.phone_number(),
            nickname=faker.name(),
            password_hash=hash_password("testpassword"),
        )
        db_session.add(other_user)
        db_session.commit()

        # Get auth headers for other user
        from api_service.app.core.security import create_access_token
        access_token = create_access_token(data={"sub": str(other_user.id)})
        other_headers = {"Authorization": f"Bearer {access_token}"}

        # Try to submit feedback to original user's diagnosis
        feedback_data = {"feedback": 1}
        response = client.post(
            f"/api/v2/diagnosis/{diagnosis.id}/feedback",
            json=feedback_data,
            headers=other_headers
        )

        # Assert forbidden
        assert response.status_code == 403


# ==============================================================================
# History Query Tests
# ==============================================================================

class TestDiagnosisHistory:
    """Test GET /api/v2/history/diagnoses endpoint."""

    @pytest.mark.integration
    def test_get_history_default_pagination(self, client: TestClient, user: User, create_multiple_diagnoses, auth_headers: dict):
        """
        Test getting diagnosis history with default pagination.

        Given: User with multiple diagnoses
        When: GET /api/v2/history/diagnoses is called
        Then: First page of diagnoses is returned
        """
        response = client.get("/api/v2/history/diagnoses", headers=auth_headers)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "items" in data
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.integration
    def test_get_history_with_pagination(self, client: TestClient, user: User, create_multiple_diagnoses, auth_headers: dict):
        """
        Test getting diagnosis history with custom pagination.

        Given: User with multiple diagnoses
        When: GET /api/v2/history/diagnoses?page=1&page_size=2
        Then: Specified page size is returned
        """
        response = client.get("/api/v2/history/diagnoses?page=1&page_size=2", headers=auth_headers)

        # Assert response status
        assert response.status_code == 200

        # Assert pagination
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2

    @pytest.mark.integration
    def test_get_history_empty(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test getting diagnosis history for user with no diagnoses.

        Given: User with no diagnosis history
        When: GET /api/v2/history/diagnoses is called
        Then: Empty list is returned
        """
        response = client.get("/api/v2/history/diagnoses", headers=auth_headers)

        # Assert response
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.integration
    def test_get_history_with_date_filter(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test getting diagnosis history with date filtering.

        Given: User with diagnosis from specific date
        When: GET /api/v2/history/diagnoses with date filters
        Then: Filtered results are returned
        """
        # Get today's date
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

        response = client.get(f"/api/v2/history/diagnoses?start_date={today}", headers=auth_headers)

        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.integration
    def test_get_history_invalid_date_format(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test getting history with invalid date format fails.

        Given: Invalid date string
        When: GET /api/v2/history/diagnoses with invalid date
        Then: 400 error is returned
        """
        response = client.get("/api/v2/history/diagnoses?start_date=invalid-date", headers=auth_headers)

        # Assert error response
        assert response.status_code == 400

    @pytest.mark.integration
    def test_get_history_requires_authentication(self, client: TestClient):
        """
        Test getting history without authentication fails.

        Given: No authentication
        When: GET /api/v2/history/diagnoses is called
        Then: 401 error is returned
        """
        response = client.get("/api/v2/history/diagnoses")

        # Assert unauthorized
        assert response.status_code == 401

    @pytest.mark.integration
    def test_get_history_items_structure(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test history item structure.

        Given: User with diagnosis
        When: GET /api/v2/history/diagnoses is called
        Then: Each item has correct structure
        """
        response = client.get("/api/v2/history/diagnoses", headers=auth_headers)

        data = response.json()
        assert len(data["items"]) > 0

        item = data["items"][0]
        assert "id" in item
        assert "user_id" in item
        assert "created_at" in item
        assert "user_info" in item
        assert "features" in item
        assert "primary_syndrome" in item
        assert "confidence" in item
        assert "inference_time_ms" in item
        assert "feedback" in item


# ==============================================================================
# Statistics Tests
# ==============================================================================

class TestDiagnosisStatistics:
    """Test GET /api/v2/history/statistics endpoint."""

    @pytest.mark.integration
    def test_get_statistics_with_data(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test getting statistics for user with diagnoses.

        Given: User with diagnosis history
        When: GET /api/v2/history/statistics is called
        Then: Aggregated statistics are returned
        """
        response = client.get("/api/v2/history/statistics", headers=auth_headers)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert "total_diagnoses" in data
        assert "most_common_syndromes" in data
        assert "most_common_features" in data
        assert "diagnosis_time_distribution" in data
        assert data["total_diagnoses"] > 0

    @pytest.mark.integration
    def test_get_statistics_empty(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test getting statistics for user with no diagnoses.

        Given: User with no diagnosis history
        When: GET /api/v2/history/statistics is called
        Then: Zero statistics are returned
        """
        response = client.get("/api/v2/history/statistics", headers=auth_headers)

        # Assert response
        data = response.json()
        assert data["success"] is True
        assert data["total_diagnoses"] == 0
        assert data["most_common_syndromes"] == []
        assert data["most_common_features"] == {}
        assert data["diagnosis_time_distribution"] == []

    @pytest.mark.integration
    def test_get_statistics_requires_authentication(self, client: TestClient):
        """
        Test getting statistics without authentication fails.

        Given: No authentication
        When: GET /api/v2/history/statistics is called
        Then: 401 error is returned
        """
        response = client.get("/api/v2/history/statistics")

        # Assert unauthorized
        assert response.status_code == 401


# ==============================================================================
# Trends Tests
# ==============================================================================

class TestDiagnosisTrends:
    """Test GET /api/v2/history/trends endpoint."""

    @pytest.mark.integration
    def test_get_trends_default_period(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test getting trends with default period.

        Given: User with diagnosis history
        When: GET /api/v2/history/trends is called
        Then: Trend data for default period is returned
        """
        response = client.get("/api/v2/history/trends", headers=auth_headers)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert "period_days" in data
        assert "start_date" in data
        assert "end_date" in data
        assert "syndrome_trends" in data
        assert "feature_trends" in data
        assert data["period_days"] == 30  # Default

    @pytest.mark.integration
    def test_get_trends_custom_period(self, client: TestClient, user: User, diagnosis: DiagnosisHistory, auth_headers: dict):
        """
        Test getting trends with custom period.

        Given: User with diagnosis history
        When: GET /api/v2/history/trends?period_days=7
        Then: Trend data for specified period is returned
        """
        response = client.get("/api/v2/history/trends?period_days=7", headers=auth_headers)

        # Assert response
        data = response.json()
        assert data["success"] is True
        assert data["period_days"] == 7

    @pytest.mark.integration
    def test_get_trends_empty(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test getting trends for user with no diagnoses.

        Given: User with no diagnosis history
        When: GET /api/v2/history/trends is called
        Then: Empty trend data is returned
        """
        response = client.get("/api/v2/history/trends", headers=auth_headers)

        # Assert response
        data = response.json()
        assert data["success"] is True
        assert data["syndrome_trends"] == []
        assert data["feature_trends"] == {}

    @pytest.mark.integration
    def test_get_trends_invalid_period(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test getting trends with invalid period fails.

        Given: Invalid period_days value
        When: GET /api/v2/history/trends?period_days=500
        Then: 422 validation error is returned
        """
        response = client.get("/api/v2/history/trends?period_days=500", headers=auth_headers)

        # Assert validation error
        assert response.status_code == 422

    @pytest.mark.integration
    def test_get_trends_requires_authentication(self, client: TestClient):
        """
        Test getting trends without authentication fails.

        Given: No authentication
        When: GET /api/v2/history/trends is called
        Then: 401 error is returned
        """
        response = client.get("/api/v2/history/trends")

        # Assert unauthorized
        assert response.status_code == 401


# ==============================================================================
# Error Handling Tests
# ==============================================================================

class TestDiagnosisErrorHandling:
    """Test error handling for diagnosis endpoints."""

    @pytest.mark.integration
    def test_diagnosis_with_missing_image_field(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test diagnosis with missing image field fails.

        Given: Diagnosis request without image field
        When: POST /api/v2/diagnosis is called
        Then: 422 validation error is returned
        """
        request_data = {
            "user_info": {"age": 35}
        }

        response = client.post("/api/v2/diagnosis", json=request_data, headers=auth_headers)

        # Assert validation error
        assert response.status_code == 422

    @pytest.mark.integration
    def test_diagnosis_with_invalid_age(self, client: TestClient, user: User, auth_headers: dict):
        """
        Test diagnosis with invalid age value fails.

        Given: User info with invalid age
        When: POST /api/v2/diagnosis is called
        Then: 422 validation error is returned
        """
        request_data = {
            "image": create_test_image_base64(),
            "user_info": {"age": 200}  # Invalid age
        }

        response = client.post("/api/v2/diagnosis", json=request_data, headers=auth_headers)

        # Assert validation error
        assert response.status_code == 422
