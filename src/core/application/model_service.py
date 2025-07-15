from sqlalchemy.orm import Session
from typing import List, Dict, Any
from src.infrastructure.db.models.model_orm import ModelORM
from src.infrastructure.db.mappers.mappers import to_domain_model
from src.core.models.domain import Model, ModelStatus
from datetime import datetime, timezone

def get_all_models(session: Session) -> List[Model]:
    models = session.query(ModelORM).all()
    return [to_domain_model(model) for model in models]

def update_model_status(session: Session, model_id: int, status: ModelStatus) -> Model:
    model = session.query(ModelORM).filter(ModelORM.id == model_id).first()
    if not model:
        raise ValueError("Model not found")

    model.status = status
    model.updated = datetime.now(timezone.utc)
    session.commit()
    session.refresh(model)
    return to_domain_model(model)