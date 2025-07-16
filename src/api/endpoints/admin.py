from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from src.infrastructure.database import get_db
from src.core.application.models import fetch_available_models
from src.core.application.config import load_config
from src.core.models.domain import ModelStatus
from src.core.application.model_service import ModelService
from typing import Dict, Any
from pydantic import BaseModel
import logging

admin_router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

class UpdateModelStatusRequest(BaseModel):
    status: ModelStatus

class ModelResponse(BaseModel):
    id: int
    url: str
    name: str
    technical_name: str
    status: ModelStatus
    capabilities: dict = {}

@admin_router.post("/refreshmodels")
async def refresh_models(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Refresh available models from configured providers.

    Args:
        db (Session): Database session from dependency injection

    Returns:
        Dict[str, Any]: Operation result message

    Raises:
        HTTPException: If there's an error during refresh
    """
    logger.info("Starting models refresh via admin endpoint")
    try:
        config = load_config()
        fetch_available_models(config.model_configs, db)
        logger.info("Models refreshed successfully")
        return {"message": "Models refreshed successfully"}
    except Exception as e:
        logger.error(f"Failed to refresh models: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh models: {str(e)}"
        )

@admin_router.patch("/models/{model_id}/status", response_model=ModelResponse)
async def update_model_status(
    model_id: int,
    request: UpdateModelStatusRequest,
    db: Session = Depends(get_db)
) -> ModelResponse:
    """Update the status of a model.

    Args:
        model_id (int): ID of the model to update
        request (UpdateModelStatusRequest): New status to set
        db (Session): Database session from dependency injection

    Returns:
        ModelResponse: Updated model data

    Raises:
        HTTPException: If model not found or update fails
    """
    logger.info(f"Updating status for model {model_id} to {request.status}")
    try:
        service = ModelService(db)
        result = service.update_model_status(model_id, request.status)
        model = result["model"]
        logger.info(f"Successfully updated model {model_id} status to {request.status}")
        return ModelResponse(
            id=model.id,
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            status=model.status,
            capabilities=model.capabilities,
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