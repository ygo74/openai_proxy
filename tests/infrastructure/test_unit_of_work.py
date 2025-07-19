"""Unit tests for Unit of Work implementation."""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.exc import SQLAlchemyError
from src.ygo74.fastapi_openai_rag.infrastructure.db.unit_of_work import SQLUnitOfWork


def test_sql_unit_of_work_enter_creates_session():
    # arrange
    mock_session = Mock()
    session_factory = Mock(return_value=mock_session)
    uow = SQLUnitOfWork(session_factory)

    # act
    result = uow.__enter__()

    # assert
    assert result is uow
    assert uow.session is mock_session
    session_factory.assert_called_once()


def test_sql_unit_of_work_exit_commits_on_success():
    # arrange
    mock_session = Mock()
    session_factory = Mock(return_value=mock_session)
    uow = SQLUnitOfWork(session_factory)
    uow.__enter__()

    # act
    uow.__exit__(None, None, None)

    # assert
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


def test_sql_unit_of_work_exit_rollback_on_exception():
    # arrange
    mock_session = Mock()
    session_factory = Mock(return_value=mock_session)
    uow = SQLUnitOfWork(session_factory)
    uow.__enter__()

    # act
    uow.__exit__(ValueError, ValueError("test"), None)

    # assert
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_sql_unit_of_work_commit_rollback_on_error():
    # arrange
    mock_session = Mock()
    mock_session.commit.side_effect = SQLAlchemyError("DB error")
    session_factory = Mock(return_value=mock_session)
    uow = SQLUnitOfWork(session_factory)
    uow.__enter__()

    # act & assert
    with pytest.raises(SQLAlchemyError):
        uow.commit()

    mock_session.rollback.assert_called_once()


def test_sql_unit_of_work_session_property_without_context():
    # arrange
    session_factory = Mock()
    uow = SQLUnitOfWork(session_factory)

    # act & assert
    with pytest.raises(RuntimeError, match="Session not initialized"):
        _ = uow.session


def test_sql_unit_of_work_context_manager_usage():
    # arrange
    mock_session = Mock()
    session_factory = Mock(return_value=mock_session)

    # act
    with SQLUnitOfWork(session_factory) as uow:
        session = uow.session

    # assert
    assert session is mock_session
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()
