#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Authentication API Integration Tests
AI舌诊智能诊断系统 - Auth API Tests
Phase 4: Testing & Documentation - US-172

Tests for authentication API endpoints:
- POST /api/v2/auth/register - User registration
- POST /api/v2/auth/login - User login
- POST /api/v2/auth/refresh - Token refresh
- POST /api/v2/auth/logout - User logout

Test Coverage:
- Registration flow validation
- Login flow validation
- Token refresh flow validation
- Logout flow validation
- Error handling for invalid inputs
- Edge cases and security scenarios
"""

import datetime
import os
from typing import Generator
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api_service.app.models.database import User, RefreshToken
from api_service.app.api.deps import get_db


# ==============================================================================
# Minimal FastAPI App for Testing
# ==============================================================================

@pytest.fixture(scope="function")
def test_app(db_session: Session) -> FastAPI:
    """
    Create a minimal FastAPI app with just the auth router for testing.

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

    # Import and include auth router (import here to avoid loading main.py)
    from api_service.app.api.v2 import auth
    app.include_router(auth.router, prefix="/api/v2/auth", tags=["Authentication"])

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


# ==============================================================================
# Test Data Fixtures
# ==============================================================================

@pytest.fixture(scope="function")
def valid_register_data(faker) -> dict:
    """
    Generate valid user registration data.

    Args:
        faker: Faker instance

    Returns:
        Dictionary with valid registration fields
    """
    return {
        "phone": faker.phone_number(),
        "password": "abc12345",
        "nickname": faker.name(),
        "email": faker.email()
    }


@pytest.fixture(scope="function")
def valid_login_data(user: User) -> dict:
    """
    Generate valid login data for existing user.

    Args:
        user: User fixture

    Returns:
        Dictionary with valid login fields
    """
    return {
        "phone": user.phone,
        "password": "testpassword"  # Default password from user fixture
    }


@pytest.fixture(scope="function")
def registered_user(client: TestClient, valid_register_data: dict) -> dict:
    """
    Register a user via API and return the response.

    Args:
        client: TestClient fixture
        valid_register_data: Registration data

    Returns:
        Response data from registration
    """
    response = client.post("/api/v2/auth/register", json=valid_register_data)
    assert response.status_code == 201
    return response.json()


# ==============================================================================
# Registration Flow Tests
# ==============================================================================

