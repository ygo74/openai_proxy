# FastAPI OpenAI Proxy

This project is a FastAPI-based proxy for OpenAI. It provides a simple interface to interact with OpenAI's API.


# sources

transparent proxy : https://github.com/fangwentong/openai-proxy
OpenAI schema : https://github.com/openai/openai-openapi/blob/manual_spec/openapi.yaml

``` python
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

```