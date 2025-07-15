from datetime import datetime, timezone
from src.core.models.domain import Model, Group, ModelStatus
from src.infrastructure.db.models.model_orm import ModelORM
from src.infrastructure.db.models.group_orm import GroupORM
from src.infrastructure.db.mappers.mappers import to_domain_model, to_orm_model, to_domain_group, to_orm_group

def test_model_to_domain():
    # Arrange
    now = datetime.now(timezone.utc)
    orm_model = ModelORM(
        id=1,
        url="http://test.com",
        name="test-model",
        technical_name="test_test-model",
        status=ModelStatus.NEW,
        created=now,
        updated=now,
        capabilities={"foo": "bar"}
    )

    # Act
    domain_model = to_domain_model(orm_model)

    # Assert
    assert domain_model.id == 1
    assert domain_model.url == "http://test.com"
    assert domain_model.name == "test-model"
    assert domain_model.technical_name == "test_test-model"
    assert domain_model.status == ModelStatus.NEW
    assert domain_model.capabilities == {"foo": "bar"}
    assert domain_model.created.replace(microsecond=0) == now.replace(microsecond=0)
    assert domain_model.updated.replace(microsecond=0) == now.replace(microsecond=0)

def test_model_to_orm():
    # Arrange
    now = datetime.now(timezone.utc)
    domain_model = Model(
        id=1,
        url="http://test.com",
        name="test-model",
        technical_name="test_test-model",
        status=ModelStatus.NEW,
        created=now,
        updated=now,
        capabilities={"foo": "bar"}
    )

    # Act
    orm_model = to_orm_model(domain_model)

    # Assert
    assert getattr(orm_model, 'id') == 1
    assert getattr(orm_model, 'url') == "http://test.com"
    assert getattr(orm_model, 'name') == "test-model"
    assert getattr(orm_model, 'technical_name') == "test_test-model"
    assert getattr(orm_model, 'status') == ModelStatus.NEW
    assert getattr(orm_model, 'capabilities') == {"foo": "bar"}
    assert getattr(orm_model, 'created').replace(microsecond=0) == now.replace(microsecond=0)
    assert getattr(orm_model, 'updated').replace(microsecond=0) == now.replace(microsecond=0)

def test_group_to_domain():
    # Arrange
    now = datetime.now(timezone.utc)
    orm_group = GroupORM(
        id=1,
        name="test-group",
        description="Test group",
        created=now,
        updated=now
    )

    # Act
    domain_group = to_domain_group(orm_group)

    # Assert
    assert domain_group.id == 1
    assert domain_group.name == "test-group"
    assert domain_group.description == "Test group"
    assert domain_group.created.replace(microsecond=0) == now.replace(microsecond=0)
    assert domain_group.updated.replace(microsecond=0) == now.replace(microsecond=0)

def test_group_to_orm():
    # Arrange
    now = datetime.now(timezone.utc)
    domain_group = Group(
        id=1,
        name="test-group",
        description="Test group",
        created=now,
        updated=now
    )

    # Act
    orm_group = to_orm_group(domain_group)

    # Assert
    assert getattr(orm_group, 'id') == 1
    assert getattr(orm_group, 'name') == "test-group"
    assert getattr(orm_group, 'description') == "Test group"
    assert getattr(orm_group, 'created').replace(microsecond=0) == now.replace(microsecond=0)
    assert getattr(orm_group, 'updated').replace(microsecond=0) == now.replace(microsecond=0)