class TestRegistrationFlow:
    """Test user registration flow."""

    @pytest.mark.integration
    def test_register_new_user_success(self, client: TestClient, valid_register_data: dict):
        """
        Test successful user registration.

        Given: Valid registration data with phone, password, nickname, email
        When: POST /api/v2/auth/register is called
        Then: User is created and tokens are returned
        """
        response = client.post("/api/v2/auth/register", json=valid_register_data)

        # Assert response status
        assert response.status_code == 201

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "注册成功"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data

        # Assert user info
        user = data["user"]
        assert user["phone"] == valid_register_data["phone"]
        assert user["nickname"] == valid_register_data["nickname"]
        assert user["email"] == valid_register_data["email"]
        assert "id" in user

    @pytest.mark.integration
    def test_register_with_minimal_fields(self, client: TestClient, faker):
        """
        Test registration with only required fields.

        Given: Valid registration data with only phone and password
        When: POST /api/v2/auth/register is called
        Then: User is created with default nickname
        """
        register_data = {
            "phone": faker.phone_number(),
            "password": "abc12345"
        }

        response = client.post("/api/v2/auth/register", json=register_data)

        # Assert response status
        assert response.status_code == 201

        # Assert nickname defaults to phone
        data = response.json()
        assert data["user"]["nickname"] == register_data["phone"]

    @pytest.mark.integration
    def test_register_duplicate_phone_fails(self, client: TestClient, registered_user: dict, faker):
        """
        Test registration with duplicate phone number fails.

        Given: A user with phone number already registered
        When: Attempting to register with same phone number
        Then: 400 error is returned with appropriate message
        """
        existing_phone = registered_user["user"]["phone"]
        register_data = {
            "phone": existing_phone,
            "password": "xyz98765",
            "nickname": faker.name()
        }

        response = client.post("/api/v2/auth/register", json=register_data)

        # Assert error response
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "手机号已被注册"

    @pytest.mark.integration
    def test_register_duplicate_email_fails(self, client: TestClient, registered_user: dict, faker):
        """
        Test registration with duplicate email fails.

        Given: A user with email already registered
        When: Attempting to register with same email
        Then: 400 error is returned with appropriate message
        """
        existing_email = registered_user["user"]["email"]
        register_data = {
            "phone": faker.phone_number(),
            "password": "xyz98765",
            "email": existing_email
        }

        response = client.post("/api/v2/auth/register", json=register_data)

        # Assert error response
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "邮箱已被注册"

    @pytest.mark.integration
    def test_register_invalid_phone_format(self, client: TestClient):
        """
        Test registration with invalid phone format fails.

        Given: Registration data with invalid phone number
        When: POST /api/v2/auth/register is called
        Then: 422 validation error is returned
        """
        register_data = {
            "phone": "12345",  # Invalid format
            "password": "abc12345"
        }

        response = client.post("/api/v2/auth/register", json=register_data)

        # Assert validation error
        assert response.status_code == 422

    @pytest.mark.integration
    def test_register_weak_password_fails(self, client: TestClient, faker):
        """
        Test registration with weak password fails.

        Given: Registration data with password that doesn't meet requirements
        When: POST /api/v2/auth/register is called
        Then: 422 validation error is returned
        """
        test_cases = [
            {"phone": faker.phone_number(), "password": "short"},  # Too short
            {"phone": faker.phone_number(), "password": "onlyletters"},  # No numbers
            {"phone": faker.phone_number(), "password": "12345678"},  # No letters
        ]

        for register_data in test_cases:
            response = client.post("/api/v2/auth/register", json=register_data)
            assert response.status_code == 422

    @pytest.mark.integration
    def test_register_invalid_email_format(self, client: TestClient, faker):
        """
        Test registration with invalid email format fails.

        Given: Registration data with invalid email format
        When: POST /api/v2/auth/register is called
        Then: 422 validation error is returned
        """
        register_data = {
            "phone": faker.phone_number(),
            "password": "abc12345",
            "email": "not-an-email"
        }

        response = client.post("/api/v2/auth/register", json=register_data)

        # Assert validation error
        assert response.status_code == 422


# ==============================================================================
# Login Flow Tests
# ==============================================================================

class TestLoginFlow:
    """Test user login flow."""

    @pytest.mark.integration
    def test_login_success(self, client: TestClient, user: User):
        """
        Test successful user login.

        Given: A registered user with valid credentials
        When: POST /api/v2/auth/login is called with correct credentials
        Then: Access and refresh tokens are returned
        """
        login_data = {
            "phone": user.phone,
            "password": "testpassword"  # From user fixture
        }

        response = client.post("/api/v2/auth/login", json=login_data)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "登录成功"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data

        # Assert user info
        assert data["user"]["phone"] == user.phone

    @pytest.mark.integration
    def test_login_wrong_password_fails(self, client: TestClient, user: User):
        """
        Test login with wrong password fails.

        Given: A registered user
        When: POST /api/v2/auth/login is called with wrong password
        Then: 401 error is returned
        """
        login_data = {
            "phone": user.phone,
            "password": "wrongpassword"
        }

        response = client.post("/api/v2/auth/login", json=login_data)

        # Assert error response
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "手机号或密码错误"

    @pytest.mark.integration
    def test_login_nonexistent_phone_fails(self, client: TestClient, faker):
        """
        Test login with non-existent phone number fails.

        Given: No user with the provided phone number
        When: POST /api/v2/auth/login is called
        Then: 401 error is returned
        """
        login_data = {
            "phone": faker.phone_number(),
            "password": "anypassword"
        }

        response = client.post("/api/v2/auth/login", json=login_data)

        # Assert error response
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "手机号或密码错误"

    @pytest.mark.integration
    def test_login_deleted_account_fails(self, client: TestClient, db_session: Session, user: User):
        """
        Test login with soft-deleted account fails.

        Given: A soft-deleted user account
        When: POST /api/v2/auth/login is called
        Then: 401 error is returned
        """
        # Soft delete the user
        user.deleted_at = datetime.datetime.now(datetime.timezone.utc)
        db_session.commit()

        login_data = {
            "phone": user.phone,
            "password": "testpassword"
        }

        response = client.post("/api/v2/auth/login", json=login_data)

        # Assert error response
        assert response.status_code == 401

    @pytest.mark.integration
    def test_login_invalid_phone_format(self, client: TestClient):
        """
        Test login with invalid phone format fails.

        Given: Login data with invalid phone format
        When: POST /api/v2/auth/login is called
        Then: 422 validation error is returned
        """
        login_data = {
            "phone": "invalid",
            "password": "abc12345"
        }

        response = client.post("/api/v2/auth/login", json=login_data)

        # Assert validation error
        assert response.status_code == 422


