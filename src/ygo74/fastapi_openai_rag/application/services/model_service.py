"""Model service implementation."""
from typing import List, Optional, Tuple, Dict, Any, Union, Callable
from datetime import datetime, timezone
from ...domain.models.llm_model import LlmModel, LlmModelStatus, AzureLlmModel
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

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None,
                 llm_client_factory: Optional[Callable[[LlmModel, str], LLMClientProtocol]] = None):
        """Initialize service with Unit of Work and optional factories.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
            repository_factory (Optional[callable]): Optional factory for testing
            llm_client_factory (Optional[callable]): Optional LLM client factory for testing
        """
        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: SQLModelRepository(session))
        self._llm_client_factory = llm_client_factory or LLMClientFactory.create_client
        logger.debug("ModelService initialized with Unit of Work")

    def add_or_update_model(self, model_id: Optional[int] = None, url: Optional[str] = None,
                           name: Optional[str] = None, technical_name: Optional[str] = None,
                           provider: Optional[LLMProvider] = None,
                           status: Optional[LlmModelStatus] = None,
                           capabilities: Optional[Dict[str, Any]] = None,
                           api_version: Optional[str] = None) -> Tuple[str, Union[LlmModel, AzureLlmModel]]:
        """Add a new model or update an existing one.

        Args:
            model_id (Optional[int]): ID of model to update
            url (Optional[str]): Model URL
            name (Optional[str]): Model name
            technical_name (Optional[str]): Model technical name
            provider (Optional[LLMProvider]): Model provider
            status (Optional[LlmModelStatus]): Model status
            capabilities (Optional[dict]): Model capabilities
            api_version (Optional[str]): API version (required for Azure models)

        Returns:
            Tuple[str, Union[LlmModel, AzureLlmModel]]: Status and model entity

        Raises:
            EntityNotFoundError: If model not found for update
            ValidationError: If required fields missing for creation
            EntityAlreadyExistsError: If model already exists
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)

            if model_id:
                logger.info(f"Updating model {model_id}")
                existing_model: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_id(model_id)
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
                    api_version=api_version or (getattr(existing_model, 'api_version', None) if isinstance(existing_model, AzureLlmModel) else None),
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

            # Validate Azure-specific requirements
            if provider == LLMProvider.AZURE and not api_version:
                logger.error("API version is required for Azure models")
                raise ValidationError("api_version is required for Azure models")

            existing: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_technical_name(technical_name)
            if existing:
                logger.warning(f"Model with technical_name {technical_name} already exists")
                raise EntityAlreadyExistsError("Model", f"technical_name {technical_name}")

            new_model = self._create_model_instance(
                url=url,
                name=name,
                technical_name=technical_name,
                provider=provider,
                status=status or LlmModelStatus.NEW,
                capabilities=capabilities or {},
                api_version=api_version,
                created=datetime.now(timezone.utc),
                updated=datetime.now(timezone.utc)
            )
            result = repository.add(new_model)
            logger.info(f"Model created successfully with id {result.id}")
            return ("created", result)

    def _create_model_instance(self, url: str, name: str, technical_name: str, provider: LLMProvider,
                              status: LlmModelStatus, capabilities: Dict[str, Any],
                              created: datetime, updated: datetime,
                              model_id: Optional[int] = None, api_version: Optional[str] = None) -> Union[LlmModel, AzureLlmModel]:
        """Create appropriate model instance based on provider.

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
            api_version (Optional[str]): API version for Azure models

        Returns:
            Union[LlmModel, AzureLlmModel]: Model instance

        Raises:
            ValidationError: If Azure model missing api_version
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

        if provider == LLMProvider.AZURE:
            if not api_version:
                raise ValidationError("api_version is required for Azure models")
            return AzureLlmModel(**base_kwargs, api_version=api_version)
        else:
            return LlmModel(**base_kwargs)

    def get_all_models(self) -> List[Union[LlmModel, AzureLlmModel]]:
        """Get all models.

        Returns:
            List[Union[LlmModel, AzureLlmModel]]: List of all model entities
        """
        logger.info("Fetching all models")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            models: List[Union[LlmModel, AzureLlmModel]] = repository.get_all()
            logger.debug(f"Found {len(models)} models")
            return models

    def get_model_by_id(self, model_id: int) -> Union[LlmModel, AzureLlmModel]:
        """Get model by ID.

        Args:
            model_id (int): Model ID

        Returns:
            Union[LlmModel, AzureLlmModel]: Model entity

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Fetching model {model_id}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            model: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_id(model_id)
            logger.debug(f"Model {model_id} {'found' if model else 'not found'}")
            if not model:
                raise EntityNotFoundError("Model", str(model_id))

            return model

    def get_model_by_technical_name(self, technical_name: str) -> Union[LlmModel, AzureLlmModel]:
        """Get model by technical name.

        Args:
            technical_name (str): Model technical name

        Returns:
            Union[LlmModel, AzureLlmModel]: Model entity

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Fetching model by technical name: {technical_name}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            model: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_technical_name(technical_name)
            logger.debug(f"Model '{technical_name}' {'found' if model else 'not found'}")
            if not model:
                raise EntityNotFoundError("Model", technical_name)
            return model

    def update_model_status(self, model_id: int, status: LlmModelStatus) -> Union[LlmModel, AzureLlmModel]:
        """Update a model's status.

        Args:
            model_id (int): ID of model to update
            status (LlmModelStatus): New status

        Returns:
            Union[LlmModel, AzureLlmModel]: Updated model entity

        Raises:
            EntityNotFoundError: If model not found
        """
        logger.info(f"Updating status of model {model_id} to {status}")
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_id(model_id)
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
                api_version=getattr(existing_model, 'api_version', None) if isinstance(existing_model, AzureLlmModel) else None,
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
                    api_version=getattr(model_config, 'api_version', None),
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )

                # Use async context manager for proper resource cleanup
                async with self._llm_client_factory(temp_model, model_config.api_key) as client:
                    # Fetch models using client
                    models_data: List[Dict[str, Any]] = await client.list_models()

                    logger.debug(f"Successfully fetched {len(models_data)} models from {model_config.provider}")

                    # Process each model
                    for model in models_data:
                        technical_name: str = f"{model_config.provider}_{model['id']}"

                        await self._save_or_update_model_async(
                            url=model_config.url,
                            name=model["id"],
                            technical_name=technical_name,
                            provider=provider_enum,
                            capabilities=model.get("capabilities", {}),
                            api_version=getattr(model_config, 'api_version', None)
                        )

            except Exception as e:
                logger.error(f"Error fetching models from {model_config.provider} at {model_config.url}: {str(e)}")

    async def _save_or_update_model_async(self, url: str, name: str, technical_name: str,
                                         provider: LLMProvider, capabilities: Dict[str, Any],
                                         api_version: Optional[str] = None) -> None:
        """Save or update a model from external API (async version).

        Args:
            url (str): Model URL
            name (str): Model name
            technical_name (str): Model technical name
            provider (LLMProvider): Model provider
            capabilities (dict): Model capabilities
            api_version (Optional[str]): API version for Azure models
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_technical_name(technical_name)

            if existing_model:
                updated_model = self._create_model_instance(
                    model_id=existing_model.id,
                    url=url,
                    name=existing_model.name,
                    technical_name=existing_model.technical_name,
                    provider=provider,
                    status=existing_model.status,
                    capabilities=capabilities,
                    api_version=api_version or (getattr(existing_model, 'api_version', None) if isinstance(existing_model, AzureLlmModel) else None),
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
                    api_version=api_version,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )
                repository.add(new_model)
                logger.debug(f"Created new model: {technical_name}")

    # Keep the original synchronous method for backward compatibility
    def _save_or_update_model(self, url: str, name: str, technical_name: str, provider: LLMProvider,
                             capabilities: Dict[str,Any], api_version: Optional[str] = None) -> None:
        """Save or update a model from external API (sync version - deprecated).

        Args:
            url (str): Model URL
            name (str): Model name
            technical_name (str): Model technical name
            provider (LLMProvider): Model provider
            capabilities (dict): Model capabilities
            api_version (Optional[str]): API version for Azure models
        """
        with self._uow as uow:
            repository: IModelRepository = self._repository_factory(uow.session)
            existing_model: Optional[Union[LlmModel, AzureLlmModel]] = repository.get_by_technical_name(technical_name)

            if existing_model:
                updated_model = self._create_model_instance(
                    model_id=existing_model.id,
                    url=url,
                    name=existing_model.name,
                    technical_name=existing_model.technical_name,
                    provider=provider,
                    status=existing_model.status,
                    capabilities=capabilities,
                    api_version=api_version or (getattr(existing_model, 'api_version', None) if isinstance(existing_model, AzureLlmModel) else None),
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
                    api_version=api_version,
                    created=datetime.now(timezone.utc),
                    updated=datetime.now(timezone.utc)
                )
                repository.add(new_model)
                logger.debug(f"Created new model: {technical_name}")
