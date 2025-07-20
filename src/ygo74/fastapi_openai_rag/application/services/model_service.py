"""Model service implementation."""
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from ...domain.models.llm_model import LlmModel, LlmModelStatus
from ...domain.models.llm import LLMProvider
from ...domain.repositories.model_repository import IModelRepository
from ...domain.unit_of_work import UnitOfWork
from ...infrastructure.db.repositories.model_repository import SQLModelRepository
from ...domain.models.configuration import ModelConfig
from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from ...domain.exceptions.validation_error import ValidationError
import logging
import requests

logger = logging.getLogger(__name__)

class ModelService:
    """Service for managing models."""

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None):
        """Initialize service with Unit of Work and optional repository factory.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
            repository_factory (Optional[callable]): Optional factory for testing
        """
        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: SQLModelRepository(session))
        logger.debug("ModelService initialized with Unit of Work")

    def add_or_update_model(self, model_id: Optional[int] = None, url: Optional[str] = None,
                           name: Optional[str] = None, technical_name: Optional[str] = None,
                           provider: Optional[LLMProvider] = None,
                           status: Optional[LlmModelStatus] = None,
                           capabilities: Optional[Dict[str, Any]] = None) -> Tuple[str, LlmModel]:
        """Add a new model or update an existing one.

        Args:
            model_id (Optional[int]): ID of model to update
            url (Optional[str]): Model URL
            name (Optional[str]): Model name
            technical_name (Optional[str]): Model technical name
            status (Optional[ModelStatus]): Model status
            capabilities (Optional[dict]): Model capabilities

        Returns:
            Tuple[str, Model]: Status and model entity

        Raises:
            EntityNotFoundError: If model not found for update
            ValidationError: If required fields missing for creation
            EntityAlreadyExistsError: If model already exists
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)

            if model_id:
                logger.info(f"Updating model {model_id}")
                existing_model: Optional[LlmModel] = repository.get_by_id(model_id)
                if not existing_model:
                    logger.error(f"Model {model_id} not found for update")
                    raise EntityNotFoundError("Model", str(model_id))

                updated_model: LlmModel = LlmModel(
                    id=model_id,
                    url=url or existing_model.url,
                    name=name or existing_model.name,
                    technical_name=technical_name or existing_model.technical_name,
                    provider=provider or existing_model.provider,
                    status=status or existing_model.status,
                    capabilities=capabilities if capabilities is not None else existing_model.capabilities,
                    created=existing_model.created,
                    updated=datetime.now(timezone.utc)
                )
                result: LlmModel = repository.update(updated_model)
                logger.info(f"Model {model_id} updated successfully")
                return ("updated", result)

            logger.info("Creating new model")
            if not all([url, name, technical_name, provider]):
                logger.error("Missing required fields for model creation")
                raise ValidationError("URL, name, and technical_name are required for new models")

            existing: Optional[LlmModel] = repository.get_by_technical_name(technical_name)
            if existing:
                logger.warning(f"Model with technical_name {technical_name} already exists")
                raise EntityAlreadyExistsError("Model", f"technical_name {technical_name}")


            new_model: LlmModel = LlmModel(
                url=url,
                name=name,
                technical_name=technical_name,
                provider=provider,
                status=status or LlmModelStatus.NEW,
                capabilities=capabilities or {},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
            result: LlmModel = repository.add(new_model)
            logger.info(f"Model created successfully with id {result.id}")
            return ("created", result)

    def get_all_models(self) -> List[LlmModel]:
        """Get all models.

        Returns:
            List[Model]: List of all model entities
        """
        logger.info("Fetching all models")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            models: List[LlmModel] = repository.get_all()
            logger.debug(f"Found {len(models)} models")
            return models

    def get_model_by_id(self, model_id: int) -> Optional[LlmModel]:
        """Get model by ID.

        Args:
            model_id (int): Model ID

        Returns:
            Optional[Model]: Model entity if found, None otherwise
        """
        logger.info(f"Fetching model {model_id}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            model: Optional[LlmModel] = repository.get_by_id(model_id)
            logger.debug(f"Model {model_id} {'found' if model else 'not found'}")
            if not model:
                raise EntityNotFoundError("Model", str(model_id))

            return model

    def get_model_by_technical_name(self, technical_name: str) -> Optional[LlmModel]:
        """Get model by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            Optional[Model]: Model entity if found, None otherwise
        """
        logger.info(f"Fetching model by technical name: {technical_name}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            model: Optional[LlmModel] = repository.get_by_technical_name(technical_name)
            logger.debug(f"Model '{technical_name}' {'found' if model else 'not found'}")
            if not model:
                raise EntityNotFoundError("Model", technical_name)
            return model

    def update_model_status(self, model_id: int, status: LlmModelStatus) -> LlmModel:
        """Update a model's status.

        Args:
            model_id (int): ID of model to update
            status (ModelStatus): New status

        Returns:
            Model: Updated model entity

        Raises:
            NoResultFound: If model not found
        """
        logger.info(f"Updating status of model {model_id} to {status}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[LlmModel] = repository.get_by_id(model_id)
            if not existing_model:
                raise EntityNotFoundError("Model", str(model_id))

            updated_model: LlmModel = LlmModel(
                id=existing_model.id,
                url=existing_model.url,
                name=existing_model.name,
                technical_name=existing_model.technical_name,
                provider=existing_model.provider,
                status=status,
                capabilities=existing_model.capabilities,
                created=existing_model.created,
                updated=datetime.now(timezone.utc)
            )
            result: LlmModel = repository.update(updated_model)
            logger.info(f"Model {model_id} status updated to {status}")
            return result

    def delete_model(self, model_id: int) -> None:
        """Delete a model.

        Args:
            model_id (int): ID of model to delete

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Deleting model {model_id}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            # Check if model exists before trying to delete
            existing_model: Optional[LlmModel] = repository.get_by_id(model_id)
            if not existing_model:
                logger.error(f"Model {model_id} not found for deletion")
                raise EntityNotFoundError("Model", str(model_id))

            repository.delete(model_id)
            logger.info(f"Model {model_id} deleted successfully")

    def fetch_available_models(self, model_configs: List[ModelConfig]) -> None:
        """Fetch available models from external APIs.

        Args:
            model_configs (List[ModelConfig]): List of model configurations
        """
        logger.debug("Starting to fetch available models.")
        for model_config in model_configs:
            logger.debug(f"Fetching models from URL: {model_config.url} with API key: {model_config.api_key}")
            headers: dict = {"Authorization": f"Bearer {model_config.api_key}"}
            params: dict = {"api-version": "2023-03-15-preview"}
            full_url: str = f"{model_config.url}/openai/models"

            try:
                response = requests.get(full_url, headers=headers, params=params)
                if response.status_code == 200:
                    logger.debug(f"Successfully fetched models from {full_url}")
                    models_data = response.json()["data"]
                    for model in models_data:
                        technical_name: str = f"{model_config.provider}_{model['id']}"

                        # Convert string provider to LLMProvider enum
                        try:
                            provider_enum = LLMProvider(model_config.provider.lower())
                        except ValueError:
                            logger.warning(f"Unknown provider '{model_config.provider}', skipping model {technical_name}")
                            continue

                        self._save_or_update_model(
                            url=model_config.url,
                            name=model["id"],
                            technical_name=technical_name,
                            provider=provider_enum,
                            capabilities=model.get("capabilities", {})
                        )
                else:
                    logger.error(f"Failed to fetch models from {full_url}. Status code: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching models from {full_url}: {str(e)}")

    def _save_or_update_model(self, url: str, name: str, technical_name: str, provider: LLMProvider, capabilities: Dict[str,Any]) -> None:
        """Save or update a model from external API.

        Args:
            url (str): Model URL
            name (str): Model name
            technical_name (str): Model technical name
            capabilities (dict): Model capabilities
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[LlmModel] = repository.get_by_technical_name(technical_name)

            if existing_model:
                updated_model: LlmModel = LlmModel(
                    id=existing_model.id,
                    url=url,
                    name=existing_model.name,
                    technical_name=existing_model.technical_name,
                    provider=provider,
                    status=existing_model.status,
                    capabilities=capabilities,
                    created=existing_model.created,
                    updated=datetime.now(timezone.utc)
                )
                repository.update(updated_model)
                logger.debug(f"Updated existing model: {technical_name}")
            else:
                new_model: LlmModel = LlmModel(
                    url=url,
                    name=name,
                    technical_name=technical_name,
                    status=LlmModelStatus.NEW,
                    provider=provider,
                    capabilities=capabilities,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )
                repository.add(new_model)
                logger.debug(f"Created new model: {technical_name}")
