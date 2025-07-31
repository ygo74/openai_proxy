"""Model endpoints module."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.model_service import ModelService
from ....domain.models.llm_model import LlmModel, LlmModelStatus
from ....domain.models.configuration import AppConfig
from ....domain.models.llm import LLMProvider
from ..decorators import endpoint_handler

logger = logging.getLogger(__name__)

router = APIRouter()

class ModelResponse(BaseModel):
    """Model response schema."""
    id: Optional[int] = None
    url: str
    name: str
    technical_name: str
    provider: LLMProvider  # Utiliser l'enum directement
    status: LlmModelStatus
    capabilities: Dict[str, Any] = {}

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


def get_model_service(db: Session = Depends(get_db)) -> ModelService:
    """Create ModelService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return ModelService(uow)


@router.get("/", response_model=List[ModelResponse])
@endpoint_handler("get_models")
async def get_models(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    service: ModelService = Depends(get_model_service)
) -> List[ModelResponse]:
    """Get list of models with optional status filtering."""
    models: List[LlmModel] = service.get_all_models()

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

    return [ModelResponse(
        id=m.id if m.id is not None else -1,
        url=m.url,
        name=m.name,
        technical_name=m.technical_name,
        provider=m.provider,  # Maintenant compatible
        status=m.status,
        capabilities=m.capabilities
    ) for m in paginated_models]


@router.get("/statistics")
@endpoint_handler("get_model_statistics")
async def get_model_statistics(
    service: ModelService = Depends(get_model_service)
) -> Dict[str, Any]:
    """Get model statistics."""
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
    service: ModelService = Depends(get_model_service)
) -> List[ModelResponse]:
    """Search models by name."""
    models: List[LlmModel] = service.get_all_models()

    # Simple name filtering
    filtered_models = [m for m in models if name.lower() in m.name.lower()]

    return [ModelResponse(
        id=m.id,
        url=m.url,
        name=m.name,
        technical_name=m.technical_name,
        provider=m.provider,  # Ajouter le provider
        status=m.status,
        capabilities=m.capabilities
    ) for m in filtered_models]


@router.post("/", response_model=ModelResponse, status_code=http_status.HTTP_201_CREATED)
@endpoint_handler("create_model")
async def create_model(
    model: ModelCreate,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Create a new model."""
    _, created_model = service.add_or_update_model(
        model_id=-1,
        url=model.url,
        name=model.name,
        technical_name=model.technical_name,
        provider=model.provider,  # Ajouter le provider
        capabilities=model.capabilities
    )
    return ModelResponse(
        id=created_model.id,
        url=created_model.url,
        name=created_model.name,
        technical_name=created_model.technical_name,
        provider=created_model.provider,  # Ajouter le provider
        status=created_model.status,
        capabilities=created_model.capabilities
    )


@router.get("/{model_id}", response_model=ModelResponse)
@endpoint_handler("get_model")
async def get_model(
    model_id: int,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Get a specific model by ID."""
    model: LlmModel | None = service.get_model_by_id(model_id)

    if model:
        return ModelResponse(
            id=model.id,
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            provider=model.provider,  # Ajouter le provider
            status=model.status,
            capabilities=model.capabilities
        )


@router.put("/{model_id}", response_model=ModelResponse)
@endpoint_handler("update_model")
async def update_model(
    model_id: int,
    model: ModelUpdate,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Update a model."""
    _, updated_model = service.add_or_update_model(
        model_id=model_id,
        url=model.url,
        name=model.name,
        technical_name=model.technical_name,
        provider=model.provider,  # Ajouter le provider
        capabilities=model.capabilities
    )

    return ModelResponse(
        id=updated_model.id,
        url=updated_model.url,
        name=updated_model.name,
        technical_name=updated_model.technical_name,
        provider=updated_model.provider,  # Ajouter le provider
        status=updated_model.status,
        capabilities=updated_model.capabilities
    )


@router.delete("/{model_id}")
@endpoint_handler("delete_model")
async def delete_model(
    model_id: int,
    service: ModelService = Depends(get_model_service)
):
    """Delete a model."""
    service.delete_model(model_id)
    return {"message": f"Model with ID {model_id} deleted successfully"}


@router.patch("/{model_id}/status", response_model=ModelResponse)
@endpoint_handler("update_model_status")
async def update_model_status(
    model_id: int,
    request: UpdateModelStatusRequest,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Update the status of a model."""
    updated_model: LlmModel = service.update_model_status(model_id, request.status)
    return ModelResponse(
        id=updated_model.id,
        url=updated_model.url,
        name=updated_model.name,
        technical_name=updated_model.technical_name,
        provider=updated_model.provider,  # Ajouter le provider
        status=updated_model.status,
        capabilities=updated_model.capabilities,
    )


@router.post("/refresh")
@endpoint_handler("refresh_models")
async def refresh_models(
    service: ModelService = Depends(get_model_service)
) -> Dict[str, Any]:
    """Refresh available models from configured providers."""
    config = AppConfig.load_from_json()
    await service.fetch_available_models(config.model_configs)
    return {"message": "Models refreshed successfully"}