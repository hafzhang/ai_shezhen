"""
User Model Unit Tests
AI舌诊智能诊断系统 - User Model Tests
Phase 4: Testing & Documentation - US-171

Tests for User model CRUD operations:
- Create user with phone/password authentication
- Create user with WeChat/Douyin mini-program authentication
- Read/query user by various fields
- Update user fields
- Soft delete user
- User model methods (is_active, has_password_auth, has_miniprogram_auth)
"""

import pytest
from sqlalchemy.orm import Session

from api_service.app.models.database import User


# ==============================================================================
# CREATE Tests
# ==============================================================================

class TestUserCreate:
    """Test user creation and persistence."""

    @pytest.mark.unit
    def test_create_user_with_phone(self, db_session: Session, user_data: dict):
        """
        Test creating a user with phone authentication.

        Given: Valid user data with phone and password_hash
        When: User is created and committed to database
        Then: User is persisted with correct fields and auto-generated ID
        """
        # Create user
        user = User(**user_data)
        db_session.add(user)
        db_session.flush()  # Flush to get the ID and default values

        # Assert user was created
        assert user.id is not None
        assert user.phone == user_data["phone"]
        assert user.email == user_data["email"]
        assert user.nickname == user_data["nickname"]
        assert user.avatar_url == user_data["avatar_url"]
        assert user.password_hash == user_data["password_hash"]
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.deleted_at is None

    @pytest.mark.unit
    def test_create_user_with_wechat_openid(self, db_session: Session, faker):
        """
        Test creating a WeChat mini-program user.

        Given: Valid WeChat openid and openid_type
        When: User is created
        Then: User is persisted with OpenID fields
        """
        # Create WeChat user
        openid = faker.uuid4()[:50]
        user = User(
            openid=openid,
            openid_type="wechat",
            nickname=faker.name(),
        )
        db_session.add(user)
        db_session.flush()  # Flush for testing

        # Assert WeChat user was created
        assert user.id is not None
        assert user.openid == openid
        assert user.openid_type == "wechat"
        assert user.nickname is not None

    @pytest.mark.unit
    def test_create_user_with_douyin_openid(self, db_session: Session, faker):
        """
        Test creating a Douyin mini-program user.

        Given: Valid Douyin openid and openid_type
        When: User is created
        Then: User is persisted with OpenID fields
        """
        # Create Douyin user
        openid = faker.uuid4()[:50]
        user = User(
            openid=openid,
            openid_type="douyin",
            nickname=faker.name(),
        )
        db_session.add(user)
        db_session.flush()  # Flush for testing

        # Assert Douyin user was created
        assert user.id is not None
        assert user.openid == openid
        assert user.openid_type == "douyin"

    @pytest.mark.unit
    def test_create_user_with_minimal_fields(self, db_session: Session):
        """
        Test creating a user with only required fields.

        Given: Only nickname (or no fields at all)
        When: User is created
        Then: User is persisted with NULL for optional fields
        """
        # Create user with minimal data
        user = User()
        db_session.add(user)
        db_session.flush()  # Flush for testing

        # Assert user was created with NULL optional fields
        assert user.id is not None
        assert user.phone is None
        assert user.email is None
        assert user.openid is None
        assert user.openid_type is None

    @pytest.mark.unit
    def test_phone_unique_constraint(self, db_session: Session, user_data: dict, faker):
        """
        Test that phone numbers must be unique.

        Given: An existing user with a phone number
        When: Attempting to create another user with the same phone
        Then: Database integrity error is raised
        """
        # Create first user
        user1 = User(**user_data)
        db_session.add(user1)
        db_session.flush()  # Flush for testing

        # Attempt to create second user with same phone
        user2 = User(
            phone=user_data["phone"],  # Same phone
            nickname=faker.name(),
            password_hash="$2b$12$" + faker.password(length=53),
        )
        db_session.add(user2)

        # Assert integrity error is raised
        with pytest.raises(Exception):  # IntegrityError
            db_session.flush()  # Flush for testing

    @pytest.mark.unit
    def test_email_unique_constraint(self, db_session: Session, user_data: dict, faker):
        """
        Test that email addresses must be unique.

        Given: An existing user with an email
        When: Attempting to create another user with the same email
        Then: Database integrity error is raised
        """
        # Create first user
        user1 = User(**user_data)
        db_session.add(user1)
        db_session.flush()  # Flush for testing

        # Attempt to create second user with same email
        user2 = User(
            email=user_data["email"],  # Same email
            nickname=faker.name(),
            password_hash="$2b$12$" + faker.password(length=53),
        )
        db_session.add(user2)

        # Assert integrity error is raised
        with pytest.raises(Exception):  # IntegrityError
            db_session.flush()  # Flush for testing


