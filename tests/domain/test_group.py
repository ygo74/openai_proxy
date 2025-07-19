"""Tests for Group domain model."""
from datetime import datetime, timezone
import pytest
from src.ygo74.fastapi_openai_rag.domain.models.group import Group


class TestGroup:
    """Test suite for Group domain model."""

    def test_create_group_with_required_fields(self):
        """Test group creation with all required fields."""
        # Arrange
        now = datetime.now(timezone.utc)

        # Act
        group = Group(
            name="Test Group",
            description="Test Description",
            created=now,
            updated=now
        )

        # Assert
        assert group.name == "Test Group"
        assert group.description == "Test Description"
        assert group.created == now
        assert group.updated == now
        assert group.models == []

    def test_create_group_without_description(self):
        """Test group creation without description."""
        # Arrange & Act
        now = datetime.now(timezone.utc)
        group = Group(
            name="Test Group",
            created=now,
            updated=now
        )

        # Assert
        assert group.name == "Test Group"
        assert group.description is None
        assert group.models == []

    def test_create_group_with_empty_description(self):
        """Test group creation with empty description."""
        # Arrange & Act
        now = datetime.now(timezone.utc)
        group = Group(
            name="Test Group",
            description="",
            created=now,
            updated=now
        )

        # Assert
        assert group.name == "Test Group"
        assert group.description == ""

    def test_create_group_with_long_description(self):
        """Test group creation with long description."""
        # Arrange
        now = datetime.now(timezone.utc)
        long_description = "This is a very long description " * 10

        # Act
        group = Group(
            name="Test Group",
            description=long_description,
            created=now,
            updated=now
        )

        # Assert
        assert group.name == "Test Group"
        assert group.description == long_description
        assert len(group.description) > 100

    def test_group_models_list_initialization(self):
        """Test that models list is properly initialized."""
        # Arrange & Act
        now = datetime.now(timezone.utc)
        group = Group(
            name="Test Group",
            created=now,
            updated=now
        )

        # Assert
        assert isinstance(group.models, list)
        assert len(group.models) == 0