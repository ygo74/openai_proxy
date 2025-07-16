from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from src.infrastructure.model_crud import ModelRepository
from typing import Dict, Any, List, Optional
from src.core.models.domain import Model, ModelStatus
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ModelService:
    """Service class for managing models."""

    def __init__(self, session: Session, repository: Optional[ModelRepository] = None):
        """Initialize the service with a database session and optional repository.

        Args:
            session (Session): The database session
            repository (Optional[ModelRepository]): Optional repository instance for testing
        """
        self._repository = repository if repository is not None else ModelRepository(session)
        logger.debug("ModelService initialized with session and repository")

    def add_or_update_model(self, model_id: Optional[int] = None, url: Optional[str] = None,
                           name: Optional[str] = None, technical_name: Optional[str] = None,
                           status: Optional[ModelStatus] = None,
                           capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add a new model or update an existing one.

        Args:
            model_id (Optional[int]): ID of the model to update
            url (Optional[str]): URL of the model
            name (Optional[str]): Name of the model
            technical_name (Optional[str]): Technical name of the model (must be unique)
            status (Optional[ModelStatus]): Status of the model
            capabilities (Optional[Dict[str, Any]]): Model capabilities

        Returns:
            Dict[str, Any]: Operation result with status and model data

        Raises:
            ValueError: If required fields are missing when creating a new model
            NoResultFound: If model is not found when updating
        """
        if model_id:
            logger.info(f"Attempting to update model with id {model_id}")
            logger.debug(f"Update parameters: url={url}, name={name}, technical_name={technical_name}, status={status}")

            existing_model = self._repository.get_by_id(model_id)
            if not existing_model:
                logger.error(f"Model with id {model_id} not found")
                raise NoResultFound(f"Model with id {model_id} not found")

            updated_model = Model(
                id=model_id,
                url=url or existing_model.url,
                name=name or existing_model.name,
                technical_name=technical_name or existing_model.technical_name,
                status=status or existing_model.status,
                capabilities=capabilities if capabilities is not None else existing_model.capabilities,
                created=existing_model.created,
                updated=datetime.now(timezone.utc)
            )
            result = self._repository.update(model_id, updated_model)
            logger.info(f"Successfully updated model {model_id}")
            return {"status": "updated", "model": result}

        # Create new model
        logger.info(f"Attempting to create new model with name: {name}")

        if not all([url, name, technical_name]):
            logger.error("Attempted to create model without required fields")
            raise ValueError("URL, name, and technical_name are required when creating a new model")

        # Check if model with same technical_name exists
        existing_model = self._repository.get_by_technical_name(technical_name)
        if existing_model:
            logger.error(f"Model with technical_name {technical_name} already exists")
            raise ValueError(f"Model with technical_name {technical_name} already exists")

        result = self._repository.create(
            url=url,
            name=name,
            technical_name=technical_name,
            status=status or ModelStatus.NEW,
            capabilities=capabilities
        )
        logger.info(f"Successfully created new model with id {result.id}")
        return {"status": "created", "model": result}

    def get_all_models(self) -> List[Dict[str, Any]]:
        """Get all models.

        Returns:
            List[Dict[str, Any]]: List of models with their details
        """
        logger.info("Fetching all models")
        models = self._repository.get_all()
        logger.debug(f"Found {len(models)} models")
        return [{"id": model.id, "name": model.name, "url": model.url,
                "technical_name": model.technical_name, "status": model.status,
                "capabilities": model.capabilities}
                for model in models]

    def update_model_status(self, model_id: int, status: ModelStatus) -> Dict[str, Any]:
        """Update a model's status.

        Args:
            model_id (int): ID of the model to update
            status (ModelStatus): New status to set

        Returns:
            Dict[str, Any]: Operation result with updated model data

        Raises:
            NoResultFound: If model doesn't exist
        """
        logger.info(f"Attempting to update status of model {model_id} to {status}")
        try:
            model = self._repository.get_by_id(model_id)
            if not model:
                raise NoResultFound(f"Model with id {model_id} not found")

            updated_model = Model(
                id=model_id,
                url=model.url,
                name=model.name,
                technical_name=model.technical_name,
                status=status,
                capabilities=model.capabilities,
                created=model.created,
                updated=datetime.now(timezone.utc)
            )
            result = self._repository.update(model_id, updated_model)
            logger.info(f"Successfully updated status of model {model_id}")
            return {"status": "updated", "model": result}
        except NoResultFound as e:
            logger.error(f"Failed to update model status: {str(e)}")
            raise

    def delete_model(self, model_id: int) -> Dict[str, str]:
        """Delete a model.

        Args:
            model_id (int): ID of the model to delete

        Returns:
            Dict[str, str]: Operation result status

        Raises:
            NoResultFound: If model doesn't exist
        """
        logger.info(f"Attempting to delete model {model_id}")
        try:
            self._repository.delete(model_id)
            logger.info(f"Successfully deleted model {model_id}")
            return {"status": "deleted"}
        except NoResultFound as e:
            logger.error(f"Failed to delete model {model_id}: {str(e)}")
            raise