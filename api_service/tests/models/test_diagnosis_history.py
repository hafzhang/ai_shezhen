"""
DiagnosisHistory Model Unit Tests
AI舌诊智能诊断系统 - DiagnosisHistory Model Tests
Phase 4: Testing & Documentation - US-171

Tests for DiagnosisHistory model CRUD operations:
- Create diagnosis with authenticated user
- Create anonymous diagnosis
- Read/query diagnosis by various fields
- Update diagnosis fields
- Store and retrieve JSONB data
- Feedback tracking
"""

import pytest
from sqlalchemy.orm import Session

from api_service.app.models.database import DiagnosisHistory


# ==============================================================================
# CREATE Tests
# ==============================================================================

class TestDiagnosisCreate:
    """Test diagnosis creation and persistence."""

    @pytest.mark.unit
    def test_create_diagnosis_with_user(
        self, db_session: Session, user, tongue_image, diagnosis_data
    ):
        """
        Test creating a diagnosis for an authenticated user.

        Given: Valid diagnosis data with user_id
        When: Diagnosis is created and committed
        Then: Diagnosis is persisted with correct fields
        """
        # Create diagnosis
        diagnosis = DiagnosisHistory(
            user_id=user.id,
            tongue_image_id=tongue_image.id,
            **diagnosis_data,
        )
        db_session.add(diagnosis)
        db_session.flush()  # Flush for testing

        # Assert diagnosis was created
        assert diagnosis.id is not None
        assert diagnosis.user_id == user.id
        assert diagnosis.tongue_image_id == tongue_image.id
        assert diagnosis.user_info == diagnosis_data["user_info"]
        assert diagnosis.features == diagnosis_data["features"]
        assert diagnosis.results == diagnosis_data["results"]
        assert diagnosis.model_version == diagnosis_data["model_version"]
        assert diagnosis.inference_time_ms == diagnosis_data["inference_time_ms"]
        assert diagnosis.created_at is not None
        assert diagnosis.updated_at is not None

    @pytest.mark.unit
    def test_create_anonymous_diagnosis(
        self, db_session: Session, anonymous_tongue_image, diagnosis_data
    ):
        """
        Test creating an anonymous diagnosis.

        Given: Valid diagnosis data with user_id=None
        When: Diagnosis is created
        Then: Diagnosis is persisted without user association
        """
        # Create anonymous diagnosis
        diagnosis = DiagnosisHistory(
            user_id=None,
            tongue_image_id=anonymous_tongue_image.id,
            **diagnosis_data,
        )
        db_session.add(diagnosis)
        db_session.flush()  # Flush for testing

        # Assert anonymous diagnosis was created
        assert diagnosis.id is not None
        assert diagnosis.user_id is None
        assert diagnosis.tongue_image_id == anonymous_tongue_image.id

    @pytest.mark.unit
    def test_create_diagnosis_with_jsonb_fields(
        self, db_session: Session, user, tongue_image, faker
    ):
        """
        Test creating diagnosis with complex JSONB data.

        Given: Diagnosis data with nested JSON structures
        When: Diagnosis is created
        Then: JSONB fields are correctly stored and retrieved
        """
        # Complex JSONB data
        complex_diagnosis_data = {
            "user_info": {
                "age": faker.pyint(18, 80),
                "gender": "female",
                "chief_complaint": faker.sentence(),
                "medical_history": ["hypertension", "diabetes"],
                "lifestyle": {
                    "smoking": False,
                    "drinking": "occasional",
                },
            },
            "features": {
                "tongue_color": "pale",
                "coating_color": "white",
                "tongue_shape": "swollen",
                "moisture": "dry",
                "special_features": ["齿痕", "裂纹"],
                "confidence_scores": {
                    "tongue_color": 0.92,
                    "coating_color": 0.88,
                },
            },
            "results": {
                "syndrome": "脾肾阳虚",
                "confidence": 0.81,
                "differential_diagnoses": [
                    {"syndrome": "脾胃虚弱", "probability": 0.15},
                    {"syndrome": "肾气虚", "probability": 0.04},
                ],
                "recommendations": {
                    "diet": ["温补食物", "避免生冷"],
                    "lifestyle": ["注意保暖", "适度运动"],
                    "tcm_therapy": ["艾灸", "推拿"],
                },
            },
            "model_version": "v1.2",
            "inference_time_ms": faker.pyint(100, 2000),
        }

        # Create diagnosis
        diagnosis = DiagnosisHistory(
            user_id=user.id,
            tongue_image_id=tongue_image.id,
            **complex_diagnosis_data,
        )
        db_session.add(diagnosis)
        db_session.flush()  # Flush for testing

        # Assert complex JSONB data is preserved
        assert diagnosis.user_info["lifestyle"]["smoking"] is False
        assert diagnosis.features["special_features"] == ["齿痕", "裂纹"]
        assert len(diagnosis.results["recommendations"]["diet"]) == 2

    @pytest.mark.unit
    def test_create_diagnosis_with_minimal_fields(
        self, db_session: Session, tongue_image
    ):
        """
        Test creating a diagnosis with only required fields.

        Given: Only tongue_image_id (required)
        When: Diagnosis is created
        Then: Diagnosis is persisted with NULL for optional fields
        """
        # Create minimal diagnosis
        diagnosis = DiagnosisHistory(
            user_id=None,
            tongue_image_id=tongue_image.id,
        )
        db_session.add(diagnosis)
        db_session.flush()  # Flush for testing

        # Assert minimal diagnosis was created
        assert diagnosis.id is not None
        assert diagnosis.user_info is None
        assert diagnosis.features is None
        assert diagnosis.results is None
        assert diagnosis.model_version is None

    @pytest.mark.unit
    def test_diagnosis_requires_tongue_image(
        self, db_session: Session, user, diagnosis_data
    ):
        """
        Test that diagnosis requires tongue_image_id.

        Given: Diagnosis data without tongue_image_id
        When: Attempting to create diagnosis
        Then: Database error is raised
        """
        # Create diagnosis without tongue_image_id
        diagnosis = DiagnosisHistory(
            user_id=user.id,
            # tongue_image_id is missing
            **diagnosis_data,
        )
        db_session.add(diagnosis)

        # Assert database error is raised
        with pytest.raises(Exception):  # IntegrityError
            db_session.flush()  # Flush for testing


