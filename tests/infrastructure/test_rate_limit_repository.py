"""Tests for rate limit repository."""
import sys
import os
from datetime import datetime, timezone, time
from unittest.mock import Mock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.domain.models.rate_limit import RateLimit, RateLimitWindow
from ygo74.fastapi_openai_rag.infrastructure.db.models.rate_limit_orm import (
    RateLimitORM,
    RateLimitWindowORM,
    ScopeTypeEnum
)
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.rate_limit_repository import SQLRateLimitRepository
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.rate_limit_mapper import RateLimitMapper


class TestSQLRateLimitRepository:
    """Test suite for SQLRateLimitRepository class."""

    def setup_method(self):
        """Set up test dependencies."""
        self.mock_session = Mock()
        self.repository = SQLRateLimitRepository(self.mock_session)

    def test_repository_initialization(self):
        """Test repository initialization."""
        # act
        repository = SQLRateLimitRepository(self.mock_session)

        # assert
        assert repository._session == self.mock_session
        assert repository._orm_class == RateLimitORM
        assert repository._mapper == RateLimitMapper

    def test_get_by_scope_global_found(self):
        """Test getting global rate limit when it exists."""
        # arrange
        window_orm = RateLimitWindowORM(
            id=1,
            rate_limit_id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=500000
        )

        rate_limit_orm = RateLimitORM(
            id=1,
            scope_type=ScopeTypeEnum.GLOBAL,
            scope_id=None,
            enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            windows=[window_orm]
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = rate_limit_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_scope("global", None)

        # assert
        assert result is not None
        assert result.scope_type == "global"
        assert result.scope_id is None
        assert len(result.windows) == 1
        assert result.windows[0].max_requests == 1000
        self.mock_session.execute.assert_called_once()

    def test_get_by_scope_model_found(self):
        """Test getting model-level rate limit when it exists."""
        # arrange
        window_orm = RateLimitWindowORM(
            id=1,
            rate_limit_id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=500,
            max_tokens=250000
        )

        rate_limit_orm = RateLimitORM(
            id=1,
            scope_type=ScopeTypeEnum.MODEL,
            scope_id="gpt-4",
            enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            windows=[window_orm]
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = rate_limit_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_scope("model", "gpt-4")

        # assert
        assert result is not None
        assert result.scope_type == "model"
        assert result.scope_id == "gpt-4"
        self.mock_session.execute.assert_called_once()

    def test_get_by_scope_group_model_found(self):
        """Test getting group/model rate limit when it exists."""
        # arrange
        window_orm = RateLimitWindowORM(
            id=1,
            rate_limit_id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=100,
            max_tokens=50000
        )

        rate_limit_orm = RateLimitORM(
            id=1,
            scope_type=ScopeTypeEnum.GROUP_MODEL,
            scope_id="finance:gpt-4",
            enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            windows=[window_orm]
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = rate_limit_orm
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_scope("group_model", "finance:gpt-4")

        # assert
        assert result is not None
        assert result.scope_type == "group_model"
        assert result.scope_id == "finance:gpt-4"
        self.mock_session.execute.assert_called_once()

    def test_get_by_scope_not_found(self):
        """Test getting rate limit when it doesn't exist."""
        # arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_by_scope("model", "non-existent")

        # assert
        assert result is None
        self.mock_session.execute.assert_called_once()

    def test_get_by_scope_invalid_scope_type(self):
        """Test getting rate limit with invalid scope type."""
        # act
        result = self.repository.get_by_scope("invalid_scope", None)

        # assert
        assert result is None

    def test_get_all_by_scope_type_global(self):
        """Test getting all global rate limits."""
        # arrange
        rate_limit_orm = RateLimitORM(
            id=1,
            scope_type=ScopeTypeEnum.GLOBAL,
            scope_id=None,
            enabled=False,  # Must be False if no windows
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            windows=[]
        )

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [rate_limit_orm]
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_all_by_scope_type("global")

        # assert
        assert len(result) == 1
        assert result[0].scope_type == "global"
        self.mock_session.execute.assert_called_once()

    def test_get_all_by_scope_type_multiple(self):
        """Test getting all model-level rate limits."""
        # arrange
        rate_limit_orms = [
            RateLimitORM(
                id=1,
                scope_type=ScopeTypeEnum.MODEL,
                scope_id="gpt-4",
                enabled=False,  # Must be False if no windows
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                windows=[]
            ),
            RateLimitORM(
                id=2,
                scope_type=ScopeTypeEnum.MODEL,
                scope_id="gpt-3.5-turbo",
                enabled=False,  # Must be False if no windows
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                windows=[]
            )
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = rate_limit_orms
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_all_by_scope_type("model")

        # assert
        assert len(result) == 2
        assert result[0].scope_id == "gpt-4"
        assert result[1].scope_id == "gpt-3.5-turbo"
        self.mock_session.execute.assert_called_once()

    def test_get_all_by_scope_type_invalid(self):
        """Test getting all rate limits with invalid scope type."""
        # act
        result = self.repository.get_all_by_scope_type("invalid")

        # assert
        assert result == []

    def test_get_enabled_only(self):
        """Test getting only enabled rate limits."""
        # arrange
        window_orm1 = RateLimitWindowORM(
            id=1,
            rate_limit_id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=0
        )
        window_orm2 = RateLimitWindowORM(
            id=2,
            rate_limit_id=2,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=500,
            max_tokens=0
        )
        rate_limit_orms = [
            RateLimitORM(
                id=1,
                scope_type=ScopeTypeEnum.GLOBAL,
                scope_id=None,
                enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                windows=[window_orm1]
            ),
            RateLimitORM(
                id=2,
                scope_type=ScopeTypeEnum.MODEL,
                scope_id="gpt-4",
                enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                windows=[window_orm2]
            )
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = rate_limit_orms
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_enabled_only()

        # assert
        assert len(result) == 2
        assert all(r.enabled for r in result)
        self.mock_session.execute.assert_called_once()

    def test_delete_by_scope_found(self):
        """Test deleting rate limit by scope when it exists."""
        # arrange
        window_orm = RateLimitWindowORM(
            id=1,
            rate_limit_id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=500,
            max_tokens=0
        )
        rate_limit_orm = RateLimitORM(
            id=1,
            scope_type=ScopeTypeEnum.MODEL,
            scope_id="gpt-4",
            enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            windows=[window_orm]
        )

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = rate_limit_orm
        self.mock_session.execute.return_value = mock_result
        self.mock_session.get.return_value = rate_limit_orm

        # act
        result = self.repository.delete_by_scope("model", "gpt-4")

        # assert
        assert result is True
        self.mock_session.delete.assert_called_once()

    def test_delete_by_scope_not_found(self):
        """Test deleting rate limit by scope when it doesn't exist."""
        # arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.delete_by_scope("model", "non-existent")

        # assert
        assert result is False
        self.mock_session.delete.assert_not_called()

    def test_get_all(self):
        """Test getting all rate limit configurations."""
        # arrange
        window_orm = RateLimitWindowORM(
            id=1,
            rate_limit_id=1,
            from_time=time(0, 0, 0),
            to_time=time(23, 59, 59),
            max_requests=1000,
            max_tokens=0
        )
        rate_limit_orms = [
            RateLimitORM(
                id=1,
                scope_type=ScopeTypeEnum.GLOBAL,
                scope_id=None,
                enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                windows=[window_orm]
            ),
            RateLimitORM(
                id=2,
                scope_type=ScopeTypeEnum.MODEL,
                scope_id="gpt-4",
                enabled=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                windows=[]
            )
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = rate_limit_orms
        self.mock_session.execute.return_value = mock_result

        # act
        result = self.repository.get_all()

        # assert
        assert len(result) == 2
        assert result[0].scope_type == "global"
        assert result[1].scope_type == "model"
        self.mock_session.execute.assert_called_once()
