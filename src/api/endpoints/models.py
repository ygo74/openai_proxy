from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.core.models.domain import ModelStatus, Model
from src.core.application.model_service import get_all_models, update_model_status
from typing import List
from pydantic import BaseModel
import logging

models_router = APIRouter(prefix="/models", tags=["admin"])
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


@models_router.get("/", response_model=List[ModelResponse])
async def get_models_endpoint(db: Session = Depends(get_db)) -> List[ModelResponse]:
    logger.debug("Fetching models from the database.")
    models = get_all_models(db)
    logger.debug(f"Fetched {len(models)} models.")
    return [
        ModelResponse(
            id=model.id,
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            status=model.status,
            capabilities=model.capabilities,
        )
        for model in models
    ]


@models_router.patch("/{model_id}/status", response_model=ModelResponse)
async def update_model_status_endpoint(
    model_id: int,
    request: UpdateModelStatusRequest,
    db: Session = Depends(get_db),
) -> ModelResponse:
    logger.debug(f"Updating status for model with ID {model_id} to {request.status}.")
    try:
        model = update_model_status(db, model_id, request.status)
        logger.debug(f"Model status updated successfully.")
        return ModelResponse(
            id=model.id,
            url=model.url,
            name=model.name,
            technical_name=model.technical_name,
            status=model.status,
            capabilities=model.capabilities,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