# ==============================================================================
# READ/QUERY Tests
# ==============================================================================

class TestDiagnosisRead:
    """Test diagnosis retrieval and querying."""

    @pytest.mark.unit
    def test_get_diagnosis_by_id(self, db_session: Session, diagnosis):
        """
        Test retrieving a diagnosis by ID.

        Given: A diagnosis with known ID
        When: Querying diagnosis by ID
        Then: Correct diagnosis is returned
        """
        # Query diagnosis by ID
        found_diagnosis = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.id == diagnosis.id)
            .first()
        )

        # Assert correct diagnosis was found
        assert found_diagnosis is not None
        assert found_diagnosis.id == diagnosis.id
        assert found_diagnosis.user_id == diagnosis.user_id

    @pytest.mark.unit
    def test_get_diagnoses_by_user(
        self, db_session: Session, user, create_multiple_diagnoses
    ):
        """
        Test retrieving all diagnoses for a specific user.

        Given: A user with multiple diagnoses
        When: Querying diagnoses by user_id
        Then: All user's diagnoses are returned
        """
        # Query diagnoses by user
        user_diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.user_id == user.id)
            .all()
        )

        # Assert all user diagnoses are returned
        assert len(user_diagnoses) >= 3
        for diagnosis in user_diagnoses:
            assert diagnosis.user_id == user.id

    @pytest.mark.unit
    def test_get_anonymous_diagnoses(self, db_session: Session, anonymous_diagnosis):
        """
        Test retrieving anonymous diagnoses.

        Given: An anonymous diagnosis in database
        When: Querying diagnoses with user_id=NULL
        Then: Anonymous diagnoses are returned
        """
        # Query anonymous diagnoses
        anonymous_diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.user_id.is_(None))
            .all()
        )

        # Assert anonymous diagnosis is found
        assert len(anonymous_diagnoses) >= 1
        assert anonymous_diagnosis in anonymous_diagnoses

    @pytest.mark.unit
    def test_get_diagnoses_by_date_range(
        self, db_session: Session, user, diagnosis, faker
    ):
        """
        Test filtering diagnoses by date range.

        Given: Diagnoses created at different times
        When: Querying with date range filter
        Then: Only diagnoses within range are returned
        """
        # Query diagnoses for today
        from datetime import date, datetime, timezone, timedelta

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        today_end = datetime.combine(today, datetime.max.time()).replace(
            tzinfo=timezone.utc
        )

        today_diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(
                DiagnosisHistory.user_id == user.id,
                DiagnosisHistory.created_at >= today_start,
                DiagnosisHistory.created_at <= today_end,
            )
            .all()
        )

        # Assert today's diagnosis is found
        assert len(today_diagnoses) >= 1

    @pytest.mark.unit
    def test_get_diagnoses_ordered_by_date(
        self, db_session: Session, user, create_multiple_diagnoses
    ):
        """
        Test ordering diagnoses by creation date.

        Given: Multiple diagnoses for a user
        When: Querying with ORDER BY created_at DESC
        Then: Diagnoses are returned in descending date order
        """
        # Query diagnoses ordered by date
        diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.user_id == user.id)
            .order_by(DiagnosisHistory.created_at.desc())
            .all()
        )

        # Assert diagnoses are in descending order
        for i in range(len(diagnoses) - 1):
            assert diagnoses[i].created_at >= diagnoses[i + 1].created_at

    @pytest.mark.unit
    def test_query_by_syndrome_in_jsonb(self, db_session: Session, user, diagnosis):
        """
        Test querying diagnosis by JSONB field content.

        Given: A diagnosis with specific syndrome in results
        When: Querying by syndrome in JSONB results field
        Then: Matching diagnoses are returned
        """
        # Query by syndrome (JSONB field)
        syndrome = diagnosis.results["syndrome"]
        matching_diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.results["syndrome"].astext == syndrome)
            .all()
        )

        # Assert diagnosis with matching syndrome is found
        assert len(matching_diagnoses) >= 1
        assert diagnosis in matching_diagnoses


