from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.core.models.models import Model, ModelStatus
from typing import List, Dict, Any
from pydantic import BaseModel
import logging
from datetime import datetime

models_router = APIRouter(prefix="/models", tags=["admin"])

logger = logging.getLogger(__name__)
db = get_db()


class UpdateModelStatusRequest(BaseModel):
    status: ModelStatus


@models_router.get("/")
async def get_models(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    logger.debug("Fetching models from the database.")
    models = db.query(Model).all()
    logger.debug(f"Fetched {len(models)} models.")
    return [
        {
            "id": model.id,
            "url": model.url,
            "name": model.name,
            "capabilities": model.capabilities,
            "technical_name": model.technical_name,
            "status": model.status,
        }
        for model in models
    ]


@models_router.patch("/{model_id}/status")
async def update_model_status(
    model_id: int, request: UpdateModelStatusRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    logger.debug(f"Updating status for model with ID {model_id} to {request.status}.")
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        return {"error": "Model not found"}, 404

    model.status = request.status
    model.updated = datetime.utcnow()
    db.commit()
    logger.debug(f"Model with ID {model_id} status updated to {request.status}.")
    return {"message": "Model status updated successfully."}