# ==============================================================================
# READ/QUERY Tests
# ==============================================================================

class TestUserRead:
    """Test user retrieval and querying."""

    @pytest.mark.unit
    def test_get_user_by_id(self, db_session: Session, user: User):
        """
        Test retrieving a user by ID.

        Given: A user with known ID
        When: Querying user by ID
        Then: Correct user is returned
        """
        # Query user by ID
        found_user = db_session.query(User).filter(User.id == user.id).first()

        # Assert correct user was found
        assert found_user is not None
        assert found_user.id == user.id
        assert found_user.nickname == user.nickname

    @pytest.mark.unit
    def test_get_user_by_phone(self, db_session: Session, user: User):
        """
        Test retrieving a user by phone number.

        Given: A user with known phone number
        When: Querying user by phone
        Then: Correct user is returned
        """
        # Query user by phone
        found_user = db_session.query(User).filter(User.phone == user.phone).first()

        # Assert correct user was found
        assert found_user is not None
        assert found_user.phone == user.phone
        assert found_user.id == user.id

    @pytest.mark.unit
    def test_get_user_by_email(self, db_session: Session, user: User):
        """
        Test retrieving a user by email address.

        Given: A user with known email
        When: Querying user by email
        Then: Correct user is returned
        """
        # Query user by email
        found_user = db_session.query(User).filter(User.email == user.email).first()

        # Assert correct user was found
        assert found_user is not None
        assert found_user.email == user.email
        assert found_user.id == user.id

    @pytest.mark.unit
    def test_get_user_by_openid(self, db_session: Session, wechat_user: User):
        """
        Test retrieving a mini-program user by openid.

        Given: A WeChat user with known openid
        When: Querying user by openid and openid_type
        Then: Correct user is returned
        """
        # Query user by openid
        found_user = db_session.query(User).filter(
            User.openid == wechat_user.openid,
            User.openid_type == "wechat",
        ).first()

        # Assert correct user was found
        assert found_user is not None
        assert found_user.openid == wechat_user.openid
        assert found_user.id == wechat_user.id

    @pytest.mark.unit
    def test_get_nonexistent_user(self, db_session: Session, faker):
        """
        Test querying for a non-existent user.

        Given: No user with a specific phone number
        When: Querying user by that phone
        Then: None is returned
        """
        # Query for non-existent user
        found_user = db_session.query(User).filter(
            User.phone == "00000000000"
        ).first()

        # Assert no user found
        assert found_user is None

    @pytest.mark.unit
    def test_list_all_users(self, db_session: Session, create_multiple_users):
        """
        Test listing all users.

        Given: Multiple users in database
        When: Querying all users
        Then: All users are returned
        """
        # Create multiple users
        users = create_multiple_users(count=5)

        # Query all users
        all_users = db_session.query(User).all()

        # Assert all users are returned
        assert len(all_users) >= 5

    @pytest.mark.unit
    def test_filter_active_users(self, db_session: Session, user: User):
        """
        Test filtering active users (not soft deleted).

        Given: Active and deleted users
        When: Filtering for users with deleted_at=NULL
        Then: Only active users are returned
        """
        # Soft delete the user
        user.deleted_at = "2024-01-01 00:00:00"
        db_session.flush()  # Flush for testing

        # Query for active users
        active_users = db_session.query(User).filter(User.deleted_at.is_(None)).all()

        # Assert soft-deleted user is not in active users
        assert user.id not in [u.id for u in active_users]


# ==============================================================================
# UPDATE Tests
# ==============================================================================