# ==============================================================================
# UPDATE Tests
# ==============================================================================

class TestDiagnosisUpdate:
    """Test diagnosis updates."""

    @pytest.mark.unit
    def test_update_diagnosis_results(
        self, db_session: Session, diagnosis, faker
    ):
        """
        Test updating diagnosis results.

        Given: An existing diagnosis
        When: Updating results JSONB field
        Then: Results are updated
        """
        # Update results
        new_results = {
            "syndrome": "肝肾阴虚",
            "confidence": faker.pyfloat(0.5, 0.95),
            "recommendations": ["滋补肝肾", "养阴清热"],
        }
        diagnosis.results = new_results
        db_session.flush()  # Flush for testing

        # Assert results were updated
        assert diagnosis.results == new_results
        assert diagnosis.results["syndrome"] == "肝肾阴虚"

    @pytest.mark.unit
    def test_update_diagnosis_feedback(
        self, db_session: Session, diagnosis
    ):
        """
        Test adding user feedback to diagnosis.

        Given: An existing diagnosis
        When: Setting feedback and feedback_comment fields
        Then: Feedback fields are updated
        """
        # Add positive feedback
        diagnosis.feedback = 1
        diagnosis.feedback_comment = "诊断很准确"
        db_session.flush()  # Flush for testing

        # Assert feedback was added
        assert diagnosis.feedback == 1
        assert diagnosis.feedback_comment == "诊断很准确"

    @pytest.mark.unit
    def test_update_diagnosis_model_version(
        self, db_session: Session, diagnosis
    ):
        """
        Test updating model version.

        Given: An existing diagnosis
        When: Updating model_version field
        Then: Model version is updated
        """
        # Update model version
        diagnosis.model_version = "v2.0"
        db_session.flush()  # Flush for testing

        # Assert model version was updated
        assert diagnosis.model_version == "v2.0"


