"""Tests for user repository."""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone
from src.ygo74.fastapi_openai_rag.infrastructure.db.repositories.user_repository import UserRepository
from src.ygo74.fastapi_openai_rag.infrastructure.db.models.user_orm import UserORM, ApiKeyORM
from src.ygo74.fastapi_openai_rag.domain.models.user import User, ApiKey

class TestUserRepository:
    """Tests for UserRepository."""

    def setup_method(self):
        """Set up test dependencies."""
        self.mock_session = Mock()
        self.repository = UserRepository(self.mock_session)

    def test_get_by_id_success(self):
        """Test successful user retrieval by ID."""
        # arrange
        user_id = "user-123"
        user_orm = UserORM(
            id=user_id,
            username="testuser",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            groups='["admin"]',
            api_keys=[],
            is_active=True
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = user_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_id(user_id)

        # assert
        assert result is not None
        assert result.id == user_id
        assert result.username == "testuser"
        self.mock_session.execute.assert_called_once()

    def test_get_by_id_not_found(self):
        """Test user retrieval by ID when user doesn't exist."""
        # arrange
        user_id = "non-existent"
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_id(user_id)

        # assert
        assert result is None
        self.mock_session.execute.assert_called_once()

    def test_get_by_username_success(self):
        """Test successful user retrieval by username."""
        # arrange
        username = "testuser"
        user_orm = UserORM(
            id="user-123",
            username=username,
            email="test@example.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            groups='[]',
            api_keys=[]
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = user_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_username(username)

        # assert
        assert result is not None
        assert result.username == username
        self.mock_session.execute.assert_called_once()

    def test_find_by_api_key_hash_success(self):
        """Test successful user retrieval by API key hash."""
        # arrange
        key_hash = "hashed-key"
        api_key_orm = ApiKeyORM(
            id="key-123",
            key_hash=key_hash,
            user_id="user-123",
            is_active=True,
            expires_at=None,
            created_at=datetime.now(timezone.utc)
        )
        user_orm = UserORM(
            id="user-123",
            username="testuser",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            groups='[]',
            api_keys=[api_key_orm]
        )
        api_key_orm.user = user_orm

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = api_key_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.find_by_api_key_hash(key_hash)

        # assert
        assert result is not None
        assert result.username == "testuser"
        self.mock_session.execute.assert_called_once()
        self.mock_session.flush.assert_called_once()  # For updating last_used_at

    def test_find_by_api_key_hash_not_found(self):
        """Test user retrieval by API key hash when key doesn't exist."""
        # arrange
        key_hash = "non-existent-hash"
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.find_by_api_key_hash(key_hash)

        # assert
        assert result is None
        self.mock_session.execute.assert_called_once()

    def test_add_user_success(self):
        """Test successful user addition."""
        # arrange
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            groups=["admin"]
        )

        # act
        result = self.repository.add(user)

        # assert
        assert result.username == "testuser"
        self.mock_session.add.assert_called_once()
        self.mock_session.flush.assert_called_once()
        self.mock_session.refresh.assert_called_once()

    def test_update_user_success(self):
        """Test successful user update."""
        # arrange
        user = User(
            id="user-123",
            username="testuser",
            email="new@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        updated_orm = UserORM(
            id="user-123",
            username="testuser",
            email="new@example.com",
            created_at=user.created_at,
            updated_at=user.updated_at,
            groups='[]',
            api_keys=[],
            is_active=True
        )
        self.mock_session.get.return_value = updated_orm

        # act
        result = self.repository.update(user)

        # assert
        assert result.email == "new@example.com"
        self.mock_session.merge.assert_called_once()
        self.mock_session.flush.assert_called_once()
        self.mock_session.get.assert_called_once()

    def test_remove_user_success(self):
        """Test successful user removal."""
        # arrange
        user_id = "user-123"
        user_orm = UserORM(id=user_id, username="testuser", created_at=datetime.now(timezone.utc))
        self.mock_session.get.return_value = user_orm

        # act
        self.repository.remove(user_id)

        # assert
        self.mock_session.get.assert_called_once_with(UserORM, user_id)
        self.mock_session.delete.assert_called_once_with(user_orm)
        self.mock_session.flush.assert_called_once()

    def test_get_active_users_success(self):
        """Test successful retrieval of active users."""
        # arrange
        user_orms = [
            UserORM(
                id="user-1",
                username="user1",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                groups='[]',
                api_keys=[]
            ),
            UserORM(
                id="user-2",
                username="user2",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                groups='[]',
                api_keys=[]
            )
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = user_orms
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_active_users()

        # assert
        assert len(result) == 2
        assert all(user.is_active for user in result)
        self.mock_session.execute.assert_called_once()
