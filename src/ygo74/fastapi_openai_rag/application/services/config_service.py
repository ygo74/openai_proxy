"""Configuration service for managing application configuration."""
import os
from typing import Dict, Optional, Union
from ...domain.models.configuration import AppConfig, ModelConfig, AzureModelConfig, UniqueModelConfig
from ...domain.models.configuration import AppConfig
from ...infrastructure.db.session import SessionManager
from ...infrastructure.db.init_db import init_db, create_initial_data

import logging

logger = logging.getLogger(__name__)

class ConfigService:
    """Singleton service for managing application configuration."""

    _instance: Optional['ConfigService'] = None
    _config: Optional[AppConfig] = None
    _config_file_path: str = "config.json"
    _last_modified: Optional[float] = None

    def __new__(cls) -> 'ConfigService':
        """Create singleton instance.

        Returns:
            ConfigService: Singleton instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the config service."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.reload_config()
            self.init_database()
            logger.debug("ConfigService initialized")

    def reload_config(self) -> None:
        """Reload configuration from file if it has been modified.

        Raises:
            FileNotFoundError: If config file not found
            json.JSONDecodeError: If config file is invalid JSON
        """
        try:
            # Check if file exists and get modification time
            if not os.path.exists(self._config_file_path):
                logger.warning(f"Config file {self._config_file_path} not found")
                return

            current_modified = os.path.getmtime(self._config_file_path)

            # Only reload if file has been modified or not loaded yet
            if self._last_modified is None or current_modified > self._last_modified:
                logger.info(f"Loading configuration from {self._config_file_path}")
                self._config = AppConfig.load_from_json(self._config_file_path)
                self._last_modified = current_modified
                logger.info("Configuration loaded successfully")
            else:
                logger.debug("Configuration file not modified, using cached version")

        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise

    def get_model_config(self, technical_name: str) -> Optional[Union[ModelConfig, AzureModelConfig, UniqueModelConfig]]:
        """Get Model config for the provider.

        Args:
            technical_name (str): technical name of the model provider

        Returns:
            Optional[str]: API key if found, None otherwise
        """
        self.reload_config()  # Check for updates

        if not self._config or not self._config.model_configs:
            logger.warning("No configuration loaded")
            return None

        # Find the model config for this provider
        for model_config in self._config.model_configs:
            if model_config.technical_name.lower() == technical_name.lower():
                return model_config

        logger.warning(f"No model config for model provider {technical_name}")
        return None



    def get_config(self) -> AppConfig:
        """Get the current application configuration.

        Returns:
            AppConfig: Current configuration
        """
        self.reload_config()  # Check for updates
        if not self._config:
            raise ValueError("Configuration not loaded")
        return self._config

    def init_database(self) -> None:
        """Initialize database connection and load initial data.

        This method can be used to set up the database connection
        and load any initial data required by the application.
        """
        """Initialize database on application startup."""
        logger.info("Initializing application...")

        # Load configuration
        config: AppConfig | None = self._config
        if not config:
            raise ValueError("Configuration must be loaded before initializing the database")

        logger.info(f"Loaded configuration with database type: {config.db_type}")

        # Initialize database connection
        if config.db_type == "sqlite":
            db_url = config.db_url
        elif config.db_type == "postgres":
            # TODO: Add PostgreSQL support
            raise NotImplementedError("PostgreSQL support is not implemented yet")
        else:
            raise ValueError(f"Unsupported database type: {config.db_type}")

        # Initialize session manager
        session_manager = SessionManager.initialize(db_url)

        # Create database structure and initial data
        init_db(session_manager._engine)
        with session_manager.session() as session:
            create_initial_data(session)

        logger.info("Application initialization completed")

# Global instance
config_service = ConfigService()
