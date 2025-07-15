from datetime import datetime, timezone
from typing import TypeVar, Any, Optional, Dict, Union, cast
from src.core.models.domain import Model, Group, ModelStatus
from src.infrastructure.db.models.model_orm import ModelORM
from src.infrastructure.db.models.group_orm import GroupORM
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

def to_domain_group(orm_group: Optional[GroupORM]) -> Group:
    if not orm_group:
        return Group(
            name="",
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

    return Group(
        id=cast(Optional[int], get_column_value(orm_group, 'id')),
        name=str(get_column_value(orm_group, 'name', "")),
        description=str(get_column_value(orm_group, 'description', "")) or None,
        created=cast(datetime, get_column_value(orm_group, 'created', datetime.now(timezone.utc))),
        updated=cast(datetime, get_column_value(orm_group, 'updated', datetime.now(timezone.utc))),
        models=[]  # Les modèles seront chargés séparément pour éviter la récursion
    )

def to_domain_model(orm_model: Optional[ModelORM]) -> Model:
    if not orm_model:
        return Model(
            url="",
            name="",
            technical_name="",
            status=ModelStatus.NEW,
            created=datetime.now(timezone.utc),
            updated=datetime.now(timezone.utc)
        )

    raw_capabilities = get_column_value(orm_model, 'capabilities', {})
    capabilities: Dict[str, Any] = {}
    if isinstance(raw_capabilities, dict):
        capabilities = cast(Dict[str, Any], raw_capabilities)

    return Model(
        id=cast(Optional[int], get_column_value(orm_model, 'id')),
        url=str(get_column_value(orm_model, 'url', "")),
        name=str(get_column_value(orm_model, 'name', "")),
        technical_name=str(get_column_value(orm_model, 'technical_name', "")),
        status=cast(ModelStatus, get_column_value(orm_model, 'status', ModelStatus.NEW)),
        created=cast(datetime, get_column_value(orm_model, 'created', datetime.now(timezone.utc))),
        updated=cast(datetime, get_column_value(orm_model, 'updated', datetime.now(timezone.utc))),
        capabilities=capabilities,
        groups=[]  # Les groupes seront chargés séparément pour éviter la récursion
    )

def to_orm_group(domain_group: Group) -> GroupORM:
    return GroupORM(
        id=domain_group.id,
        name=domain_group.name,
        description=domain_group.description,
        created=domain_group.created,
        updated=domain_group.updated
    )

def to_orm_model(domain_model: Model) -> ModelORM:
    return ModelORM(
        id=domain_model.id,
        url=domain_model.url,
        name=domain_model.name,
        technical_name=domain_model.technical_name,
        status=domain_model.status,
        created=domain_model.created,
        updated=domain_model.updated,
        capabilities=domain_model.capabilities
    )