class TestUserUpdate:
    """Test user updates."""

    @pytest.mark.unit
    def test_update_user_nickname(self, db_session: Session, user: User, faker):
        """
        Test updating user nickname.

        Given: An existing user
        When: Updating nickname field
        Then: Nickname is updated and updated_at is refreshed
        """
        # Update nickname
        old_updated_at = user.updated_at
        user.nickname = faker.name()
        db_session.flush()  # Flush for testing

        # Assert nickname was updated
        assert user.nickname != user.nickname
        assert user.updated_at >= old_updated_at

    @pytest.mark.unit
    def test_update_user_avatar(self, db_session: Session, user: User, faker):
        """
        Test updating user avatar URL.

        Given: An existing user
        When: Updating avatar_url field
        Then: Avatar URL is updated
        """
        # Update avatar
        new_avatar_url = faker.url()
        user.avatar_url = new_avatar_url
        db_session.flush()  # Flush for testing

        # Assert avatar was updated
        assert user.avatar_url == new_avatar_url

    @pytest.mark.unit
    def test_update_user_password(self, db_session: Session, user: User, faker):
        """
        Test updating user password hash.

        Given: An existing user with password
        When: Updating password_hash field
        Then: Password hash is updated
        """
        # Update password
        new_password_hash = "$2b$12$" + faker.password(length=53)
        user.password_hash = new_password_hash
        db_session.flush()  # Flush for testing

        # Assert password was updated
        assert user.password_hash == new_password_hash

    @pytest.mark.unit
    def test_add_password_to_miniprogram_user(
        self, db_session: Session, wechat_user: User, faker
    ):
        """
        Test adding password to a mini-program user.

        Given: A WeChat user without password
        When: Adding password_hash
        Then: User now has both mini-program and password auth
        """
        # Assert user initially has no password
        assert wechat_user.password_hash is None

        # Add password
        wechat_user.password_hash = "$2b$12$" + faker.pystr(50)
        db_session.flush()  # Flush for testing

        # Assert user now has password
        assert wechat_user.password_hash is not None
        assert wechat_user.has_password_auth() is True
        assert wechat_user.has_miniprogram_auth() is True


# ==============================================================================
# DELETE Tests (Soft Delete)
# ==============================================================================

class TestUserDelete:
    """Test user soft delete."""

    @pytest.mark.unit
    def test_soft_delete_user(self, db_session: Session, user: User):
        """
        Test soft deleting a user.

        Given: An active user
        When: Setting deleted_at timestamp
        Then: User is marked as deleted but not removed from database
        """
        # Soft delete user
        from datetime import datetime, timezone

        user.deleted_at = datetime.now(timezone.utc)
        db_session.flush()  # Flush for testing

        # Assert user is soft deleted
        assert user.deleted_at is not None
        assert user.is_active() is False

        # Assert user still exists in database
        found_user = db_session.query(User).filter(User.id == user.id).first()
        assert found_user is not None

    @pytest.mark.unit
    def test_soft_deleted_user_not_in_active_queries(
        self, db_session: Session, user: User
    ):
        """
        Test that soft-deleted users are excluded from active queries.

        Given: A soft-deleted user
        When: Querying for active users (deleted_at=NULL)
        Then: Soft-deleted user is not in results
        """
        # Soft delete user
        from datetime import datetime, timezone

        user.deleted_at = datetime.now(timezone.utc)
        db_session.flush()  # Flush for testing

        # Query for active users
        active_users = db_session.query(User).filter(User.deleted_at.is_(None)).all()

        # Assert deleted user not in active users
        assert user not in active_users


# ==============================================================================
# Model Methods Tests
# ==============================================================================