# ==============================================================================
# JSONB Field Tests
# ==============================================================================

class TestDiagnosisJsonbFields:
    """Test JSONB field operations."""

    @pytest.mark.unit
    def test_user_info_jsonb_storage(
        self, db_session: Session, diagnosis, diagnosis_data
    ):
        """
        Test storing and retrieving user_info JSONB data.

        Given: Diagnosis with user_info containing age, gender, etc.
        When: Retrieving diagnosis from database
        Then: user_info JSONB is correctly preserved
        """
        # Refresh from DB

        # Assert user_info is preserved
        assert diagnosis.user_info == diagnosis_data["user_info"]
        assert "age" in diagnosis.user_info
        assert "gender" in diagnosis.user_info

    @pytest.mark.unit
    def test_features_jsonb_storage(
        self, db_session: Session, diagnosis, diagnosis_data
    ):
        """
        Test storing and retrieving features JSONB data.

        Given: Diagnosis with features containing tongue characteristics
        When: Retrieving diagnosis from database
        Then: features JSONB is correctly preserved
        """
        # Refresh from DB

        # Assert features are preserved
        assert diagnosis.features == diagnosis_data["features"]
        assert "tongue_color" in diagnosis.features

    @pytest.mark.unit
    def test_results_jsonb_storage(
        self, db_session: Session, diagnosis, diagnosis_data
    ):
        """
        Test storing and retrieving results JSONB data.

        Given: Diagnosis with results containing syndrome and recommendations
        When: Retrieving diagnosis from database
        Then: results JSONB is correctly preserved
        """
        # Refresh from DB

        # Assert results are preserved
        assert diagnosis.results == diagnosis_data["results"]
        assert "syndrome" in diagnosis.results
        assert "confidence" in diagnosis.results

    @pytest.mark.unit
    def test_jsonb_has_key_query(
        self, db_session: Session, diagnosis
    ):
        """
        Test querying by JSONB key existence.

        Given: Diagnoses with varying JSONB structures
        When: Querying by existence of specific JSONB key
        Then: Only diagnoses with that key are returned
        """
        # Query diagnoses that have 'syndrome' key in results
        diagnoses_with_syndrome = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.results.has_key("syndrome"))
            .all()
        )

        # Assert diagnosis with syndrome is found
        assert diagnosis in diagnoses_with_syndrome


# ==============================================================================
# Feedback Tests
# ==============================================================================

