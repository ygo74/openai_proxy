"""Tests for users endpoints add/remove groups."""
from datetime import datetime, timezone
from typing import Callable
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock

from src.ygo74.fastapi_openai_rag.interfaces.api.endpoints.users import router, get_user_service, require_admin_role
from src.ygo74.fastapi_openai_rag.domain.models.user import User
from src.ygo74.fastapi_openai_rag.domain.exceptions.entity_not_found_exception import EntityNotFoundError
from src.ygo74.fastapi_openai_rag.domain.models.autenticated_user import AuthenticatedUser

def build_app(mock_service: Mock) -> TestClient:
    """Create a FastAPI app that mounts the users router and overrides dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/users")

    # Override dependencies: bypass admin auth and inject mock service
    app.dependency_overrides[get_user_service] = lambda: mock_service
    app.dependency_overrides[require_admin_role] = lambda: AuthenticatedUser(sub="admin", username="admin")  # type: ignore

    return TestClient(app)

