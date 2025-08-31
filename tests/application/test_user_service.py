"""Tests for user service."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from typing import Any
from src.ygo74.fastapi_openai_rag.application.services.user_service import UserService
from src.ygo74.fastapi_openai_rag.domain.models.user import User, ApiKey
from src.ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
from src.ygo74.fastapi_openai_rag.domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from src.ygo74.fastapi_openai_rag.domain.exceptions.validation_error import ValidationError
from src.ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModelStatus


class MockUnitOfWork:
    """Mock Unit of Work for testing."""

    def __init__(self) -> None:
        self.session: Mock = Mock()
        self.committed: bool = False
        self.rolled_back: bool = False

    def __enter__(self) -> 'MockUnitOfWork':
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestUserService:
    """Tests for UserService."""

    @pytest.fixture
    def mock_uow(self) -> MockUnitOfWork:
        """Create a mock Unit of Work."""
        return MockUnitOfWork()

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Create a mock repository with all necessary methods."""
        repository = Mock()
        repository.get_by_username = Mock()
        repository.get_by_email = Mock()
        repository.get_by_id = Mock()
        repository.get_all = Mock()
        repository.add = Mock()
        repository.update = Mock()
        repository.remove = Mock()
        repository.find_by_api_key_hash = Mock()
        repository.get_active_users = Mock()
        return repository

    @pytest.fixture
    def mock_repository_factory(self, mock_repository: Mock) -> Mock:
        """Create a mock repository factory."""
        factory: Mock = Mock()
        factory.return_value = mock_repository
        return factory

    @pytest.fixture
    def mock_model_repository(self) -> Mock:
        """Mock model repository."""
        return Mock()

    @pytest.fixture
    def mock_group_repository(self) -> Mock:
        """Mock group repository."""
        return Mock()

    @pytest.fixture
    def service(
        self,
        mock_uow: MockUnitOfWork,
        mock_repository_factory: Mock,
        mock_model_repository: Mock,
        mock_group_repository: Mock,
    ) -> UserService:
        """Create a UserService instance with mocks."""
        return UserService(
            mock_uow,
            mock_repository_factory,
            model_repository_factory=lambda s: mock_model_repository,
            group_repository_factory=lambda s: mock_group_repository,
        )

    def test_add_or_update_user_create_success(self, service: UserService, mock_repository: Mock):
        """Test successful user creation."""
        # arrange
        username = "testuser"
        email = "test@example.com"
        groups = ["admin"]

        mock_repository.get_by_username.return_value = None
        mock_repository.get_by_email.return_value = None
        created_user = User(
            id="user-123",
            username=username,
            email=email,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            groups=groups
        )
        mock_repository.add.return_value = created_user

        # act
        status, result = service.add_or_update_user(
            username=username,
            email=email,
            groups=groups
        )

        # assert
        assert status == "created"
        assert result.username == username
        assert result.email == email
        assert result.groups == groups
        mock_repository.get_by_username.assert_called_once_with(username)
        mock_repository.get_by_email.assert_called_once_with(email)
        mock_repository.add.assert_called_once()

    def test_add_or_update_user_create_missing_username(self, service: UserService, mock_repository: Mock):
        """Test user creation without required username."""
        # arrange & act & assert
        with pytest.raises(ValidationError):
            service.add_or_update_user(email="test@example.com")

    def test_add_or_update_user_create_duplicate_username(self, service: UserService, mock_repository: Mock):
        """Test user creation with duplicate username."""
        # arrange
        username = "existing_user"
        existing_user = User(
            id="user-456",
            username=username,
            created_at=datetime.now(timezone.utc)
        )
        mock_repository.get_by_username.return_value = existing_user

        # act & assert
        with pytest.raises(EntityAlreadyExistsError):
            service.add_or_update_user(username=username)

    def test_add_or_update_user_update_success(self, service: UserService, mock_repository: Mock):
        """Test successful user update."""
        # arrange
        user_id = "user-123"
        new_email = "new@example.com"
        existing_user = User(
            id=user_id,
            username="testuser",
            email="old@example.com",
            created_at=datetime.now(timezone.utc),
            groups=["user"]
        )
        updated_user = User(
            id=user_id,
            username="testuser",
            email=new_email,
            created_at=existing_user.created_at,
            updated_at=datetime.now(timezone.utc),
            groups=["user"]
        )

        mock_repository.get_by_id.return_value = existing_user
        mock_repository.update.return_value = updated_user

        # act
        status, result = service.add_or_update_user(
            user_id=user_id,
            email=new_email
        )

        # assert
        assert status == "updated"
        assert result.email == new_email
        mock_repository.get_by_id.assert_called_once_with(user_id)
        mock_repository.update.assert_called_once()

    def test_add_or_update_user_update_not_found(self, service: UserService, mock_repository: Mock):
        """Test user update when user doesn't exist."""
        # arrange
        user_id = "non-existent"
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(EntityNotFoundError):
            service.add_or_update_user(user_id=user_id, username="test")

    def test_get_all_users_success(self, service: UserService, mock_repository: Mock):
        """Test successful retrieval of all users."""
        # arrange
        users = [
            User(id="1", username="user1", created_at=datetime.now(timezone.utc)),
            User(id="2", username="user2", created_at=datetime.now(timezone.utc))
        ]
        mock_repository.get_all.return_value = users

        # act
        result = service.get_all_users()

        # assert
        assert len(result) == 2
        assert result == users
        mock_repository.get_all.assert_called_once()

    def test_get_user_by_id_success(self, service: UserService, mock_repository: Mock):
        """Test successful user retrieval by ID."""
        # arrange
        user_id = "user-123"
        user = User(id=user_id, username="testuser", created_at=datetime.now(timezone.utc))
        mock_repository.get_by_id.return_value = user

        # act
        result = service.get_user_by_id(user_id)

        # assert
        assert result == user
        mock_repository.get_by_id.assert_called_once_with(user_id)

    def test_get_user_by_id_not_found(self, service: UserService, mock_repository: Mock):
        """Test user retrieval by ID when user doesn't exist."""
        # arrange
        user_id = "non-existent"
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(EntityNotFoundError):
            service.get_user_by_id(user_id)

    @patch('src.ygo74.fastapi_openai_rag.application.services.user_service.secrets.token_urlsafe')
    @patch('src.ygo74.fastapi_openai_rag.application.services.user_service.hashlib.sha256')
    def test_create_api_key_success(self, mock_sha256, mock_token, service: UserService, mock_repository: Mock):
        """Test successful API key creation."""
        # arrange
        user_id = "user-123"
        key_name = "Test Key"
        user = User(
            id=user_id,
            username="testuser",
            created_at=datetime.now(timezone.utc),
            api_keys=[]
        )

        mock_token.return_value = "random_token"
        mock_hash = Mock()
        mock_hash.hexdigest.return_value = "hashed_key"
        mock_sha256.return_value = mock_hash

        mock_repository.get_by_id.return_value = user
        mock_repository.update.return_value = user

        # act
        plain_key, api_key = service.create_api_key(user_id, name=key_name)

        # assert
        assert plain_key == "sk-random_token"
        assert api_key.name == key_name
        assert api_key.user_id == user_id
        assert api_key.key_hash == "hashed_key"
        assert api_key.is_active is True
        mock_repository.get_by_id.assert_called_once_with(user_id)
        mock_repository.update.assert_called_once()

    def test_create_api_key_user_not_found(self, service: UserService, mock_repository: Mock):
        """Test API key creation when user doesn't exist."""
        # arrange
        user_id = "non-existent"
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(EntityNotFoundError):
            service.create_api_key(user_id)

    def test_deactivate_user_success(self, service: UserService, mock_repository: Mock):
        """Test successful user deactivation."""
        # arrange
        user_id = "user-123"
        user = User(
            id=user_id,
            username="testuser",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        deactivated_user = User(
            id=user_id,
            username="testuser",
            is_active=False,
            created_at=user.created_at,
            updated_at=datetime.now(timezone.utc)
        )

        mock_repository.get_by_id.return_value = user
        mock_repository.update.return_value = deactivated_user

        # act
        result = service.deactivate_user(user_id)

        # assert
        assert result.is_active is False
        mock_repository.get_by_id.assert_called_once_with(user_id)
        mock_repository.update.assert_called_once()

    def test_delete_user_success(self, service: UserService, mock_repository: Mock):
        """Test successful user deletion."""
        # arrange
        user_id = "user-123"
        user = User(id=user_id, username="testuser", created_at=datetime.now(timezone.utc))
        mock_repository.get_by_id.return_value = user

        # act
        service.delete_user(user_id)

        # assert
        mock_repository.get_by_id.assert_called_once_with(user_id)
        mock_repository.remove.assert_called_once_with(user_id)

    def test_delete_user_not_found(self, service: UserService, mock_repository: Mock):
        """Test user deletion when user doesn't exist."""
        # arrange
        user_id = "non-existent"
        mock_repository.get_by_id.return_value = None

        # act & assert
        with pytest.raises(EntityNotFoundError):
            service.delete_user(user_id)

    def test_get_active_users_success(self, service: UserService, mock_repository: Mock):
        """Test successful retrieval of active users."""
        # arrange
        users = [
            User(id="1", username="user1", is_active=True, created_at=datetime.now(timezone.utc)),
            User(id="2", username="user2", is_active=True, created_at=datetime.now(timezone.utc))
        ]
        mock_repository.get_active_users.return_value = users

        # act
        result = service.get_active_users()

        # assert
        assert len(result) == 2
        assert all(user.is_active for user in result)
        mock_repository.get_active_users.assert_called_once()

    def test_unit_of_work_commit_on_success(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock):
        """Test that Unit of Work commits on successful operation."""
        # arrange
        service: UserService = UserService(mock_uow, mock_repository_factory)
        mock_repository: Mock = mock_repository_factory.return_value
        mock_repository.get_all.return_value = []

        # act
        service.get_all_users()

        # assert
        assert mock_uow.committed is True
        assert mock_uow.rolled_back is False

    def test_unit_of_work_rollback_on_exception(self, mock_uow: MockUnitOfWork, mock_repository_factory: Mock):
        """Test that Unit of Work rolls back on exception."""
        # arrange
        service: UserService = UserService(mock_uow, mock_repository_factory)
        mock_repository: Mock = mock_repository_factory.return_value
        mock_repository.get_all.side_effect = Exception("Database error")

        # act & assert
        with pytest.raises(Exception, match="Database error"):
            service.get_all_users()

        assert mock_uow.rolled_back is True
        assert mock_uow.committed is False

    def test_get_models_for_user_admin_returns_only_approved(
        self,
        service: UserService,
        mock_model_repository: Mock,
        mock_group_repository: Mock,
    ):
        """Admin user receives all approved models."""
        # arrange
        m1 = Mock(id="m1", status=LlmModelStatus.APPROVED)
        m2 = Mock(id="m2", status=LlmModelStatus.PENDING)
        m3 = Mock(id="m3", status=LlmModelStatus.APPROVED)
        mock_model_repository.get_all.return_value = [m1, m2, m3]

        # act
        result = service.get_models_for_user(["admin"])

        # assert
        assert {m.id for m in result} == {"m1", "m3"}
        mock_model_repository.get_all.assert_called_once()
        mock_group_repository.get_by_name.assert_not_called()

    def test_get_models_for_user_regular_user_dedup_and_filter_approved(
        self,
        service: UserService,
        mock_model_repository: Mock,
        mock_group_repository: Mock,
    ):
        """Regular user gets union of approved models from their groups, deduplicated."""
        # arrange
        mock_group_repository.get_by_name.side_effect = [
            Mock(id=1, name="g1"),
            Mock(id=2, name="g2"),
        ]
        g1_models = [Mock(id="m1", status=LlmModelStatus.APPROVED), Mock(id="m2", status=LlmModelStatus.PENDING)]
        g2_models = [Mock(id="m1", status=LlmModelStatus.APPROVED), Mock(id="m3", status=LlmModelStatus.APPROVED)]
        mock_model_repository.get_by_group_id.side_effect = [g1_models, g2_models]

        # act
        result = service.get_models_for_user(["g1", "g2"])

        # assert
        assert {m.id for m in result} == {"m1", "m3"}
        assert mock_model_repository.get_by_group_id.call_count == 2
        mock_group_repository.get_by_name.assert_any_call("g1")
        mock_group_repository.get_by_name.assert_any_call("g2")
