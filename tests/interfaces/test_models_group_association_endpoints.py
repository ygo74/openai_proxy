"""Tests for model-group association endpoints."""
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from fastapi import status

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.group import Group
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ygo74.fastapi_openai_rag.main import app

client = TestClient(app)


def create_test_model() -> LlmModel:
    """Create a test model."""
    return LlmModel(
        id=1,
        url="http://test.com",
        name="Test Model",
        technical_name="test_model",
        provider=LLMProvider.OPENAI,
        status=LlmModelStatus.NEW,
        capabilities={},
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        groups=[]
    )


def create_test_group() -> Group:
    """Create a test group."""
    return Group(
        id=1,
        name="Test Group",
        description="Test Description",
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        models=[]
    )


@pytest.fixture
def mock_auth():
    """Mock the authentication dependency."""
    with patch("ygo74.fastapi_openai_rag.interfaces.api.decorators.require_oauth_role") as mock:
        # Configure the decorator to just call the decorated function
        mock.return_value = lambda func: func
        yield mock


@pytest.fixture
def mock_model_service():
    """Mock the model service."""
    with patch("ygo74.fastapi_openai_rag.interfaces.api.endpoints.models.ModelService") as mock:
        yield mock


def test_add_group_to_model_success(mock_auth, mock_model_service):
    """Test adding a group to a model successfully."""
    # arrange
    model_id = 1
    group_id = 2
    model = create_test_model()
    group = create_test_group()
    group.id = group_id
    model.groups = [group]

    # Configure mock
    service_instance = mock_model_service.return_value
    service_instance.add_model_to_group.return_value = model

    # act
    response = client.post(f"/v1/models/{model_id}/groups/{group_id}")

    # assert
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == model_id
    assert len(data["groups"]) == 1
    assert data["groups"][0] == group.name
    service_instance.add_model_to_group.assert_called_once_with(model_id, group_id)


def test_add_group_to_model_not_found(mock_auth, mock_model_service):
    """Test adding a group to a model when not found."""
    # arrange
    model_id = 1
    group_id = 2

    # Configure mock
    service_instance = mock_model_service.return_value
    service_instance.add_model_to_group.side_effect = EntityNotFoundError("Model", str(model_id))

    # act
    response = client.post(f"/v1/models/{model_id}/groups/{group_id}")

    # assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    service_instance.add_model_to_group.assert_called_once_with(model_id, group_id)


def test_remove_group_from_model_success(mock_auth, mock_model_service):
    """Test removing a group from a model successfully."""
    # arrange
    model_id = 1
    group_id = 2
    model = create_test_model()

    # Configure mock
    service_instance = mock_model_service.return_value
    service_instance.remove_model_from_group.return_value = model

    # act
    response = client.delete(f"/v1/models/{model_id}/groups/{group_id}")

    # assert
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == model_id
    assert len(data["groups"]) == 0
    service_instance.remove_model_from_group.assert_called_once_with(model_id, group_id)


def test_remove_group_from_model_not_found(mock_auth, mock_model_service):
    """Test removing a group from a model when not found."""
    # arrange
    model_id = 1
    group_id = 2

    # Configure mock
    service_instance = mock_model_service.return_value
    service_instance.remove_model_from_group.side_effect = EntityNotFoundError("Model", str(model_id))

    # act
    response = client.delete(f"/v1/models/{model_id}/groups/{group_id}")

    # assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    service_instance.remove_model_from_group.assert_called_once_with(model_id, group_id)


def test_get_groups_for_model_success(mock_auth, mock_model_service):
    """Test getting groups for model successfully."""
    # arrange
    model_id = 1
    groups = [
        Group(
            id=1,
            name="Group 1",
            description="Description 1",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            models=[]
        ),
        Group(
            id=2,
            name="Group 2",
            description="Description 2",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc),
            models=[]
        )
    ]

    # Configure mock
    service_instance = mock_model_service.return_value
    service_instance.get_groups_for_model.return_value = groups

    # act
    response = client.get(f"/v1/models/{model_id}/groups")

    # assert
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert "Group 1" in data
    assert "Group 2" in data
    service_instance.get_groups_for_model.assert_called_once_with(model_id)


def test_get_groups_for_model_not_found(mock_auth, mock_model_service):
    """Test getting groups for model when model not found."""
    # arrange
    model_id = 1

    # Configure mock
    service_instance = mock_model_service.return_value
    service_instance.get_groups_for_model.side_effect = EntityNotFoundError("Model", str(model_id))

    # act
    response = client.get(f"/v1/models/{model_id}/groups")

    # assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    service_instance.get_groups_for_model.assert_called_once_with(model_id)