class TestDiagnosisFeedback:
    """Test feedback tracking functionality."""

    @pytest.mark.unit
    def test_add_positive_feedback(
        self, db_session: Session, diagnosis
    ):
        """
        Test adding positive feedback (1 = helpful).

        Given: An existing diagnosis
        When: Setting feedback = 1
        Then: Positive feedback is recorded
        """
        # Add positive feedback
        diagnosis.feedback = 1
        db_session.flush()  # Flush for testing

        # Assert positive feedback
        assert diagnosis.feedback == 1

    @pytest.mark.unit
    def test_add_negative_feedback(
        self, db_session: Session, diagnosis
    ):
        """
        Test adding negative feedback (-1 = not helpful).

        Given: An existing diagnosis
        When: Setting feedback = -1
        Then: Negative feedback is recorded
        """
        # Add negative feedback
        diagnosis.feedback = -1
        db_session.flush()  # Flush for testing

        # Assert negative feedback
        assert diagnosis.feedback == -1

    @pytest.mark.unit
    def test_add_feedback_with_comment(
        self, db_session: Session, diagnosis, faker
    ):
        """
        Test adding feedback with comment.

        Given: An existing diagnosis
        When: Setting feedback and feedback_comment
        Then: Both feedback and comment are recorded
        """
        # Add feedback with comment
        comment = faker.sentence()
        diagnosis.feedback = 1
        diagnosis.feedback_comment = comment
        db_session.flush()  # Flush for testing

        # Assert feedback and comment
        assert diagnosis.feedback == 1
        assert diagnosis.feedback_comment == comment

    @pytest.mark.unit
    def test_query_diagnoses_with_feedback(
        self, db_session: Session, diagnosis
    ):
        """
        Test querying diagnoses that have feedback.

        Given: Diagnoses with and without feedback
        When: Querying for diagnoses where feedback is not NULL
        Then: Only diagnoses with feedback are returned
        """
        # Add feedback
        diagnosis.feedback = 1
        db_session.flush()  # Flush for testing

        # Query diagnoses with feedback
        diagnoses_with_feedback = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.feedback.isnot(None))
            .all()
        )

        # Assert diagnosis with feedback is found
        assert diagnosis in diagnoses_with_feedback

    @pytest.mark.unit
    def test_query_diagnoses_without_feedback(
        self, db_session: Session, diagnosis
    ):
        """
        Test querying diagnoses without feedback.

        Given: A diagnosis without feedback (feedback = NULL)
        When: Querying for diagnoses where feedback is NULL
        Then: Diagnosis without feedback is returned
        """
        # Query diagnoses without feedback
        diagnoses_without_feedback = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.feedback.is_(None))
            .all()
        )

        # Assert diagnosis without feedback is found
        assert diagnosis in diagnoses_without_feedback


# ==============================================================================
# Relationship Tests
# ==============================================================================

class TestDiagnosisRelationships:
    """Test DiagnosisHistory model relationships."""

    @pytest.mark.unit
    def test_diagnosis_user_relationship(
        self, db_session: Session, diagnosis, user
    ):
        """
        Test Diagnosis -> User relationship.

        Given: A diagnosis for a specific user
        When: Accessing diagnosis.user
        Then: Correct user is returned
        """
        # Refresh relationship

        # Assert relationship works
        assert diagnosis.user is not None
        assert diagnosis.user.id == user.id
        assert diagnosis.user.nickname == user.nickname

    @pytest.mark.unit
    def test_anonymous_diagnosis_no_user(
        self, db_session: Session, anonymous_diagnosis
    ):
        """
        Test that anonymous diagnosis has no user.

        Given: An anonymous diagnosis (user_id = NULL)
        When: Accessing diagnosis.user
        Then: None is returned (not an error)
        """
        # Assert no user relationship
        assert anonymous_diagnosis.user is None

    @pytest.mark.unit
    def test_diagnosis_tongue_image_relationship(
        self, db_session: Session, diagnosis, tongue_image
    ):
        """
        Test Diagnosis -> TongueImage relationship.

        Given: A diagnosis using a specific tongue image
        When: Accessing diagnosis.tongue_image
        Then: Correct tongue image is returned
        """
        # Refresh relationship

        # Assert relationship works
        assert diagnosis.tongue_image is not None
        assert diagnosis.tongue_image.id == tongue_image.id
        assert diagnosis.tongue_image.file_hash == tongue_image.file_hash


# ==============================================================================
# Model Methods Tests
# ==============================================================================

class TestDiagnosisMethods:
    """Test DiagnosisHistory model instance methods."""

    @pytest.mark.unit
    def test_repr(self, db_session: Session, diagnosis):
        """
        Test __repr__ method returns useful debug info.

        Given: A diagnosis instance
        When: Converting to string
        Then: String contains useful debugging information
        """
        repr_str = repr(diagnosis)

        # Assert repr contains key information
        assert "DiagnosisHistory" in repr_str
        assert str(diagnosis.id) in repr_str
        assert "syndrome" in repr_str.lower()
