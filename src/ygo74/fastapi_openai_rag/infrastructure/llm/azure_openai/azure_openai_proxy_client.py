"""Azure OpenAI client implementation."""
from typing import Dict, Any, Optional, List

from ....domain.models.llm import LLMProvider
from ....domain.models.chat_completion import ChatCompletionRequest
from ....domain.models.completion import CompletionRequest

from ..openai.base_openai_client import BaseOpenAIClient
from .azure_management_client import AzureManagementClient
from ..enterprise_config import EnterpriseConfig
import logging

logger = logging.getLogger(__name__)

class AzureOpenAIClient(BaseOpenAIClient):
    """Azure OpenAI client with API versioning support."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        api_version: str,
        management_client: Optional[AzureManagementClient] = None,
        enterprise_config: Optional[EnterpriseConfig] = None
    ):
        """Initialize Azure OpenAI client with API version support.

        Args:
            api_key (str): API key for authentication
            base_url (str): Base URL for the Azure OpenAI API
            api_version (str): Azure API version (e.g., "2024-06-01")
            management_client (Optional[AzureManagementClient]): Optional management client for deployment listing
            enterprise_config (Optional[EnterpriseConfig]): Enterprise configuration
        """
        # Call parent constructor with Azure provider
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            provider=LLMProvider.AZURE,
            enterprise_config=enterprise_config
        )

        self.api_version = api_version
        self.management_client = management_client

        logger.debug(f"AzureOpenAIClient initialized at {base_url} with API version {api_version}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Azure OpenAI API requests.

        Returns:
            Dict[str, str]: Request headers with Azure-specific format
        """
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "fastapi-openai-rag/1.0.0"
        }

    def _build_url(self, endpoint: str, deployment_name: str) -> str:
        """Build Azure OpenAI API URL with deployment and API version.

        Args:
            endpoint (str): API endpoint (e.g., "chat/completions")
            deployment_name (str): Azure deployment name

        Returns:
            str: Complete API URL
        """
        return f"{self.base_url}/openai/deployments/{deployment_name}/{endpoint}?api-version={self.api_version}"

    def _build_models_url(self) -> str:
        """Build URL for Azure OpenAI models endpoint.

        Returns:
            str: Models API URL with API version
        """
        return f"{self.base_url}/openai/models?api-version={self.api_version}"

    def _build_responses_url(self) -> str:
        """Build URL for Azure OpenAI responses endpoint.

        Returns:
            str: Responses API URL with API version
        """
        return f"{self.base_url}/openai/v1/responses"

    def _build_embeddings_url(self) -> str:
        """Build URL for embeddings endpoint.

        Returns:
            str: Embeddings API URL
        """
        # Default implementation for standard OpenAI
        return f"{self.base_url}/openai/v1/embeddings"


    def _prepare_completion_payload(self, request: CompletionRequest) -> Dict[str, Any]:
        """Prepare text completion payload for Azure API.

        Args:
            request (CompletionRequest): Domain request

        Returns:
            Dict[str, Any]: API payload
        """
        payload = request.model_dump(exclude_none=True)

        # Remove model from payload as it's in the URL for Azure
        payload.pop("model", None)

        # Azure-specific adjustments
        # Remove parameters that Azure doesn't support or handle differently
        unsupported_params = ["best_of", "suffix", "echo", "logit_bias"]
        for param in unsupported_params:
            payload.pop(param, None)

        # Ensure prompt is properly formatted
        if "prompt" in payload:
            if isinstance(payload["prompt"], list):
                payload["prompt"] = "\n".join(str(p) for p in payload["prompt"])  # type: ignore[list-item]

        # Adjust logprobs parameter - Azure may have different limits
        if "logprobs" in payload and payload["logprobs"] is not None:
            # Azure supports logprobs but may have different limits
            payload["logprobs"] = min(payload["logprobs"], 5)

        # Ensure stop sequences are properly formatted
        if "stop" in payload and payload["stop"] is not None:
            if isinstance(payload["stop"], str):
                # Convert single string to array
                payload["stop"] = [payload["stop"]]
            elif isinstance(payload["stop"], list):
                # Limit to maximum 4 stop sequences for Azure
                payload["stop"] = payload["stop"][:4]

        # Set reasonable defaults for Azure - use higher default for max_tokens
        if "max_tokens" not in payload or payload["max_tokens"] is None:
            payload["max_tokens"] = 1000  # Higher default for better responses
            logger.debug("No max_tokens specified, using default: 1000")

        # Ensure temperature is within Azure limits
        if "temperature" in payload and payload["temperature"] is not None:
            payload["temperature"] = max(0.0, min(2.0, payload["temperature"]))

        # Ensure top_p is within limits
        if "top_p" in payload and payload["top_p"] is not None:
            payload["top_p"] = max(0.0, min(1.0, payload["top_p"]))

        # Ensure n is within Azure limits
        if "n" in payload and payload["n"] is not None:
            payload["n"] = max(1, min(128, payload["n"]))

        # Ensure penalties are within limits
        for penalty_field in ["presence_penalty", "frequency_penalty"]:
            if penalty_field in payload and payload[penalty_field] is not None:
                payload[penalty_field] = max(-2.0, min(2.0, payload[penalty_field]))

        logger.debug(f"Prepared Azure completion payload: {payload}")
        return payload

    def _prepare_chat_payload(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Prepare chat completion payload for Azure API.

        Args:
            request (ChatCompletionRequest): Domain request

        Returns:
            Dict[str, Any]: API payload
        """
        payload = request.model_dump(exclude_none=True)

        # Remove model from payload as it's in the URL for Azure
        payload.pop("model", None)

        if "messages" in payload:
            payload["messages"] = [
                msg.model_dump(exclude_none=True) for msg in request.messages
            ]

        return payload

    async def list_deployments(self) -> List[Dict[str, Any]]:
        """List deployed models from Azure using Management API or fallback to models endpoint.

        Returns:
            List[Dict[str, Any]]: List of deployed models with deployment info

        Raises:
            httpx.HTTPError: If API request fails
        """
        # If management client is available, use it for true deployment listing
        if self.management_client:
            try:
                return await self.management_client.list_deployments()
            except Exception as e:
                logger.warning(f"Failed to get deployments from Management API, falling back to models endpoint: {e}")

        # Fallback to the standard models endpoint with retry
        return await self.list_models()