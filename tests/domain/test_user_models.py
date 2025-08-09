"""Tests for user domain models."""
import pytest
from datetime import datetime, timezone
from src.ygo74.fastapi_openai_rag.domain.models.user import User, ApiKey

class TestApiKey:
    """Tests for ApiKey domain model."""

    def test_api_key_creation_with_required_fields(self):
        """Test ApiKey creation with required fields only."""
        # arrange
        api_key_id = "key-123"
        key_hash = "hashed-key"
        user_id = "user-456"
        created_at = datetime.now(timezone.utc)

        # act
        api_key = ApiKey(
            id=api_key_id,
            key_hash=key_hash,
            user_id=user_id,
            created_at=created_at
        )

        # assert
        assert api_key.id == api_key_id
        assert api_key.key_hash == key_hash
        assert api_key.user_id == user_id
        assert api_key.created_at == created_at
        assert api_key.name is None
        assert api_key.expires_at is None
        assert api_key.is_active is True
        assert api_key.last_used_at is None

    def test_api_key_creation_with_all_fields(self):
        """Test ApiKey creation with all fields."""
        # arrange
        api_key_id = "key-123"
        key_hash = "hashed-key"
        name = "Test Key"
        user_id = "user-456"
        created_at = datetime.now(timezone.utc)
        expires_at = datetime.now(timezone.utc)
        last_used_at = datetime.now(timezone.utc)

        # act
        api_key = ApiKey(
            id=api_key_id,
            key_hash=key_hash,
            name=name,
            user_id=user_id,
            created_at=created_at,
            expires_at=expires_at,
            is_active=False,
            last_used_at=last_used_at
        )

        # assert
        assert api_key.id == api_key_id
        assert api_key.key_hash == key_hash
        assert api_key.name == name
        assert api_key.user_id == user_id
        assert api_key.created_at == created_at
        assert api_key.expires_at == expires_at
        assert api_key.is_active is False
        assert api_key.last_used_at == last_used_at

class TestUser:
    """Tests for User domain model."""

    def test_user_creation_with_required_fields(self):
        """Test User creation with required fields only."""
        # arrange
        user_id = "user-123"
        username = "testuser"
        created_at = datetime.now(timezone.utc)

        # act
        user = User(
            id=user_id,
            username=username,
            created_at=created_at
        )

        # assert
        assert user.id == user_id
        assert user.username == username
        assert user.created_at == created_at
        assert user.email is None
        assert user.is_active is True
        assert user.updated_at is None
        assert user.groups == []
        assert user.api_keys == []

    def test_user_creation_with_all_fields(self):
        """Test User creation with all fields."""
        # arrange
        user_id = "user-123"
        username = "testuser"
        email = "test@example.com"
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)
        groups = ["admin", "users"]
        api_key = ApiKey(
            id="key-123",
            key_hash="hash",
            user_id=user_id,
            created_at=created_at
        )

        # act
        user = User(
            id=user_id,
            username=username,
            email=email,
            is_active=False,
            created_at=created_at,
            updated_at=updated_at,
            groups=groups,
            api_keys=[api_key]
        )

        # assert
        assert user.id == user_id
        assert user.username == username
        assert user.email == email
        assert user.is_active is False
        assert user.created_at == created_at
        assert user.updated_at == updated_at
        assert user.groups == groups
        assert len(user.api_keys) == 1
        assert user.api_keys[0] == api_key

    def test_user_model_validation(self):
        """Test User model validation."""
        # arrange & act & assert
        with pytest.raises(ValueError):
            User(
                id="user-123",
                username="",  # Empty username should fail
                created_at=datetime.now(timezone.utc)
            )

    def test_api_key_validation(self):
        """Test ApiKey model validation."""
        # arrange & act & assert
        with pytest.raises(ValueError):
            ApiKey(
                id="",  # Empty ID should fail
                key_hash="valid-hash",
                user_id="user-123",
                created_at=datetime.now(timezone.utc)
            )
