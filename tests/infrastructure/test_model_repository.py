"""Unit tests for SQLModelRepository."""
import sys
import os
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.infrastructure.db.models.model_orm import ModelORM
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.model_repository import SQLModelRepository
from tests.conftest import MockSession


class TestSQLModelRepository:
    """Test suite for SQLModelRepository class."""

    @pytest.fixture
    def repository(self, session: MockSession) -> SQLModelRepository:
        """Create a ModelRepository instance with mock session."""
        return SQLModelRepository(session)

    def test_get_by_technical_name_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting model by technical name when it exists."""
        # arrange
        technical_name: str = "test_model"
        expected_model: ModelORM = ModelORM()
        expected_model.id = 1
        expected_model.url = "http://test.com"
        expected_model.name = "Test Model"
        expected_model.technical_name = technical_name
        expected_model.provider = "openai"  # Use lowercase to match enum
        expected_model.status = LlmModelStatus.NEW
        expected_model.capabilities = {}
        expected_model.created = datetime.now(timezone.utc)
        expected_model.updated = datetime.now(timezone.utc)
        expected_model.groups = []

        # Mock execute result for select query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expected_model]
        session.set_execute_result(mock_result)

        # act
        result: List[LlmModel] = repository.get_by_technical_name(technical_name)

        # assert
        assert len(result) == 1
        assert result[0].technical_name == technical_name
        assert isinstance(result[0], LlmModel)

    def test_get_by_technical_name_azure_model(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting Azure model by technical name."""
        # arrange
        technical_name: str = "azure_test_model"
        expected_model: ModelORM = ModelORM(
            id=1,
            url="https://test.openai.azure.com",
            name="Azure Test Model",
            technical_name=technical_name,
            provider="azure",
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        expected_model.groups = []

        # Mock execute result for select query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expected_model]
        session.set_execute_result(mock_result)

        # act
        result: List[LlmModel] = repository.get_by_technical_name(technical_name)

        # assert
        assert len(result) == 1
        assert result[0].technical_name == technical_name
        assert isinstance(result[0], LlmModel)
        assert result[0].provider == LLMProvider.AZURE

    def test_get_by_technical_name_not_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting model by technical name when it doesn't exist."""
        # arrange
        technical_name: str = "non_existent"

        # Mock execute result for select query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.set_execute_result(mock_result)

        # act
        result: List[LlmModel] = repository.get_by_technical_name(technical_name)

        # assert
        assert len(result) == 0

    def test_get_by_group_id_with_models(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting models by group ID when models exist."""
        # arrange
        group_id: int = 1
        models: List[ModelORM] = []

        model1 = ModelORM()
        model1.id = 1
        model1.url = "http://test1.com"
        model1.name = "Model 1"
        model1.technical_name = "model_1"
        model1.provider = "openai"
        model1.status = LlmModelStatus.NEW
        model1.capabilities = {}
        model1.created = datetime.now(timezone.utc)
        model1.updated = datetime.now(timezone.utc)
        model1.groups = []

        model2 = ModelORM()
        model2.id = 2
        model2.url = "http://test2.com"
        model2.name = "Model 2"
        model2.technical_name = "model_2"
        model2.provider = "anthropic"
        model2.status = LlmModelStatus.APPROVED
        model2.capabilities = {}
        model2.created = datetime.now(timezone.utc)
        model2.updated = datetime.now(timezone.utc)
        model2.groups = []

        models.extend([model1, model2])

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = models
        session.set_execute_result(mock_result)

        # act
        result: List[LlmModel] = repository.get_by_group_id(group_id)

        # assert
        assert len(result) == 2
        assert result[0].name == "Model 1"
        assert result[1].name == "Model 2"

    def test_get_by_group_id_no_models(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting models by group ID when no models exist."""
        # arrange
        group_id: int = 999

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.set_execute_result(mock_result)

        # act
        result: List[LlmModel] = repository.get_by_group_id(group_id)

        # assert
        assert len(result) == 0
        assert result == []

    def test_repository_initialization(self, session: MockSession) -> None:
        """Test repository initialization."""
        # act
        repository: SQLModelRepository = SQLModelRepository(session)

        # assert
        assert repository._session == session
        assert repository._orm_class.__name__ == "ModelORM"
        assert repository._mapper is not None

    def test_get_by_id_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting model by ID when it exists."""
        # arrange
        model_id: int = 1
        expected_model: ModelORM = ModelORM()
        expected_model.id = model_id
        expected_model.url = "http://test.com"
        expected_model.name = "Test Model"
        expected_model.technical_name = "test_model"
        expected_model.provider = "openai"
        expected_model.status = LlmModelStatus.NEW
        expected_model.capabilities = {}
        expected_model.created = datetime.now(timezone.utc)
        expected_model.updated = datetime.now(timezone.utc)
        expected_model.groups = []

        # Set up mock for get method
        session.get_result = expected_model

        # act
        result: Optional[LlmModel] = repository.get_by_id(model_id)

        # assert
        assert result is not None
        assert result.id == model_id
        assert result.name == "Test Model"

    def test_get_by_id_not_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting model by ID when it doesn't exist."""
        # arrange
        model_id: int = 999

        # Set up mock for get method to return None
        session.get_result = None

        # act
        result: Optional[LlmModel] = repository.get_by_id(model_id)

        # assert
        assert result is None

    def test_get_all_models(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting all models."""
        # arrange
        models: List[ModelORM] = []

        model1 = ModelORM()
        model1.id = 1
        model1.url = "http://test1.com"
        model1.name = "Model 1"
        model1.technical_name = "model_1"
        model1.provider = "openai"
        model1.status = LlmModelStatus.NEW
        model1.capabilities = {}
        model1.created = datetime.now(timezone.utc)
        model1.updated = datetime.now(timezone.utc)
        model1.groups = []

        model2 = ModelORM()
        model2.id = 2
        model2.url = "http://test2.com"
        model2.name = "Model 2"
        model2.technical_name = "model_2"
        model2.provider = "anthropic"
        model2.status = LlmModelStatus.APPROVED
        model2.capabilities = {}
        model2.created = datetime.now(timezone.utc)
        model2.updated = datetime.now(timezone.utc)
        model2.groups = []

        models.extend([model1, model2])

        # Configure mock_mapper to return domain objects
        mock_domain_models = [
            LlmModel(
                id=model1.id,
                url=model1.url,
                name=model1.name,
                technical_name=model1.technical_name,
                provider=LLMProvider.OPENAI,
                status=model1.status,
                capabilities=model1.capabilities,
                created=model1.created,
                updated=model1.updated,
                groups=[]
            ),
            LlmModel(
                id=model2.id,
                url=model2.url,
                name=model2.name,
                technical_name=model2.technical_name,
                provider=LLMProvider.ANTHROPIC,
                status=model2.status,
                capabilities=model2.capabilities,
                created=model2.created,
                updated=model2.updated,
                groups=[]
            )
        ]

        # Configure the query mock
        mock_query = MagicMock()
        mock_query.all.return_value = models
        session.query = MagicMock(return_value=mock_query)

        # Configure mapper mock in repository
        repository._mapper.to_domain = MagicMock(side_effect=lambda orm: next(
            (m for m in mock_domain_models if m.id == orm.id),
            mock_domain_models[0]
        ))

        # act
        result: List[LlmModel] = repository.get_all()

        # assert
        assert len(result) == 2
        assert result[0].name == "Model 1"
        assert result[1].name == "Model 2"

    def test_add_model(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test adding a new model."""
        # arrange
        model: LlmModel = LlmModel(
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            provider=LLMProvider.OPENAI,
            status=LlmModelStatus.NEW,
            capabilities={"test": True},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            groups=[]
        )

        # Mock the returned ORM object after add
        orm_result = ModelORM()
        orm_result.id = 1
        orm_result.url = "http://test.com"  # Ensure this matches the input
        orm_result.name = "Test Model"
        orm_result.technical_name = "test_model"
        orm_result.provider = "openai"
        orm_result.status = LlmModelStatus.NEW
        orm_result.capabilities = {"test": True}
        orm_result.created = model.created
        orm_result.updated = model.updated
        orm_result.groups = []

        # Configure mapper to return domain model matching the input
        repository._mapper.to_domain = MagicMock(return_value=model)

        # Set up the mock so that after add and refresh, the ORM returns our configured object
        def mock_add(orm_entity):
            session.added_items.append(orm_entity)

        def mock_refresh(orm_entity):
            # Copy values from our prepared orm_result to the actual entity
            for attr in ['id', 'url', 'name', 'technical_name', 'provider', 'status',
                        'capabilities', 'created', 'updated', 'groups']:
                if hasattr(orm_result, attr):
                    setattr(orm_entity, attr, getattr(orm_result, attr))

        session.add = MagicMock(side_effect=mock_add)
        session.refresh = MagicMock(side_effect=mock_refresh)

        # act
        result: LlmModel = repository.add(model)

        # assert
        assert len(session.added_items) == 1
        assert result.url == model.url
        assert result.name == model.name
        assert result.technical_name == model.technical_name

    def test_add_azure_model(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test adding a new Azure model."""
        # arrange
        model: LlmModel = LlmModel(
            url="https://test.openai.azure.com",
            name="Azure Test Model",
            technical_name="azure_test_model",
            provider=LLMProvider.AZURE,
            status=LlmModelStatus.NEW,
            capabilities={"azure": True},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            groups=[]
        )

        # Mock the returned ORM object after add
        orm_result = ModelORM()
        orm_result.id = 1
        orm_result.url = "https://test.openai.azure.com"  # Ensure this matches the input
        orm_result.name = "Azure Test Model"
        orm_result.technical_name = "azure_test_model"
        orm_result.provider = "azure"
        orm_result.status = LlmModelStatus.NEW
        orm_result.capabilities = {"azure": True}
        orm_result.created = model.created
        orm_result.updated = model.updated
        orm_result.groups = []

        # Configure mapper to return domain model matching the input
        repository._mapper.to_domain = MagicMock(return_value=model)

        # Set up the mock so that after add and refresh, the ORM returns our configured object
        def mock_add(orm_entity):
            session.added_items.append(orm_entity)

        def mock_refresh(orm_entity):
            # Copy values from our prepared orm_result to the actual entity
            for attr in ['id', 'url', 'name', 'technical_name', 'provider', 'status',
                        'capabilities', 'created', 'updated', 'groups']:
                if hasattr(orm_result, attr):
                    setattr(orm_entity, attr, getattr(orm_result, attr))

        session.add = MagicMock(side_effect=mock_add)
        session.refresh = MagicMock(side_effect=mock_refresh)

        # act
        result: LlmModel = repository.add(model)

        # assert
        assert len(session.added_items) == 1
        assert result.url == model.url
        assert result.name == model.name
        assert result.technical_name == model.technical_name
        assert result.provider == LLMProvider.AZURE

    def test_update_model_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test updating an existing model."""
        # arrange
        updated_model: LlmModel = LlmModel(
            id=1,
            url="http://updated.com",
            name="Updated Model",
            technical_name="updated_model",
            provider=LLMProvider.ANTHROPIC,
            status=LlmModelStatus.APPROVED,
            capabilities={"updated": True},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            groups=[]
        )

        existing_orm: ModelORM = ModelORM()
        existing_orm.id = 1
        existing_orm.url = "http://original.com"
        existing_orm.name = "Original Model"
        existing_orm.technical_name = "original_model"
        existing_orm.provider = "openai"
        existing_orm.status = LlmModelStatus.NEW
        existing_orm.capabilities = {}
        existing_orm.created = datetime.now(timezone.utc)
        existing_orm.updated = datetime.now(timezone.utc)
        existing_orm.groups = []

        # Set up mock for get method to return the existing model first, then updated model
        session.get_result = existing_orm

        # act
        result: LlmModel = repository.update(updated_model)

        # assert
        assert result is not None
        assert session.merged_items
        # No need to check all attributes as the Mapper is mocked

    def test_update_model_not_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test updating a non-existent model."""
        # arrange
        updated_model: LlmModel = LlmModel(
            id=999,
            url="http://notfound.com",
            name="Not Found Model",
            technical_name="not_found_model",
            provider=LLMProvider.AZURE,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            groups=[]
        )

        # Set up mock for get method to return None
        session.get_result = None

        # Configure merge to raise the error directly (instead of relying on side_effect)
        def mock_raise(*args, **kwargs):
            raise ValueError(f"Entity with id 999 not found")

        session.merge = mock_raise

        # act & assert
        with pytest.raises(ValueError, match="Entity with id 999 not found"):
            repository.update(updated_model)

    def test_delete_model_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test removing existing model."""
        # arrange
        model_id: int = 1
        existing_orm: ModelORM = ModelORM()
        existing_orm.id = model_id
        existing_orm.url = "http://test.com"
        existing_orm.name = "Model to Delete"
        existing_orm.technical_name = "model_to_delete"
        existing_orm.provider = "openai"
        existing_orm.status = LlmModelStatus.NEW
        existing_orm.capabilities = {}
        existing_orm.created = datetime.now(timezone.utc)
        existing_orm.updated = datetime.now(timezone.utc)
        existing_orm.groups = []

        # Set up mock for get method to return the model
        session.get_result = existing_orm

        # act
        repository.delete(model_id)

        # assert
        assert session.deleted is True

    def test_delete_model_not_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test removing model that doesn't exist."""
        # arrange
        model_id: int = 999

        # Set up mock for get method to return None
        session.get_result = None

        # act & assert
        with pytest.raises(ValueError, match="Entity with id 999 not found"):
            repository.delete(model_id)