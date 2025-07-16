from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.core.models.domain import ModelStatus
from src.core.application.model_service import ModelService
from typing import List
from pydantic import BaseModel
import logging

models_router = APIRouter(prefix="/models", tags=["models"])
logger = logging.getLogger(__name__)


class ModelResponse(BaseModel):
    id: int
    url: str
    name: str
    technical_name: str
    status: ModelStatus
    capabilities: dict = {}


@models_router.get("/", response_model=List[ModelResponse])
async def get_models(db: Session = Depends(get_db)) -> List[ModelResponse]:
    """Get all available models.

    Args:
        db (Session): Database session from dependency injection

    Returns:
        List[ModelResponse]: List of all models with their details
    """
    logger.info("Fetching models from database")
    service = ModelService(db)
    models = service.get_all_models()
    logger.debug(f"Found {len(models)} models")
    return [
        ModelResponse(
            id=model["id"],
            url=model["url"],
            name=model["name"],
            technical_name=model["technical_name"],
            status=model["status"],
            capabilities=model["capabilities"],
        )
        for model in models
    ]
