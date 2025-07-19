"""SQLAlchemy model mappers."""

from typing import TypeVar, Any, Optional, Union
from ..models.model_orm import ModelORM
from ..models.group_orm import GroupORM
from sqlalchemy import inspect

T = TypeVar('T')
ModelOrGroup = Union[ModelORM, GroupORM]

def get_column_value(orm_obj: ModelOrGroup, column_name: str, default: Optional[T] = None) -> Union[T, Any]:
    """Récupère la valeur d'une colonne de manière sûre"""
    if not orm_obj:
        return default if default is not None else None

    try:
        inspected = inspect(orm_obj)
        if hasattr(inspected, 'dict'):
            attrs = getattr(inspected, 'dict', {}) or {}
            return attrs.get(column_name, default)
        return default
    except:
        return default if default is not None else None
