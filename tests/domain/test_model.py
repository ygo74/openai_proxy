"""Tests for Model domain model."""
from typing import Dict, Any
from datetime import datetime, timezone
import pytest
from ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, LlmModelStatus
from ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider


class TestModel:
    """Test suite for Model domain model."""

    def test_create_model_with_required_fields(self):
        """Test model creation with all required fields."""
        # Arrange
        now = datetime.now(timezone.utc)

        # Act
        model = LlmModel(
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            status=LlmModelStatus.NEW,
            provider=LLMProvider.OPENAI,
            capabilities={"test": True},
            created=now,
            updated=now
        )

        # Assert
        assert model.url == "http://test.com"
        assert model.name == "Test Model"
        assert model.technical_name == "test_model"
        assert model.status == LlmModelStatus.NEW
        assert model.provider == LLMProvider.OPENAI
        assert model.capabilities == {"test": True}
        assert model.created == now
        assert model.updated == now
        assert model.groups == []

    def test_create_model_with_default_status(self):
        """Test model creation with default status."""
        # Arrange & Act
        now = datetime.now(timezone.utc)
        model = LlmModel(
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            provider=LLMProvider.OPENAI,
            created=now,
            updated=now
        )

        # Assert
        assert model.status == LlmModelStatus.NEW
        assert model.capabilities == {}

    def test_create_model_with_all_statuses(self):
        """Test model creation with different status values."""
        # Arrange
        now = datetime.now(timezone.utc)
        statuses = [LlmModelStatus.NEW, LlmModelStatus.APPROVED, LlmModelStatus.DEPRECATED, LlmModelStatus.RETIRED]

        for status in statuses:
            # Act
            model = LlmModel(
                url="http://test.com",
                name="Test Model",
                technical_name=f"test_model_{status.value}",
                provider=LLMProvider.OPENAI,
                status=status,
                created=now,
                updated=now
            )

            # Assert
            assert model.status == status

    def test_model_with_complex_capabilities(self):
        """Test model with complex capabilities configuration."""
        # Arrange
        now = datetime.now(timezone.utc)
        capabilities: Dict[str, Any] = {
            "max_tokens": 4096,
            "supports_streaming": True,
            "supports_functions": False,
            "rate_limits": {
                "requests_per_minute": 60,
                "tokens_per_minute": 40000
            }
        }

        # Act
        model = LlmModel(
            url="http://test.com",
            name="Test Model",
            technical_name="test_model",
            provider=LLMProvider.OPENAI,
            capabilities=capabilities,
            created=now,
            updated=now
        )

        # Assert
        assert model.capabilities["max_tokens"] == 4096
        assert model.capabilities["supports_streaming"] is True
        assert model.capabilities["rate_limits"]["requests_per_minute"] == 60