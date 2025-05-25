from typing import List, Dict, Any
import requests
from sqlalchemy.orm import Session
from src.core.models.configuration import ModelConfig
from src.infrastructure.database import save_or_update_model
import logging

logger = logging.getLogger(__name__)

def fetch_available_models(model_configs: List[ModelConfig], db_session: Session) -> None:
    logger.debug("Starting to fetch available models.")
    for model_config in model_configs:
        logger.debug(f"Fetching models from URL: {model_config.url} with API key: {model_config.api_key}")
        headers = {"Authorization": f"Bearer {model_config.api_key}"}
        # params = {"api-version": model_config.api_version} if model_config.api_version else {}
        params = {"api-version": "2023-03-15-preview"}
        full_url = f"{model_config.url}/openai/models"
        response = requests.get(full_url, headers=headers, params=params)
        if response.status_code == 200:
            logger.debug(f"Successfully fetched models from {full_url}")
            print(response.json())
            models_data = response.json()["data"]
            for model in models_data:
                model_data: Dict[str, Any] = {
                    "url": model_config.url,
                    "name": model["id"],
                    "provider": model_config.provider,
                    "technical_name": f"{model_config.provider}_{model['id']}",
                    "capabilities": model.get("capabilities", {}),
                }
                save_or_update_model(db_session, model_data)
        else:
            logger.error(f"Failed to fetch models from {full_url}. Status code: {response.status_code}, Response: {response.text}")