from datetime import datetime, timezone
from unittest.mock import MagicMock
from src.core.application.model_service import get_all_models, update_model_status
from src.core.models.domain import Model, ModelStatus
import pytest

def test_get_all_models():
    # Arrange
    mock_session = MagicMock()
    models = [
        Model(
            id=1,
            url="http://test1.com",
            name="model1",
            technical_name="test_model1",
            status=ModelStatus.NEW,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            capabilities={"foo": "bar"}
        ),
        Model(
            id=2,
            url="http://test2.com",
            name="model2",
            technical_name="test_model2",
            status=ModelStatus.APPROVED,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            capabilities={"baz": "qux"}
        )
    ]
    mock_session.query().all.return_value = models

    # Act
    result = get_all_models(mock_session)

    # Assert
    assert len(result) == 2
    assert result[0].id == 1
    assert result[1].id == 2
    assert result[0].status == ModelStatus.NEW
    assert result[1].status == ModelStatus.APPROVED

def test_update_model_status_success():
    # Arrange
    mock_session = MagicMock()
    model_id = 1
    now = datetime.now(timezone.utc)
    existing_model = Model(
        id=model_id,
        url="http://test.com",
        name="test-model",
        technical_name="test_model",
        status=ModelStatus.NEW,
        created=now,
        updated=now,
        capabilities={"foo": "bar"}
    )
    mock_session.query().filter().first.return_value = existing_model

    # Act
    result = update_model_status(mock_session, model_id, ModelStatus.APPROVED)

    # Assert
    assert result.id == model_id
    assert result.status == ModelStatus.APPROVED
    mock_session.commit.assert_called_once()

def test_update_model_status_not_found():
    # Arrange
    mock_session = MagicMock()
    model_id = 999
    mock_session.query().filter().first.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Model not found"):
        update_model_status(mock_session, model_id, ModelStatus.APPROVED)