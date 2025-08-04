"""Model service implementation."""
from typing import List, Optional, Tuple, Dict, Any, Callable
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
from ...domain.protocols.llm_client import LLMClientProtocol
from ...infrastructure.llm.client_factory import LLMClientFactory
import logging

logger = logging.getLogger(__name__)

class ModelService:
    """Service for managing models."""

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None):
        """Initialize service with Unit of Work and optional factories.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
            repository_factory (Optional[callable]): Optional factory for testing
            llm_client_factory (Optional[callable]): Optional LLM client factory for testing
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
            provider (Optional[LLMProvider]): Model provider
            status (Optional[LlmModelStatus]): Model status
            capabilities (Optional[dict]): Model capabilities

        Returns:
            Tuple[str, LlmModel]: Status and model entity

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

                updated_model = self._create_model_instance(
                    model_id=model_id,
                    url=url or existing_model.url,
                    name=name or existing_model.name,
                    technical_name=technical_name or existing_model.technical_name,
                    provider=provider or existing_model.provider,
                    status=status or existing_model.status,
                    capabilities=capabilities if capabilities is not None else existing_model.capabilities,
                    created=existing_model.created,
                    updated=datetime.now(timezone.utc)
                )
                result = repository.update(updated_model)
                logger.info(f"Model {model_id} updated successfully")
                return ("updated", result)

            logger.info("Creating new model")
            if not all([url, name, technical_name, provider]):
                logger.error("Missing required fields for model creation")
                raise ValidationError("URL, name, technical_name, and provider are required for new models")

            models = repository.get_by_technical_name(technical_name)
            if models:
                logger.warning(f"Model with technical_name {technical_name} already exists")
                raise EntityAlreadyExistsError("Model", f"technical_name {technical_name}")

            new_model = self._create_model_instance(
                url=url,
                name=name,
                technical_name=technical_name,
                provider=provider,
                status=status or LlmModelStatus.NEW,
                capabilities=capabilities or {},
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
            result = repository.add(new_model)
            logger.info(f"Model created successfully with id {result.id}")
            return ("created", result)

    def _create_model_instance(self, url: str, name: str, technical_name: str, provider: LLMProvider,
                              status: LlmModelStatus, capabilities: Dict[str, Any],
                              created: datetime, updated: datetime,
                              model_id: Optional[int] = None) -> LlmModel:
        """Create model instance.

        Args:
            url (str): Model URL
            name (str): Model name
            technical_name (str): Model technical name
            provider (LLMProvider): Model provider
            status (LlmModelStatus): Model status
            capabilities (Dict[str, Any]): Model capabilities
            created (datetime): Creation timestamp
            updated (datetime): Update timestamp
            model_id (Optional[int]): Model ID

        Returns:
            LlmModel: Model instance
        """
        base_kwargs = {
            "url": url,
            "name": name,
            "technical_name": technical_name,
            "provider": provider,
            "status": status,
            "capabilities": capabilities,
            "created": created,
            "updated": updated
        }

        if model_id is not None:
            base_kwargs["id"] = model_id

        return LlmModel(**base_kwargs)

    def get_all_models(self) -> List[LlmModel]:
        """Get all models.

        Returns:
            List[LlmModel]: List of all model entities
        """
        logger.info("Fetching all models")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            models: List[LlmModel] = repository.get_all()
            logger.debug(f"Found {len(models)} models")
            return models

    def get_model_by_id(self, model_id: int) -> LlmModel:
        """Get model by ID.

        Args:
            model_id (int): Model ID

        Returns:
            LlmModel: Model entity

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Fetching model {model_id}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            model: Optional[LlmModel] = repository.get_by_id(model_id)
            logger.debug(f"Model {model_id} {'found' if model else 'not found'}")
            if not model:
                raise EntityNotFoundError("Model", str(model_id))

            return model

    def get_model_by_technical_name(self, technical_name: str) -> LlmModel:
        """Get model by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            LlmModel: Model entity

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Fetching model by technical name: {technical_name}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            models: List[LlmModel] = repository.get_by_technical_name(technical_name)
            logger.debug(f"Model '{technical_name}' {'found' if models else 'not found'}")
            if not models:
                raise EntityNotFoundError("Model", technical_name)
            return models[0]  # Return first match

    def update_model_status(self, model_id: int, status: LlmModelStatus) -> LlmModel:
        """Update a model's status.

        Args:
            model_id (int): ID of model to update
            status (LlmModelStatus): New status

        Returns:
            LlmModel: Updated model entity

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Updating status of model {model_id} to {status}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[LlmModel] = repository.get_by_id(model_id)
            if not existing_model:
                raise EntityNotFoundError("Model", str(model_id))

            updated_model = self._create_model_instance(
                model_id=existing_model.id,
                url=existing_model.url,
                name=existing_model.name,
                technical_name=existing_model.technical_name,
                provider=existing_model.provider,
                status=status,
                capabilities=existing_model.capabilities,
                created=existing_model.created,
                updated=datetime.now(timezone.utc)
            )
            result = repository.update(updated_model)
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

    async def fetch_available_models(self, model_configs: List[ModelConfig]) -> None:
        """Fetch available models from external APIs using appropriate LLM clients.

        Args:
            model_configs (List[ModelConfig]): List of model configurations
        """
        logger.debug("Starting to fetch available models using LLM clients.")

        for model_config in model_configs:
            logger.debug(f"Fetching models from provider: {model_config.provider} at {model_config.url}")

            try:
                # Convert string provider to LLMProvider enum
                try:
                    provider_enum = LLMProvider(model_config.provider.lower())
                except ValueError:
                    logger.warning(f"Unknown provider '{model_config.provider}', skipping")
                    continue

                # Create a temporary model instance for the client factory
                temp_model = self._create_model_instance(
                    url=model_config.url,
                    name="temp",
                    technical_name="temp",
                    provider=provider_enum,
                    status=LlmModelStatus.NEW,
                    capabilities={},
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )

                # Use async context manager for proper resource cleanup
                async with LLMClientFactory.create_client(model=temp_model, model_config=model_config) as client:
                    # For Azure, use deployments; for others, use models
                    if provider_enum == LLMProvider.AZURE:
                        models_data: List[Dict[str, Any]] = await client.list_deployments()
                        logger.debug(f"Successfully fetched {len(models_data)} deployments from Azure")
                    else:
                        models_data: List[Dict[str, Any]] = await client.list_models()
                        logger.debug(f"Successfully fetched {len(models_data)} models from {model_config.provider}")

                    # Process each model/deployment
                    for model in models_data:
                        # For Azure deployments, use deployment_id as the model identifier
                        model_id = model.get("deployment_id") or model.get("id", "")
                        model_name = model.get("model") or model.get("id", "")

                        technical_name: str = f"{model_config.technical_name}"

                        await self._save_or_update_model_async(
                            url=model_config.url,
                            name=model_id,  # Use deployment name for Azure
                            technical_name=technical_name,
                            provider=provider_enum,
                            capabilities=model.get("capabilities", {})
                        )

            except Exception as e:
                logger.error(f"Error fetching models from {model_config.provider} at {model_config.url}: {str(e)}")

    async def _save_or_update_model_async(self, url: str, name: str, technical_name: str,
                                         provider: LLMProvider, capabilities: Dict[str, Any]) -> None:
        """Save or update a model from external API (async version).

        Args:
            url (str): Model URL
            name (str): Model name
            technical_name (str): Model technical name
            provider (LLMProvider): Model provider
            capabilities (dict): Model capabilities
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[LlmModel] = repository.get_by_model_provider(name=name, technical_name=technical_name)

            if existing_model:
                updated_model = self._create_model_instance(
                    model_id=existing_model.id,
                    url=url,
                    name=existing_model.name,
                    technical_name=technical_name or existing_model.technical_name,
                    provider=provider,
                    status=existing_model.status,
                    capabilities=capabilities,
                    created=existing_model.created,
                    updated=datetime.now(timezone.utc)
                )
                repository.update(updated_model)
                logger.debug(f"Updated existing model: {technical_name}")
            else:
                new_model = self._create_model_instance(
                    url=url,
                    name=name,
                    technical_name=technical_name,
                    provider=provider,
                    status=LlmModelStatus.NEW,
                    capabilities=capabilities,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )
                repository.add(new_model)
                logger.debug(f"Created new model: {technical_name}")

    def _save_or_update_model(self, url: str, name: str, technical_name: str, provider: LLMProvider,
                             capabilities: Dict[str,Any]) -> None:
        """Save or update a model from external API (sync version - deprecated).

        Args:
            url (str): Model URL
            name (str): Model name
            technical_name (str): Model technical name
            provider (LLMProvider): Model provider
            capabilities (dict): Model capabilities
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            models: List[LlmModel] = repository.get_by_technical_name(technical_name)
            existing_model = models[0] if models else None

            if existing_model:
                updated_model = self._create_model_instance(
                    model_id=existing_model.id,
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
                new_model = self._create_model_instance(
                    url=url,
                    name=name,
                    technical_name=technical_name,
                    provider=provider,
                    status=LlmModelStatus.NEW,
                    capabilities=capabilities,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )
                repository.add(new_model)
                logger.debug(f"Created new model: {technical_name}")
