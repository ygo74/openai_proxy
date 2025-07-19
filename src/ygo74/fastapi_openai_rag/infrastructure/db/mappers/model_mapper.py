"""Mapper for Model domain and ORM models."""
from typing import Optional
from .base import BaseMapper
from ....domain.models.model import Model
from ..models.model_orm import ModelORM

class ModelMapper(BaseMapper[Model, ModelORM]):
    """Mapper for converting between Model domain and ORM models."""

    def to_orm(self, entity: Model) -> ModelORM:
        """Convert Model domain entity to ORM entity.

        Args:
            entity (Model): Domain entity instance

        Returns:
            ModelORM: ORM entity instance
        """
        return ModelORM(
            id=entity.id,
            url=entity.url,
            name=entity.name,
            technical_name=entity.technical_name,
            status=entity.status,
            capabilities=entity.capabilities,
            created=entity.created,
            updated=entity.updated
        )

    def to_domain(self, orm_entity: ModelORM) -> Model:
        """Convert ORM entity to Model domain entity.

        Args:
            orm_entity (ModelORM): ORM entity instance

        Returns:
            Model: Domain entity instance
        """
        return Model(
            id=orm_entity.id,
            url=orm_entity.url,
            name=orm_entity.name,
            technical_name=orm_entity.technical_name,
            status=orm_entity.status,
            capabilities=orm_entity.capabilities,
            created=orm_entity.created,
            updated=orm_entity.updated
        )