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
        expected_model: ModelORM = ModelORM(
            id=1,
            url="http://test.com",
            name="Test Model",
            technical_name=technical_name,
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([expected_model])

        # act
        result: Optional[LlmModel] = repository.get_by_technical_name(technical_name)

        # assert
        assert result is not None
        assert result.technical_name == technical_name

    def test_get_by_technical_name_not_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting model by technical name when it doesn't exist."""
        # arrange
        technical_name: str = "non_existent"
        session.set_query_result([])

        # act
        result: Optional[LlmModel] = repository.get_by_technical_name(technical_name)

        # assert
        assert result is None

    def test_get_by_group_id_with_models(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting models by group ID when models exist."""
        # arrange
        group_id: int = 1
        models: List[ModelORM] = [
            ModelORM(
                id=1,
                url="http://test1.com",
                name="Model 1",
                technical_name="model_1",
                status=LlmModelStatus.NEW,
                capabilities={},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            ModelORM(
                id=2,
                url="http://test2.com",
                name="Model 2",
                technical_name="model_2",
                status=LlmModelStatus.APPROVED,
                capabilities={},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]

        # Mock the execute result
        mock_result: MagicMock = MagicMock()
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
        mock_result: MagicMock = MagicMock()
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
        expected_model: ModelORM = ModelORM(
            id=model_id,
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([expected_model])

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
        session.set_query_result([])

        # act
        result: Optional[LlmModel] = repository.get_by_id(model_id)

        # assert
        assert result is None

    def test_get_all_models(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test getting all models."""
        # arrange
        models: List[ModelORM] = [
            ModelORM(
                id=1,
                url="http://test1.com",
                name="Model 1",
                technical_name="model_1",
                status=LlmModelStatus.NEW,
                capabilities={},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            ),
            ModelORM(
                id=2,
                url="http://test2.com",
                name="Model 2",
                technical_name="model_2",
                status=LlmModelStatus.APPROVED,
                capabilities={},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
        ]
        session.set_query_result(models)

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
            updated=datetime.now(timezone.utc)
        )

        # act
        result: LlmModel = repository.add(model)

        # assert
        assert len(session.added_items) == 1
        assert result.url == model.url
        assert result.name == model.name
        assert result.technical_name == model.technical_name

    def test_update_model_found(self, repository: SQLModelRepository,session: MockSession) -> None:
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
            updated=datetime.now(timezone.utc)
        )
        existing_orm: ModelORM = ModelORM(
            id=1,
            url="http://original.com",
            name="Original Model",
            technical_name="original_model",
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([existing_orm])

        # act
        result: LlmModel = repository.update(updated_model)

        # assert
        assert result.name == "Updated Model"
        assert result.technical_name == "updated_model"
        assert result.status == LlmModelStatus.APPROVED

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
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([])

        # act & assert
        with pytest.raises(ValueError, match="Entity with id 999 not found"):
            repository.update(updated_model)

    def test_remove_model_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test removing existing model."""
        # arrange
        model_id: int = 1
        existing_orm: ModelORM = ModelORM(
            id=model_id,
            url="http://test.com",
            name="Model to Delete",
            technical_name="model_to_delete",
            status=LlmModelStatus.NEW,
            capabilities={},
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )
        session.set_query_result([existing_orm])

        # act
        repository.remove(model_id)

        # assert
        assert session.deleted is True

    def test_remove_model_not_found(self, repository: SQLModelRepository, session: MockSession) -> None:
        """Test removing model that doesn't exist."""
        # arrange
        model_id: int = 999
        session.set_query_result([])

        # act & assert
        with pytest.raises(ValueError, match="Entity with id 999 not found"):
            repository.remove(model_id)