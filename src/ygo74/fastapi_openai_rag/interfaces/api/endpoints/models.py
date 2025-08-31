"""Model endpoints module."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging
from datetime import datetime

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.model_service import ModelService
from ....application.services.chat_completion_service import ChatCompletionService
from ....domain.models.llm_model import LlmModel, LlmModelStatus
from ....domain.models.configuration import AppConfig
from ....domain.models.llm import LLMProvider
from ..decorators.decorators import endpoint_handler
from ..security.auth import auth_jwt_or_api_key, require_admin_role
from ....domain.models.autenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

router = APIRouter()

class ModelResponse(BaseModel):
    """Model response schema."""
    id: Optional[int] = None
    url: str
    name: str
    technical_name: str
    provider: LLMProvider
    status: LlmModelStatus
    capabilities: Dict[str, Any] = {}
    groups: List[str]
    created: datetime  # Ajout du champ manquant
    updated: datetime  # Ajout du champ manquant

class ModelCreate(BaseModel):
    """Model creation schema."""
    url: str
    name: str
    technical_name: str
    provider: LLMProvider
    capabilities: Dict[str, Any] = {}

class ModelUpdate(BaseModel):
    """Model update schema."""
    url: Optional[str] = None
    name: Optional[str] = None
    technical_name: Optional[str] = None
    provider: LLMProvider
    capabilities: Optional[Dict[str, Any]] = {}

class UpdateModelStatusRequest(BaseModel):
    """Request schema for updating model status."""
    status: LlmModelStatus


def map_model_to_response(model: LlmModel) -> ModelResponse:
    """Map LlmModel to ModelResponse."""
    return ModelResponse(
        id=model.id,
        url=model.url,
        name=model.name,
        technical_name=model.technical_name,
        provider=model.provider,
        status=model.status,
        capabilities=model.capabilities,
        groups=[group.name for group in model.groups] if model.groups else [],
        created=model.created,
        updated=model.updated
    )

def map_model_list_to_response(models: List[LlmModel]) -> List[ModelResponse]:
    """Map list of LlmModel to list of ModelResponse."""
    return [map_model_to_response(model) for model in models]


def get_model_service(db: Session = Depends(get_db)) -> ModelService:
    """Create ModelService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return ModelService(uow)


def get_chat_completion_service(db: Session = Depends(get_db)) -> ChatCompletionService:
    """Create ChatCompletionService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return ChatCompletionService(uow)

@router.get("", response_model=List[ModelResponse])
@endpoint_handler("get_models")
async def get_models(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    service: ModelService = Depends(get_model_service),
    chat_service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> List[ModelResponse]:
    """Get list of models with optional status filtering.

    Returns only models that the user has access to based on their group membership,
    unless the user is an admin, in which case all models are returned.

    Args:
        status_filter: Filter models by status (optional)
        skip: Number of models to skip (pagination)
        limit: Maximum number of models to return (pagination)
        service: Model service
        chat_service: Chat completion service
        user: Authenticated user information

    Returns:
        List of models the user has access to
    """
    # Get models the user has access to based on their group membership
    user_groups = user.groups
    logger.debug(f"Fetching models for user {user.username} with groups: {user_groups}")

    # Get all models accessible to the user
    models = chat_service.get_models_for_user(user_groups)

    # Apply status filter if provided
    if status_filter:
        try:
            # Convert string to ModelStatus enum
            status_enum = LlmModelStatus(status_filter)
            models = [m for m in models if m.status == status_enum]
        except ValueError:
            # Invalid status value, raise error
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status value: {status_filter}. Valid values are: {[s.value for s in LlmModelStatus]}"
            )

    # Apply pagination
    paginated_models = models[skip:skip + limit]

    return map_model_list_to_response(paginated_models)


@router.get("/statistics")
@endpoint_handler("get_model_statistics")
async def get_model_statistics(
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
) -> Dict[str, Any]:
    """Get model statistics.

    This endpoint requires admin privileges.

    Returns:
        Dictionary with model statistics
    """
    models: List[LlmModel] = service.get_all_models()

    stats: Dict[str, Any] = {
        "total": len(models),
        "by_status": {}
    }

    for status_value in LlmModelStatus:
        stats["by_status"][status_value.value] = len([m for m in models if m.status == status_value])

    return stats


@router.get("/search", response_model=List[ModelResponse])
@endpoint_handler("search_models")
async def search_models_by_name(
    name: str,
    service: ModelService = Depends(get_model_service),
    chat_service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> List[ModelResponse]:
    """Search models by name.

    Returns only models that match the search term and that the user has access to
    based on their group membership.

    Args:
        name: Search term to filter models by name
        service: Model service
        chat_service: Chat completion service
        user: Authenticated user information

    Returns:
        List of models matching the search criteria that the user has access to
    """
    # Get models the user has access to based on their group membership
    user_groups = user.groups
    logger.debug(f"Searching models for user {user.username} with groups: {user_groups}")

    # Get all models accessible to the user
    models = chat_service.get_models_for_user(user_groups)

    # Simple name filtering
    filtered_models = [m for m in models if name.lower() in m.name.lower()]

    return map_model_list_to_response(filtered_models)

@router.post("", response_model=ModelResponse, status_code=http_status.HTTP_201_CREATED)
@endpoint_handler("create_model")
async def create_model(
    model: ModelCreate,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Create a new model.

    This endpoint requires admin privileges.
    """
    _, created_model = service.add_or_update_model(
        model_id=None,
        url=model.url,
        name=model.name,
        technical_name=model.technical_name,
        provider=model.provider,
        capabilities=model.capabilities
    )
    return map_model_to_response(created_model)

