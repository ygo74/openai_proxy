from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import NoResultFound
from src.infrastructure.model_crud import ModelRepository
from src.core.models.domain import Model, ModelStatus
from src.infrastructure.db.models.model_orm import ModelORM

class TestModelRepository:
    """Test suite for ModelRepository class"""

    @pytest.fixture
    def repository(self, session):
        """Create a ModelRepository instance with mock session"""
        return ModelRepository(session)

    def test_create_model_success(self, repository, session):
        """Test successful model creation"""
        # Arrange
        url = "http://test.com"
        name = "Test Model"
        technical_name = "test_model"
        capabilities = {"feature": "test"}

        # Act
        model = repository.create(
            url=url,
            name=name,
            technical_name=technical_name,
            capabilities=capabilities
        )

        # Assert
        assert session.committed
        assert len(session.added_items) == 1
        assert isinstance(session.added_items[0], ModelORM)
        assert model.url == url
        assert model.name == name
        assert model.technical_name == technical_name
        assert model.capabilities == capabilities
        assert model.status == ModelStatus.NEW
        assert isinstance(model.created, datetime)
        assert isinstance(model.updated, datetime)

    def test_get_model_by_id_exists(self, repository, session):
        """Test retrieving an existing model by ID"""
        # Arrange
        model_orm = ModelORM(
            id=1,
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            status=ModelStatus.NEW,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            capabilities={"feature": "test"}
        )
        session.set_query_result([model_orm])

        # Act
        result = repository.get_by_id(1)

        # Assert
        assert result is not None
        assert result.url == model_orm.url
        assert result.name == model_orm.name
        assert result.technical_name == model_orm.technical_name

    def test_get_model_by_id_not_exists(self, repository, session):
        """Test retrieving a non-existing model by ID"""
        # Arrange
        session.set_query_result([])

        # Act
        result = repository.get_by_id(999)

        # Assert
        assert result is None

    def test_get_model_by_technical_name_exists(self, repository, session):
        """Test retrieving an existing model by technical name"""
        # Arrange
        model_orm = ModelORM(
            id=1,
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            status=ModelStatus.NEW,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            capabilities={"feature": "test"}
        )
        session.set_query_result([model_orm])

        # Act
        result = repository.get_by_technical_name("test_model")

        # Assert
        assert result is not None
        assert result.technical_name == "test_model"

    def test_get_model_by_technical_name_not_exists(self, repository, session):
        """Test retrieving a non-existing model by technical name"""
        # Arrange
        session.set_query_result([])

        # Act
        result = repository.get_by_technical_name("nonexistent")

        # Assert
        assert result is None

    def test_get_all_models(self, repository, session):
        """Test retrieving all models"""
        # Arrange
        models = [
            ModelORM(
                id=1,
                url="http://test1.com",
                name="Model 1",
                technical_name="model_1",
                status=ModelStatus.NEW,
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
                capabilities={"feature": "test1"}
            ),
            ModelORM(
                id=2,
                url="http://test2.com",
                name="Model 2",
                technical_name="model_2",
                status=ModelStatus.APPROVED,
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc),
                capabilities={"feature": "test2"}
            )
        ]
        session.set_query_result(models)

        # Act
        result = repository.get_all()

        # Assert
        assert len(result) == 2
        assert all(isinstance(m, Model) for m in result)
        assert result[0].name == "Model 1"
        assert result[1].name == "Model 2"
        assert result[0].status == ModelStatus.NEW
        assert result[1].status == ModelStatus.APPROVED

    def test_update_model_success(self, repository, session):
        """Test successful model update"""
        # Arrange
        original_model = ModelORM(
            id=1,
            url="http://old.com",
            name="Old Name",
            technical_name="old_name",
            status=ModelStatus.NEW,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            capabilities={"old": "feature"}
        )
        session.set_query_result([original_model])

        updated_model = Model(
            url="http://new.com",
            name="New Name",
            technical_name="new_name",
            status=ModelStatus.APPROVED,
            created=original_model.created,
            updated=datetime.now(timezone.utc),
            capabilities={"new": "feature"}
        )

        # Act
        result = repository.update(1, updated_model)

        # Assert
        assert session.committed
        assert result.url == "http://new.com"
        assert result.name == "New Name"
        assert result.technical_name == "new_name"
        assert result.status == ModelStatus.APPROVED
        assert result.capabilities == {"new": "feature"}

    def test_update_model_not_found(self, repository, session):
        """Test updating a non-existing model"""
        # Arrange
        session.set_query_result([])
        updated_model = Model(
            url="http://new.com",
            name="New Name",
            technical_name="new_name",
            status=ModelStatus.APPROVED,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            capabilities={}
        )

        # Act & Assert
        with pytest.raises(NoResultFound):
            repository.update(999, updated_model)

    def test_delete_model_success(self, repository, session):
        """Test successful model deletion"""
        # Arrange
        session.set_deleted(True)

        # Act
        repository.delete(1)

        # Assert
        assert session.committed

    def test_delete_model_not_found(self, repository, session):
        """Test deleting a non-existing model"""
        # Arrange
        session.set_deleted(False)

        # Act & Assert
        with pytest.raises(NoResultFound):
            repository.delete(999)