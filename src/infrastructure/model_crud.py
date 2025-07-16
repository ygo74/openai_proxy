from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from src.infrastructure.db.models.model_orm import ModelORM
from src.infrastructure.db.mappers.mappers import to_domain_model, to_orm_model
from src.core.models.domain import Model, ModelStatus
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

class ModelRepository:
    """Repository for managing models in the database."""

    def __init__(self, session: Session):
        """Initialize the repository with a database session.

        Args:
            session (Session): SQLAlchemy database session
        """
        self._session = session

    def create(self, url: str, name: str, technical_name: str,
               status: ModelStatus = ModelStatus.NEW,
               capabilities: Optional[Dict[str, Any]] = None) -> Model:
        """Create a new model in the database.

        Args:
            url (str): URL of the model
            name (str): Name of the model
            technical_name (str): Technical name of the model (must be unique)
            status (ModelStatus, optional): Status of the model. Defaults to ModelStatus.NEW
            capabilities (Dict[str, Any], optional): Model capabilities. Defaults to None.

        Returns:
            Model: The created model domain model

        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            new_model = Model(
                url=url,
                name=name,
                technical_name=technical_name,
                status=status,
                capabilities=capabilities or {},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
            orm_model = to_orm_model(new_model)
            self._session.add(orm_model)
            self._session.commit()
            self._session.refresh(orm_model)
            return to_domain_model(orm_model)
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def get_by_id(self, model_id: int) -> Optional[Model]:
        """Get a model by its ID.

        Args:
            model_id (int): The ID of the model to retrieve

        Returns:
            Optional[Model]: The model if found, None otherwise
        """
        model = self._session.query(ModelORM).filter(ModelORM.id == model_id).first()
        return to_domain_model(model) if model else None

    def get_by_technical_name(self, technical_name: str) -> Optional[Model]:
        """Get a model by its technical name.

        Args:
            technical_name (str): The technical name of the model to retrieve

        Returns:
            Optional[Model]: The model if found, None otherwise
        """
        model = self._session.query(ModelORM).filter(ModelORM.technical_name == technical_name).first()
        return to_domain_model(model) if model else None

    def get_all(self) -> List[Model]:
        """Get all models.

        Returns:
            List[Model]: List of all models
        """
        return [to_domain_model(model) for model in self._session.query(ModelORM).all()]

    def update(self, model_id: int, updated_model: Model) -> Model:
        """Update a model in the database.

        Args:
            model_id (int): ID of the model to update
            updated_model (Model): New model data

        Returns:
            Model: The updated model

        Raises:
            NoResultFound: If model doesn't exist
            SQLAlchemyError: If database operation fails
        """
        try:
            now = datetime.now(timezone.utc)
            result = self._session.query(ModelORM).filter(ModelORM.id == model_id).update({
                ModelORM.url: updated_model.url,
                ModelORM.name: updated_model.name,
                ModelORM.technical_name: updated_model.technical_name,
                ModelORM.status: updated_model.status,
                ModelORM.capabilities: updated_model.capabilities,
                ModelORM.updated: now
            })

            if result == 0:
                raise NoResultFound(f"Model with id {model_id} not found")

            self._session.commit()
            updated = self._session.query(ModelORM).filter(ModelORM.id == model_id).one()
            return to_domain_model(updated)
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def delete(self, model_id: int) -> None:
        """Delete a model from the database.

        Args:
            model_id (int): ID of the model to delete

        Raises:
            NoResultFound: If model doesn't exist
            SQLAlchemyError: If database operation fails
        """
        try:
            result = self._session.query(ModelORM).filter(ModelORM.id == model_id).delete()
            if result == 0:
                raise NoResultFound(f"Model with id {model_id} not found")

            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise