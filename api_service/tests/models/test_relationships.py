"""
Database Model Relationships Unit Tests
AI舌诊智能诊断系统 - Model Relationships Tests
Phase 4: Testing & Documentation - US-171

Tests for ORM relationships between models:
- User -> RefreshToken (one-to-many)
- User -> TongueImage (one-to-many)
- User -> DiagnosisHistory (one-to-many)
- User -> HealthRecord (one-to-many)
- TongueImage -> DiagnosisHistory (one-to-many)
- Cascade delete behaviors
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from api_service.app.models.database import (
    User,
    RefreshToken,
    TongueImage,
    DiagnosisHistory,
    HealthRecord,
)


# ==============================================================================
# User -> RefreshToken Relationship
# ==============================================================================

class TestUserRefreshTokenRelationship:
    """Test User to RefreshToken one-to-many relationship."""

    @pytest.mark.unit
    def test_user_has_many_refresh_tokens(
        self, db_session: Session, user: User
    ):
        """
        Test that a user can have multiple refresh tokens.

        Given: A user
        When: Creating multiple refresh tokens for the user
        Then: User.refresh_tokens returns all tokens
        """
        # Create multiple tokens
        tokens = []
        for i in range(3):
            token = RefreshToken(
                user_id=user.id,
                token=f"token_{i}",
                expires_at=datetime.now(timezone.utc),
            )
            db_session.add(token)
            tokens.append(token)

        db_session.flush()  # Flush for testing

        # Assert user has all tokens
        assert len(user.refresh_tokens) == 3

    @pytest.mark.unit
    def test_refresh_token_belongs_to_user(
        self, db_session: Session, user: User, refresh_token: RefreshToken
    ):
        """
        Test that refresh token has back-reference to user.

        Given: A refresh token for a user
        When: Accessing token.user
        Then: Correct user is returned
        """
        # Refresh relationship

        # Assert token belongs to user
        assert refresh_token.user.id == user.id
        assert refresh_token.user.nickname == user.nickname

    @pytest.mark.unit
    def test_cascade_delete_user_deletes_refresh_tokens(
        self, db_session: Session, user: User, faker
    ):
        """
        Test that deleting a user cascades to refresh tokens.

        Given: A user with refresh tokens
        When: User is hard deleted
        Then: Associated refresh tokens are deleted
        """
        # Create tokens
        token_ids = []
        for i in range(2):
            token = RefreshToken(
                user_id=user.id,
                token=f"token_{i}",
                expires_at=datetime.now(timezone.utc),
            )
            db_session.add(token)
            db_session.flush()
            token_ids.append(token.id)

        db_session.flush()  # Flush for testing

        # Hard delete user
        db_session.delete(user)
        db_session.flush()  # Flush for testing

        # Assert tokens are cascade deleted
        remaining_tokens = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.id.in_(token_ids))
            .all()
        )
        assert len(remaining_tokens) == 0


# ==============================================================================
# User -> TongueImage Relationship
# ==============================================================================

class TestUserTongueImageRelationship:
    """Test User to TongueImage one-to-many relationship."""

    @pytest.mark.unit
    def test_user_has_many_tongue_images(
        self, db_session: Session, user: User, faker
    ):
        """
        Test that a user can have multiple tongue images.

        Given: A user
        When: Creating multiple tongue images for the user
        Then: User.tongue_images returns all images
        """
        # Create multiple images
        images = []
        for i in range(3):
            image = TongueImage(
                user_id=user.id,
                file_hash=faker.sha256()[:64],
                storage_path=f"/path/to/image_{i}.jpg",
            )
            db_session.add(image)
            images.append(image)

        db_session.flush()  # Flush for testing

        # Assert user has all images
        assert len(user.tongue_images) == 3

    @pytest.mark.unit
    def test_tongue_image_belongs_to_user(
        self, db_session: Session, user: User, tongue_image: TongueImage
    ):
        """
        Test that tongue image has back-reference to user.

        Given: A tongue image for a user
        When: Accessing image.user
        Then: Correct user is returned
        """
        # Refresh relationship

        # Assert image belongs to user
        assert tongue_image.user.id == user.id

    @pytest.mark.unit
    def test_soft_delete_user_sets_tongue_image_user_to_null(
        self, db_session: Session, user: User, tongue_image: TongueImage
    ):
        """
        Test that soft-deleting user does NOT cascade to tongue images.

        Given: A user with tongue images (ON DELETE SET NULL)
        When: User is soft deleted (deleted_at is set)
        Then: Tongue images remain but user_id is preserved (SET NULL only on hard delete)
        """
        # Soft delete user
        user.deleted_at = datetime.now(timezone.utc)
        db_session.flush()  # Flush for testing

        # Assert tongue image still has user_id
        # Note: SET NULL only applies to hard deletes (ON DELETE clause)
        assert tongue_image.user_id == user.id

    @pytest.mark.unit
    def test_anonymous_tongue_image_has_no_user(
        self, db_session: Session, anonymous_tongue_image: TongueImage
    ):
        """
        Test that anonymous tongue image has no user.

        Given: A tongue image with user_id=NULL
        When: Accessing image.user
        Then: None is returned
        """
        # Assert no user
        assert anonymous_tongue_image.user is None
        assert anonymous_tongue_image.user_id is None


# ==============================================================================
# User -> DiagnosisHistory Relationship
# ==============================================================================

class TestUserDiagnosisRelationship:
    """Test User to DiagnosisHistory one-to-many relationship."""

    @pytest.mark.unit
    def test_user_has_many_diagnoses(
        self,
        db_session: Session,
        user: User,
        tongue_image: TongueImage,
        faker,
    ):
        """
        Test that a user can have multiple diagnoses.

        Given: A user
        When: Creating multiple diagnoses for the user
        Then: User.diagnoses returns all diagnoses
        """
        # Create multiple diagnoses
        diagnoses = []
        for i in range(3):
            diagnosis = DiagnosisHistory(
                user_id=user.id,
                tongue_image_id=tongue_image.id,
                user_info={"age": faker.pyint(18, 80)},
                features={"tongue_color": "red"},
                results={"syndrome": "测试证型", "confidence": 0.8},
            )
            db_session.add(diagnosis)
            diagnoses.append(diagnosis)

        db_session.flush()  # Flush for testing

        # Assert user has all diagnoses
        assert len(user.diagnoses) == 3

    @pytest.mark.unit
    def test_diagnosis_belongs_to_user(
        self, db_session: Session, user: User, diagnosis: DiagnosisHistory
    ):
        """
        Test that diagnosis has back-reference to user.

        Given: A diagnosis for a user
        When: Accessing diagnosis.user
        Then: Correct user is returned
        """
        # Refresh relationship

        # Assert diagnosis belongs to user
        assert diagnosis.user.id == user.id

    @pytest.mark.unit
    def test_query_user_diagnoses_ordered(
        self,
        db_session: Session,
        user: User,
        create_multiple_diagnoses,
    ):
        """
        Test querying user's diagnoses ordered by date.

        Given: A user with multiple diagnoses
        When: Querying with ORDER BY created_at DESC
        Then: Diagnoses are in correct order
        """
        # Query ordered diagnoses
        diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.user_id == user.id)
            .order_by(DiagnosisHistory.created_at.desc())
            .limit(10)
            .all()
        )

        # Assert order is correct
        for i in range(len(diagnoses) - 1):
            assert diagnoses[i].created_at >= diagnoses[i + 1].created_at

    @pytest.mark.unit
    def test_anonymous_diagnosis_has_no_user(
        self, db_session: Session, anonymous_diagnosis: DiagnosisHistory
    ):
        """
        Test that anonymous diagnosis has no user.

        Given: A diagnosis with user_id=NULL
        When: Accessing diagnosis.user
        Then: None is returned
        """
        # Assert no user
        assert anonymous_diagnosis.user is None
        assert anonymous_diagnosis.user_id is None


# ==============================================================================
# User -> HealthRecord Relationship
# ==============================================================================

class TestUserHealthRecordRelationship:
    """Test User to HealthRecord one-to-many relationship."""

    @pytest.mark.unit
    def test_user_has_many_health_records(
        self, db_session: Session, user: User, faker
    ):
        """
        Test that a user can have multiple health records.

        Given: A user
        When: Creating multiple health records for the user
        Then: User.health_records returns all records
        """
        # Create multiple records
        records = []
        for i in range(3):
            record = HealthRecord(
                user_id=user.id,
                record_type="blood_pressure",
                record_value={
                    "systolic": faker.pyint(90, 140),
                    "diastolic": faker.pyint(60, 90),
                },
            )
            db_session.add(record)
            records.append(record)

        db_session.flush()  # Flush for testing

        # Assert user has all records
        assert len(user.health_records) == 3

    @pytest.mark.unit
    def test_health_record_belongs_to_user(
        self, db_session: Session, user: User, health_record: HealthRecord
    ):
        """
        Test that health record has back-reference to user.

        Given: A health record for a user
        When: Accessing record.user
        Then: Correct user is returned
        """
        # Refresh relationship

        # Assert record belongs to user
        assert health_record.user.id == user.id

    @pytest.mark.unit
    def test_cascade_delete_user_deletes_health_records(
        self, db_session: Session, user: User, faker
    ):
        """
        Test that deleting a user cascades to health records.

        Given: A user with health records
        When: User is hard deleted
        Then: Associated health records are deleted
        """
        # Create records
        record_ids = []
        for i in range(2):
            record = HealthRecord(
                user_id=user.id,
                record_type="weight",
                record_value={"value": faker.pyint(50, 100), "unit": "kg"},
            )
            db_session.add(record)
            db_session.flush()
            record_ids.append(record.id)

        db_session.flush()  # Flush for testing

        # Hard delete user
        db_session.delete(user)
        db_session.flush()  # Flush for testing

        # Assert records are cascade deleted
        remaining_records = (
            db_session.query(HealthRecord)
            .filter(HealthRecord.id.in_(record_ids))
            .all()
        )
        assert len(remaining_records) == 0


# ==============================================================================
# TongueImage -> DiagnosisHistory Relationship
# ==============================================================================

class TestTongueImageDiagnosisRelationship:
    """Test TongueImage to DiagnosisHistory one-to-many relationship."""

    @pytest.mark.unit
    def test_tongue_image_has_many_diagnoses(
        self,
        db_session: Session,
        user: User,
        tongue_image: TongueImage,
        faker,
    ):
        """
        Test that a tongue image can have multiple diagnoses.

        Given: A tongue image
        When: Creating multiple diagnoses using the same image
        Then: TongueImage.diagnoses returns all diagnoses
        """
        # Create multiple diagnoses using same image
        diagnoses = []
        for i in range(3):
            diagnosis = DiagnosisHistory(
                user_id=user.id,
                tongue_image_id=tongue_image.id,
                user_info={"age": faker.pyint(18, 80)},
                features={"tongue_color": "red"},
                results={"syndrome": f"证型_{i}", "confidence": 0.8},
            )
            db_session.add(diagnosis)
            diagnoses.append(diagnosis)

        db_session.flush()  # Flush for testing

        # Assert image has all diagnoses
        assert len(tongue_image.diagnoses) == 3

    @pytest.mark.unit
    def test_diagnosis_belongs_to_tongue_image(
        self, db_session: Session, diagnosis: DiagnosisHistory, tongue_image: TongueImage
    ):
        """
        Test that diagnosis has back-reference to tongue image.

        Given: A diagnosis using a tongue image
        When: Accessing diagnosis.tongue_image
        Then: Correct tongue image is returned
        """
        # Refresh relationship

        # Assert diagnosis uses correct image
        assert diagnosis.tongue_image.id == tongue_image.id
        assert diagnosis.tongue_image.file_hash == tongue_image.file_hash

    @pytest.mark.unit
    def test_cascade_delete_tongue_image_deletes_diagnoses(
        self,
        db_session: Session,
        user: User,
        tongue_image: TongueImage,
        faker,
    ):
        """
        Test that deleting a tongue image cascades to diagnoses.

        Given: A tongue image with diagnoses
        When: Tongue image is hard deleted
        Then: Associated diagnoses are deleted
        """
        # Create diagnoses
        diagnosis_ids = []
        for i in range(2):
            diagnosis = DiagnosisHistory(
                user_id=user.id,
                tongue_image_id=tongue_image.id,
                user_info={"age": faker.pyint(18, 80)},
                features={"tongue_color": "red"},
                results={"syndrome": "测试", "confidence": 0.8},
            )
            db_session.add(diagnosis)
            db_session.flush()
            diagnosis_ids.append(diagnosis.id)

        db_session.flush()  # Flush for testing

        # Hard delete tongue image
        db_session.delete(tongue_image)
        db_session.flush()  # Flush for testing

        # Assert diagnoses are cascade deleted
        remaining_diagnoses = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.id.in_(diagnosis_ids))
            .all()
        )
        assert len(remaining_diagnoses) == 0


# ==============================================================================
# Complex Relationship Queries
# ==============================================================================

class TestComplexRelationshipQueries:
    """Test complex queries involving multiple relationships."""

    @pytest.mark.unit
    def test_join_user_and_diagnoses(
        self, db_session: Session, user: User, diagnosis: DiagnosisHistory
    ):
        """
        Test joining users with their diagnoses.

        Given: A user with diagnoses
        When: Querying with JOIN
        Then: Combined results are returned
        """
        # Query with join
        result = (
            db_session.query(User, DiagnosisHistory)
            .join(DiagnosisHistory, User.id == DiagnosisHistory.user_id)
            .filter(User.id == user.id)
            .first()
        )

        # Assert join returns both user and diagnosis
        assert result is not None
        queried_user, queried_diagnosis = result
        assert queried_user.id == user.id
        assert queried_diagnosis.id == diagnosis.id

    @pytest.mark.unit
    def test_eager_load_relationships(
        self, db_session: Session, user: User, create_multiple_diagnoses
    ):
        """
        Test eager loading relationships to avoid N+1 queries.

        Given: A user with many related records
        When: Querying with joinedload
        Then: Relationships are loaded efficiently
        """
        from sqlalchemy.orm import joinedload

        # Query with eager load
        user_with_diagnoses = (
            db_session.query(User)
            .options(joinedload(User.diagnoses))
            .filter(User.id == user.id)
            .first()
        )

        # Assert relationships are loaded
        assert len(user_with_diagnoses.diagnoses) >= 3
        # Access should not trigger additional queries
        for diagnosis in user_with_diagnoses.diagnoses:
            assert diagnosis.user_id == user.id

    @pytest.mark.unit
    def test_count_user_diagnoses(
        self, db_session: Session, user: User, create_multiple_diagnoses
    ):
        """
        Test counting user's diagnoses.

        Given: A user with multiple diagnoses
        When: Using count aggregation
        Then: Correct count is returned
        """
        # Count diagnoses
        diagnosis_count = (
            db_session.query(DiagnosisHistory)
            .filter(DiagnosisHistory.user_id == user.id)
            .count()
        )

        # Assert count is correct
        assert diagnosis_count >= 3