# ==============================================================================
# Token Refresh Flow Tests
# ==============================================================================

class TestTokenRefreshFlow:
    """Test token refresh flow."""

    @pytest.mark.integration
    def test_refresh_token_success(self, client: TestClient, registered_user: dict):
        """
        Test successful token refresh.

        Given: A valid refresh token from registration
        When: POST /api/v2/auth/refresh is called
        Then: New access token is returned
        """
        refresh_token = registered_user["refresh_token"]
        refresh_data = {"refresh_token": refresh_token}

        response = client.post("/api/v2/auth/refresh", json=refresh_data)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "令牌刷新成功"
        assert "access_token" in data
        assert "expires_in" in data
        assert data["expires_in"] == 1800  # 30 minutes

    @pytest.mark.integration
    def test_refresh_with_revoked_token_fails(self, client: TestClient, registered_user: dict, db_session: Session):
        """
        Test refresh with revoked token fails.

        Given: A refresh token that has been revoked
        When: POST /api/v2/auth/refresh is called
        Then: 401 error is returned
        """
        refresh_token = registered_user["refresh_token"]

        # Revoke the token
        token_record = db_session.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        token_record.revoked_at = datetime.datetime.now(datetime.timezone.utc)
        db_session.commit()

        # Try to refresh
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v2/auth/refresh", json=refresh_data)

        # Assert error response
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "刷新令牌已失效，请重新登录"

    @pytest.mark.integration
    def test_refresh_with_invalid_token_fails(self, client: TestClient):
        """
        Test refresh with invalid token fails.

        Given: A malformed or invalid refresh token
        When: POST /api/v2/auth/refresh is called
        Then: 401 error is returned
        """
        refresh_data = {"refresh_token": "invalid-token-12345"}

        response = client.post("/api/v2/auth/refresh", json=refresh_data)

        # Assert error response
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "无效的刷新令牌"

    @pytest.mark.integration
    def test_refresh_with_access_token_fails(self, client: TestClient, registered_user: dict):
        """
        Test refresh with access token fails (wrong token type).

        Given: An access token instead of refresh token
        When: POST /api/v2/auth/refresh is called
        Then: 401 error is returned
        """
        access_token = registered_user["access_token"]
        refresh_data = {"refresh_token": access_token}

        response = client.post("/api/v2/auth/refresh", json=refresh_data)

        # Assert error response
        assert response.status_code == 401


# ==============================================================================
# Logout Flow Tests
# ==============================================================================

class TestLogoutFlow:
    """Test user logout flow."""

    @pytest.mark.integration
    def test_logout_success(self, client: TestClient, registered_user: dict, db_session: Session):
        """
        Test successful logout.

        Given: A valid refresh token from active session
        When: POST /api/v2/auth/logout is called
        Then: Refresh token is revoked
        """
        refresh_token = registered_user["refresh_token"]
        logout_data = {"refresh_token": refresh_token}

        response = client.post("/api/v2/auth/logout", json=logout_data)

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "退出登录成功"

        # Assert token is revoked in database
        token_record = db_session.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        assert token_record.revoked_at is not None

    @pytest.mark.integration
    def test_logout_idempotent(self, client: TestClient, registered_user: dict):
        """
        Test logout is idempotent.

        Given: A refresh token that was already revoked
        When: POST /api/v2/auth/logout is called again
        Then: Still returns success (idempotent operation)
        """
        refresh_token = registered_user["refresh_token"]

        # First logout
        logout_data = {"refresh_token": refresh_token}
        response1 = client.post("/api/v2/auth/logout", json=logout_data)
        assert response1.status_code == 200

        # Second logout with same token
        response2 = client.post("/api/v2/auth/logout", json=logout_data)
        assert response2.status_code == 200


