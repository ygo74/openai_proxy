"""Model endpoints module."""
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from pydantic import BaseModel
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.model_service import ModelService
from ....domain.models.model import Model, ModelStatus
from ....domain.models.configuration import AppConfig

logger = logging.getLogger(__name__)

router = APIRouter()

class ModelResponse(BaseModel):
    """Model response schema."""
    id: int
    url: str
    name: str
    technical_name: str
    status: ModelStatus
    capabilities: dict = {}

class ModelCreate(BaseModel):
    """Model creation schema."""
    url: str
    name: str
    technical_name: str
    capabilities: dict = {}

class ModelUpdate(BaseModel):
    """Model update schema."""
    url: Optional[str] = None
    name: Optional[str] = None
    technical_name: Optional[str] = None
    capabilities: Optional[dict] = None

class UpdateModelStatusRequest(BaseModel):
    """Request schema for updating model status."""
    status: ModelStatus


def get_model_service(db: Session = Depends(get_db)) -> ModelService:
    """Create ModelService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return ModelService(uow)


@router.get("/", response_model=List[ModelResponse])
async def get_models(
    status_filter: Optional[str] = None,  # Renamed from status to status_filter
    skip: int = 0,
    limit: int = 100,
    service: ModelService = Depends(get_model_service)
) -> List[ModelResponse]:
    """Get list of models with optional status filtering."""
    try:
        models: List[Model] = service.get_all_models()

        # Apply status filter if provided
        if status_filter:
            try:
                # Convert string to ModelStatus enum
                status_enum = ModelStatus(status_filter)
                models = [m for m in models if m.status == status_enum]
            except ValueError:
                # Invalid status value, return empty list or raise error
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status value: {status_filter}. Valid values are: {[s.value for s in ModelStatus]}"
                )

        # Apply pagination
        paginated_models = models[skip:skip + limit]

        return [ModelResponse(
            id=m.id if m.id is not None else -1,
            url=m.url,
            name=m.name,
            technical_name=m.technical_name,
            status=m.status,
            capabilities=m.capabilities
        ) for m in paginated_models]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get models: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve models"
        )


@router.get("/statistics")
async def get_model_statistics(
    service: ModelService = Depends(get_model_service)
) -> Dict[str, Any]:
    """Get model statistics."""
    try:
        models: List[Model] = service.get_all_models()

        stats = {
            "total": len(models),
            "by_status": {}
        }

        for status_value in ModelStatus:
            stats["by_status"][status_value.value] = len([m for m in models if m.status == status_value])

        return stats
    except Exception as e:
        logger.error(f"Failed to get model statistics: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model statistics"
        )


@router.get("/search", response_model=List[ModelResponse])
async def search_models_by_name(
    name: str,
    service: ModelService = Depends(get_model_service)
) -> List[ModelResponse]:
    """Search models by name."""
    try:
        models: List[Model] = service.get_all_models()

        # Simple name filtering
        filtered_models = [m for m in models if name.lower() in m.name.lower()]

        return [ModelResponse(
            id=m.id,
            url=m.url,
            name=m.name,
            technical_name=m.technical_name,
            status=m.status,
            capabilities=m.capabilities
        ) for m in filtered_models]
    except Exception as e:
        logger.error(f"Failed to search models: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search models"
        )


@router.post("/", response_model=ModelResponse, status_code=http_status.HTTP_201_CREATED)
async def create_model(
    model: ModelCreate,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Create a new model."""
    try:
        status_result, created_model = service.add_or_update_model(
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            capabilities=model.capabilities
        )
        return ModelResponse(
            id=created_model.id,
            url=created_model.url,
            name=created_model.name,
            technical_name=created_model.technical_name,
            status=created_model.status,
            capabilities=created_model.capabilities
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create model: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model"
        )


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: int,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Get a specific model by ID."""
    try:
        model: Optional[Model] = service.get_model_by_id(model_id)
        if not model:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Model with ID {model_id} not found"
            )
        return ModelResponse(
            id=model.id,
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            status=model.status,
            capabilities=model.capabilities
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model {model_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model"
        )


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: int,
    model: ModelUpdate,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Update a model."""
    try:
        status_result, updated_model = service.add_or_update_model(
            model_id=model_id,
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            capabilities=model.capabilities
        )
        return ModelResponse(
            id=updated_model.id,
            url=updated_model.url,
            name=updated_model.name,
            technical_name=updated_model.technical_name,
            status=updated_model.status,
            capabilities=updated_model.capabilities
        )
    except NoResultFound as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update model {model_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model"
        )


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    service: ModelService = Depends(get_model_service)
):
    """Delete a model."""
    try:
        service.delete_model(model_id)
        return {"message": f"Model with ID {model_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete model {model_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model"
        )


@router.patch("/{model_id}/status", response_model=ModelResponse)
async def update_model_status(
    model_id: int,
    request: UpdateModelStatusRequest,
    service: ModelService = Depends(get_model_service)
) -> ModelResponse:
    """Update the status of a model."""
    logger.info(f"Updating status for model {model_id} to {request.status}")
    try:
        updated_model: Model = service.update_model_status(model_id, request.status)
        logger.info(f"Successfully updated model {model_id} status to {request.status}")
        return ModelResponse(
            id=updated_model.id,
            url=updated_model.url,
            name=updated_model.name,
            technical_name=updated_model.technical_name,
            status=updated_model.status,
            capabilities=updated_model.capabilities,
        )
    except NoResultFound as e:
        logger.error(f"Model not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update model status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update model status: {str(e)}"
        )


@router.post("/refresh")
async def refresh_models(
    service: ModelService = Depends(get_model_service)
) -> Dict[str, Any]:
    """Refresh available models from configured providers."""
    logger.info("Starting models refresh via models endpoint")
    try:
        config = AppConfig.load_from_json()
        service.fetch_available_models(config.model_configs)
        logger.info("Models refreshed successfully")
        return {"message": "Models refreshed successfully"}
    except Exception as e:
        logger.error(f"Failed to refresh models: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh models: {str(e)}"
        )


# Remove endpoints that don't align with the new architecture
# @router.patch("/bulk-status") - Can be added later if needed