class TestUserMethods:
    """Test User model instance methods."""

    @pytest.mark.unit
    def test_is_active_true(self, db_session: Session, user: User):
        """
        Test is_active() returns True for active users.

        Given: A user with deleted_at=NULL
        When: Calling is_active()
        Then: True is returned
        """
        assert user.is_active() is True

    @pytest.mark.unit
    def test_is_active_false(self, db_session: Session, user: User):
        """
        Test is_active() returns False for deleted users.

        Given: A user with deleted_at set
        When: Calling is_active()
        Then: False is returned
        """
        from datetime import datetime, timezone

        user.deleted_at = datetime.now(timezone.utc)
        db_session.flush()  # Flush for testing

        assert user.is_active() is False

    @pytest.mark.unit
    def test_has_password_auth_true(self, db_session: Session, user: User):
        """
        Test has_password_auth() returns True for users with password.

        Given: A user with password_hash set
        When: Calling has_password_auth()
        Then: True is returned
        """
        assert user.has_password_auth() is True

    @pytest.mark.unit
    def test_has_password_auth_false(self, db_session: Session, wechat_user: User):
        """
        Test has_password_auth() returns False for mini-program users.

        Given: A WeChat user without password_hash
        When: Calling has_password_auth()
        Then: False is returned
        """
        assert wechat_user.has_password_auth() is False

    @pytest.mark.unit
    def test_has_miniprogram_auth_true(self, db_session: Session, wechat_user: User):
        """
        Test has_miniprogram_auth() returns True for mini-program users.

        Given: A user with openid and openid_type set
        When: Calling has_miniprogram_auth()
        Then: True is returned
        """
        assert wechat_user.has_miniprogram_auth() is True

    @pytest.mark.unit
    def test_has_miniprogram_auth_false(self, db_session: Session, user: User):
        """
        Test has_miniprogram_auth() returns False for password users.

        Given: A user without openid
        When: Calling has_miniprogram_auth()
        Then: False is returned
        """
        assert user.has_miniprogram_auth() is False

    @pytest.mark.unit
    def test_repr(self, db_session: Session, user: User):
        """
        Test __repr__ method returns useful debug info.

        Given: A user instance
        When: Converting to string
        Then: String contains useful debugging information
        """
        repr_str = repr(user)

        # Assert repr contains key information
        assert "User" in repr_str
        assert str(user.id) in repr_str
        assert "deleted=False" in repr_str


# ==============================================================================
# Relationship Tests
# ==============================================================================

class TestUserRelationships:
    """Test User model relationships to other models."""

    @pytest.mark.unit
    def test_user_refresh_tokens_relationship(
        self, db_session: Session, user: User, refresh_token
    ):
        """
        Test User -> RefreshToken relationship.

        Given: A user with refresh token
        When: Accessing user.refresh_tokens
        Then: List contains the refresh token
        """
        # Refresh relationship

        # Assert relationship works
        assert len(user.refresh_tokens) > 0
        assert user.refresh_tokens[0].id == refresh_token.id
        assert user.refresh_tokens[0].user_id == user.id

    @pytest.mark.unit
    def test_user_tongue_images_relationship(
        self, db_session: Session, user: User, tongue_image
    ):
        """
        Test User -> TongueImage relationship.

        Given: A user with tongue images
        When: Accessing user.tongue_images
        Then: List contains the tongue images
        """
        # Refresh relationship

        # Assert relationship works
        assert len(user.tongue_images) > 0
        assert user.tongue_images[0].id == tongue_image.id
        assert user.tongue_images[0].user_id == user.id

    @pytest.mark.unit
    def test_user_diagnoses_relationship(
        self, db_session: Session, user: User, diagnosis
    ):
        """
        Test User -> DiagnosisHistory relationship.

        Given: A user with diagnoses
        When: Accessing user.diagnoses
        Then: List contains the diagnoses
        """
        # Refresh relationship

        # Assert relationship works
        assert len(user.diagnoses) > 0
        assert user.diagnoses[0].id == diagnosis.id
        assert user.diagnoses[0].user_id == user.id

    @pytest.mark.unit
    def test_user_health_records_relationship(
        self, db_session: Session, user: User, health_record
    ):
        """
        Test User -> HealthRecord relationship.

        Given: A user with health records
        When: Accessing user.health_records
        Then: List contains the health records
        """
        # Refresh relationship

        # Assert relationship works
        assert len(user.health_records) > 0
        assert user.health_records[0].id == health_record.id
        assert user.health_records[0].user_id == user.id

    @pytest.mark.unit
    def test_cascade_delete_refresh_tokens(
        self, db_session: Session, user: User, refresh_token
    ):
        """
        Test that deleting a user cascades to refresh tokens.

        Given: A user with refresh tokens
        When: User is deleted (hard delete for test)
        Then: Related refresh tokens are also deleted
        """
        token_id = refresh_token.id

        # Hard delete user (not soft delete)
        db_session.delete(user)
        db_session.flush()  # Flush for testing

        # Assert refresh token was cascade deleted
        deleted_token = db_session.query(type(refresh_token)).filter(
            type(refresh_token).id == token_id
        ).first()
        assert deleted_token is None