@router.get("/{model_id}", response_model=ModelResponse)
@endpoint_handler("get_model")
async def get_model(
    model_id: int,
    service: ModelService = Depends(get_model_service),
    chat_service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> ModelResponse:
    """Get a specific model by ID.

    Returns the model only if the user has access to it based on their group membership.

    Args:
        model_id: ID of the model to retrieve
        service: Model service
        chat_service: Chat completion service
        user: Authenticated user information

    Returns:
        The model if the user has access to it

    Raises:
        HTTPException: If the model is not found or the user doesn't have access to it
    """
    # Get all models the user has access to
    user_groups = user.groups
    accessible_models = chat_service.get_models_for_user(user_groups)

    # Find the specific model by ID
    model = service.get_model_by_id(model_id)

    # Check if the model exists
    if not model:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found"
        )

    # Check if the user has access to the model
    if not any(m.id == model_id for m in accessible_models) and "admin" not in user_groups:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"You don't have access to this model"
        )

    return map_model_to_response(model)


@router.put("/{model_id}", response_model=ModelResponse)
@endpoint_handler("update_model")
async def update_model(
    model_id: int,
    model: ModelUpdate,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Update a model.

    This endpoint requires admin privileges.
    """
    _, updated_model = service.add_or_update_model(
        model_id=model_id,
        url=model.url,
        name=model.name,
        technical_name=model.technical_name,
        provider=model.provider,
        capabilities=model.capabilities
    )

    return map_model_to_response(updated_model)

@router.delete("/{model_id}")
@endpoint_handler("delete_model")
async def delete_model(
    model_id: int,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
):
    """Delete a model.

    This endpoint requires admin privileges.
    """
    service.delete_model(model_id)
    return {"message": f"Model with ID {model_id} deleted successfully"}


@router.patch("/{model_id}/status", response_model=ModelResponse)
@endpoint_handler("update_model_status")
async def update_model_status(
    model_id: int,
    request: UpdateModelStatusRequest,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Update the status of a model.

    This endpoint requires admin privileges.
    """
    updated_model: LlmModel = service.update_model_status(model_id, request.status)
    return map_model_to_response(updated_model)

@router.post("/refresh")
@endpoint_handler("refresh_models")
async def refresh_models(
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
) -> Dict[str, Any]:
    """Refresh available models from configured providers."""
    config = AppConfig.load_from_json()
    await service.fetch_available_models(config.model_configs)
    return {"message": "Models refreshed successfully"}

@router.post("/{model_id}/groups/{group_id}", response_model=ModelResponse)
@endpoint_handler("add_group_to_model")
async def add_group_to_model(
    model_id: int,
    group_id: int,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
):
    """Add a group to a model.

    This endpoint requires admin privileges.

    Args:
        model_id: Model ID
        group_id: Group ID
        service: ModelService instance

    Returns:
        Updated model

    Raises:
        HTTPException: If model or group not found
    """
    updated_model = service.add_model_to_group(model_id, group_id)
    return map_model_to_response(updated_model)

@router.delete("/{model_id}/groups/{group_id}", response_model=ModelResponse)
@endpoint_handler("remove_group_from_model")
async def remove_group_from_model(
    model_id: int,
    group_id: int,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
):
    """Remove a group from a model.

    This endpoint requires admin privileges.

    Args:
        model_id: Model ID
        group_id: Group ID
        service: ModelService instance

    Returns:
        Updated model

    Raises:
        HTTPException: If model not found or group not associated with model
    """
    updated_model = service.remove_model_from_group(model_id, group_id)
    return map_model_to_response(updated_model)

@router.get("/{model_id}/groups", response_model=List[str])
@endpoint_handler("get_groups_for_model")
async def get_groups_for_model(
    model_id: int,
    user: AuthenticatedUser = Depends(require_admin_role),  # Use dependency instead of decorator
    service: ModelService = Depends(get_model_service)
):
    """Get all groups associated with a model.

    This endpoint requires admin privileges.

    Args:
        model_id: Model ID
        service: ModelService instance

    Returns:
        List of groups associated with the model

    Raises:
        HTTPException: If model not found
    """
    groups = service.get_groups_for_model(model_id)
    return [group.name for group in groups] if groups else []
