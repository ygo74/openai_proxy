from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.core.application.models import fetch_available_models
from src.core.application.config import load_config
from typing import Dict, Any
import logging

admin_router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger(__name__)
db = get_db()

@admin_router.post("/refreshmodels")
async def refresh_models(db: Session = Depends(get_db)) -> Dict[str, Any]:
    logger.debug("Refreshing models via admin endpoint.")
    config = load_config()
    fetch_available_models(config.model_configs, db)
    return {"message": "Models refreshed successfully."}