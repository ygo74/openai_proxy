"""Tests for LLM client factory."""
import pytest
from unittest.mock import Mock, patch
import ssl

from src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory import (
    LLMClientFactory, EnterpriseConfig
)
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from src.ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel, AzureLlmModel


class TestEnterpriseConfig:
    """Test EnterpriseConfig dataclass."""

    def test_enterprise_config_default_values(self):
        """Test enterprise config default values."""
        # arrange & act
        config = EnterpriseConfig()

        # assert
        assert config.enable_retry is True
        assert config.retry_handler is None
        assert config.proxy_url is None
        assert config.proxy_auth is None
        assert config.verify_ssl is True
        assert config.ca_cert_file is None
        assert config.client_cert_file is None
        assert config.client_key_file is None

    def test_enterprise_config_should_auto_detect_proxy_default(self):
        """Test should auto-detect proxy with default settings."""
        # arrange & act
        config = EnterpriseConfig()

        # assert
        assert config.should_auto_detect_proxy() is True

    def test_enterprise_config_should_auto_detect_proxy_explicit_empty(self):
        """Test should not auto-detect proxy when explicitly set to empty."""
        # arrange & act
        config = EnterpriseConfig(proxy_url="")

        # assert
        assert config.should_auto_detect_proxy() is False

    def test_enterprise_config_should_auto_detect_proxy_explicit_url(self):
        """Test should not auto-detect proxy when URL is set."""
        # arrange & act
        config = EnterpriseConfig(proxy_url="http://proxy.example.com:8080")

        # assert
        assert config.should_auto_detect_proxy() is False


class TestLLMClientFactory:
    """Test LLMClientFactory class."""

    def test_llm_client_factory_create_azure_client(self):
        """Test creating Azure OpenAI client."""
        # arrange
        model = AzureLlmModel(
            name="gpt-4",
            provider=LLMProvider.AZURE,
            url="https://test.openai.azure.com",
            api_version="2024-06-01"
        )

        # act
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory.AzureOpenAIProxyClient') as mock_client:
            client = LLMClientFactory.create_client(model, "test-key")

        # assert
        mock_client.assert_called_once()
        call_args = mock_client.call_args
        assert call_args[1]['api_key'] == "test-key"
        assert call_args[1]['base_url'] == "https://test.openai.azure.com"
        assert call_args[1]['api_version'] == "2024-06-01"
        assert call_args[1]['provider'] == LLMProvider.AZURE

    def test_llm_client_factory_create_openai_client(self):
        """Test creating OpenAI client."""
        # arrange
        model = LlmModel(
            name="gpt-4",
            provider=LLMProvider.OPENAI,
            url="https://api.openai.com/v1"
        )

        # act
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory.OpenAIProxyClient') as mock_client:
            client = LLMClientFactory.create_client(model, "test-key")

        # assert
        mock_client.assert_called_once()

    def test_llm_client_factory_create_azure_client_invalid_model(self):
        """Test creating Azure client with invalid model."""
        # arrange
        model = LlmModel(  # Not AzureLlmModel
            name="gpt-4",
            provider=LLMProvider.AZURE,
            url="https://test.openai.azure.com"
        )

        # act & assert
        with pytest.raises(ValueError, match="Azure provider requires AzureLlmModel with api_version"):
            LLMClientFactory.create_client(model, "test-key")

    def test_llm_client_factory_create_unsupported_provider(self):
        """Test creating client with unsupported provider."""
        # arrange
        model = LlmModel(
            name="claude-3",
            provider=LLMProvider.ANTHROPIC,
            url="https://api.anthropic.com"
        )

        # act & assert
        with pytest.raises(ValueError, match="Anthropic client not yet implemented"):
            LLMClientFactory.create_client(model, "test-key")

    def test_llm_client_factory_create_enterprise_client(self):
        """Test creating enterprise client with defaults."""
        # arrange
        model = AzureLlmModel(
            name="gpt-4",
            provider=LLMProvider.AZURE,
            url="https://test.openai.azure.com",
            api_version="2024-06-01"
        )

        # act
        with patch('src.ygo74.fastapi_openai_rag.infrastructure.llm.client_factory.AzureOpenAIProxyClient') as mock_client:
            client = LLMClientFactory.create_enterprise_client(model, "test-key")

        # assert
        mock_client.assert_called_once()
        call_args = mock_client.call_args
        enterprise_config = call_args[1]['enterprise_config']
        assert enterprise_config.enable_retry is True
        assert enterprise_config.retry_handler is not None
        assert enterprise_config.verify_ssl is True