# ==============================================================================
# End-to-End Flow Tests
# ==============================================================================

class TestAuthEndToEnd:
    """Test complete authentication flows."""

    @pytest.mark.integration
    def test_complete_auth_flow(self, client: TestClient, faker):
        """
        Test complete authentication flow: register -> login -> refresh -> logout.

        Given: A new user
        When: Going through complete auth lifecycle
        Then: All steps complete successfully
        """
        # Step 1: Register
        register_data = {
            "phone": faker.phone_number(),
            "password": "abc12345",
            "nickname": faker.name()
        }
        register_response = client.post("/api/v2/auth/register", json=register_data)
        assert register_response.status_code == 201
        register_data_response = register_response.json()

        # Step 2: Login
        login_data = {
            "phone": register_data["phone"],
            "password": register_data["password"]
        }
        login_response = client.post("/api/v2/auth/login", json=login_data)
        assert login_response.status_code == 200
        login_data_response = login_response.json()

        # Step 3: Refresh token
        refresh_request = {"refresh_token": login_data_response["refresh_token"]}
        refresh_response = client.post("/api/v2/auth/refresh", json=refresh_request)
        assert refresh_response.status_code == 200

        # Step 4: Logout
        logout_response = client.post("/api/v2/auth/logout", json=refresh_request)
        assert logout_response.status_code == 200

        # Step 5: Try to refresh with revoked token (should fail)
        refresh_after_logout = client.post("/api/v2/auth/refresh", json=refresh_request)
        assert refresh_after_logout.status_code == 401

    @pytest.mark.integration
    def test_password_not_in_response(self, client: TestClient, valid_register_data: dict):
        """
        Test password hash is never exposed in API responses.

        Given: A user registration/login
        When: Checking API responses
        Then: Password hash is not included
        """
        # Check register response
        response = client.post("/api/v2/auth/register", json=valid_register_data)
        assert response.status_code == 201
        registered_user = response.json()
        assert "password_hash" not in registered_user["user"]
        assert "password" not in registered_user["user"]


# ==============================================================================
# Security Tests
# ==============================================================================

class TestAuthSecurity:
    """Test security aspects of authentication."""

    @pytest.mark.integration
    def test_password_hashing(self, client: TestClient, valid_register_data: dict, db_session: Session):
        """
        Test passwords are properly hashed before storage.

        Given: User registration with plain text password
        When: Checking database
        Then: Password is hashed (not plain text)
        """
        response = client.post("/api/v2/auth/register", json=valid_register_data)
        assert response.status_code == 201

        # Get user from database
        user = db_session.query(User).filter(
            User.phone == valid_register_data["phone"]
        ).first()

        # Assert password is hashed
        assert user.password_hash is not None
        assert user.password_hash != valid_register_data["password"]
        assert user.password_hash.startswith("$2b$")  # bcrypt prefix

    @pytest.mark.integration
    def test_sql_injection_prevention(self, client: TestClient):
        """
        Test SQL injection attempts are prevented.

        Given: Registration data with SQL injection patterns
        When: Attempting to register
        Then: Input validation prevents registration
        """
        # Phone format validation should catch this
        injection_attempts = [
            {"phone": "'; DROP TABLE users; --", "password": "abc12345"},
            {"phone": "1' OR '1'='1", "password": "abc12345"},
        ]

        for attempt in injection_attempts:
            response = client.post("/api/v2/auth/register", json=attempt)
            # Should fail validation (invalid phone format)
            assert response.status_code == 422
