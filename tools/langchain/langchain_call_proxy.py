"""Langchain integration for FastAPI OpenAI proxy."""

from typing import Any
import logging
import os
import sys

# Handle missing langchain_openai dependency
try:
    from langchain_openai import ChatOpenAI, OpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    print("❌ Langchain OpenAI not found!")
    print("📦 To install dependencies, run:")
    print("   pip install langchain-openai")
    print("   # or")
    print("   pip install langchain[openai]")
    print()

log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Validate log level
numeric_level: int = getattr(logging, log_level, logging.INFO)
if not isinstance(numeric_level, int):
    numeric_level = logging.INFO

logger = logging.getLogger(__name__)
    # Configure root logger

logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)


class ProxyLangchainFactory:
    """Factory class for creating Langchain clients that use FastAPI proxy."""

    @staticmethod
    def _check_availability() -> None:
        """Check if langchain_openai is available.

        Raises:
            ImportError: If langchain_openai is not installed
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "langchain_openai is not installed. "
                "Run 'pip install langchain-openai' to install it."
            )

    @staticmethod
    def create_llm(
        proxy_base_url: str,
        proxy_api_key: str,
        model_name: str = "gpt-3.5-turbo-instruct",
        **kwargs: Any
    ) -> "OpenAI":
        """Create an OpenAI LLM instance using the proxy.

        Args:
            proxy_base_url: Base URL of your FastAPI proxy
            proxy_api_key: API key for your proxy authentication
            model_name: Model name to use through the proxy
            **kwargs: Additional arguments

        Returns:
            OpenAI instance configured to use the proxy

        Raises:
            ImportError: If langchain_openai is not installed
            ValueError: If proxy_base_url or proxy_api_key is empty
            Exception: If LLM creation fails
        """
        ProxyLangchainFactory._check_availability()

        if not proxy_base_url:
            raise ValueError("proxy_base_url cannot be empty")
        if not proxy_api_key:
            raise ValueError("proxy_api_key cannot be empty")

        try:
            base_url = f"{proxy_base_url.rstrip('/')}/v1"
            logger.debug(f"Creating OpenAI LLM with base_url: {base_url}, model: {model_name}")

            return OpenAI(
                base_url=base_url,
                api_key=proxy_api_key,
                model=model_name,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create OpenAI LLM: {str(e)}")
            raise

    @staticmethod
    def create_chat_model(
        proxy_base_url: str,
        proxy_api_key: str,
        model_name: str = "gpt-3.5-turbo",
        **kwargs: Any
    ) -> "ChatOpenAI":
        """Create a ChatOpenAI model instance using the proxy.

        Args:
            proxy_base_url: Base URL of your FastAPI proxy
            proxy_api_key: API key for your proxy authentication
            model_name: Model name to use through the proxy
            **kwargs: Additional arguments

        Returns:
            ChatOpenAI instance configured to use the proxy

        Raises:
            ImportError: If langchain_openai is not installed
            ValueError: If proxy_base_url or proxy_api_key is empty
            Exception: If chat model creation fails
        """
        ProxyLangchainFactory._check_availability()

        if not proxy_base_url:
            raise ValueError("proxy_base_url cannot be empty")
        if not proxy_api_key:
            raise ValueError("proxy_api_key cannot be empty")

        try:
            base_url = f"{proxy_base_url.rstrip('/')}/v1"
            logger.debug(f"Creating ChatOpenAI with base_url: {base_url}, model: {model_name}")

            return ChatOpenAI(
                base_url=base_url,
                api_key=proxy_api_key,
                model=model_name,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create ChatOpenAI: {str(e)}")
            raise


# Example usage functions
def create_proxy_chat_model(
    proxy_url: str = "http://localhost:8000",
    api_key: str = "your-proxy-api-key",
    model: str = "gpt-3.5-turbo"
) -> "ChatOpenAI":
    """Create a chat model that uses your FastAPI proxy.

    Args:
        proxy_url: URL of your FastAPI proxy
        api_key: API key for authentication
        model: Model name to use

    Returns:
        ChatOpenAI instance ready to use
    """
    return ProxyLangchainFactory.create_chat_model(
        proxy_base_url=proxy_url,
        proxy_api_key=api_key,
        model_name=model
    )


def create_proxy_llm(
    proxy_url: str = "http://localhost:8000",
    api_key: str = "your-proxy-api-key",
    model: str = "gpt-3.5-turbo-instruct"
) -> "OpenAI":
    """Create an LLM that uses your FastAPI proxy.

    Args:
        proxy_url: URL of your FastAPI proxy
        api_key: API key for authentication
        model: Model name to use

    Returns:
        OpenAI instance ready to use
    """
    return ProxyLangchainFactory.create_llm(
        proxy_base_url=proxy_url,
        proxy_api_key=api_key,
        model_name=model
    )


# Example usage
if __name__ == "__main__":
    if not LANGCHAIN_AVAILABLE:
        print("Cannot run example: langchain_openai not installed")
        exit(1)

    # Configure logging for debugging
    logging.basicConfig(level=logging.DEBUG)

    try:
        print("✅ Langchain OpenAI is available!")
        print("🚀 Creating proxy instances...")

        # For chat models
        chat_model = create_proxy_chat_model(
            proxy_url="http://localhost:8000",
            api_key="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s",
            # api_key="sk-Uhw0UnymWqxlBcI13rv3644-ZwvXXmq_WjrTFvni62A",
            model="gpt-4o"
        )
        print("✅ Chat model created successfully")

        # For completion models
        llm = create_proxy_llm(
            proxy_url="http://localhost:8000",
            api_key="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s",
            # api_key="sk-Uhw0UnymWqxlBcI13rv3644-ZwvXXmq_WjrTFvni62A",
            model="gpt-4o"
        )
        print("✅ LLM created successfully")

        print("\n📝 To use these models, call invoke() method:")
        print("   # For chat:")
        print("   from langchain_core.messages import HumanMessage")
        print("   messages = [HumanMessage(content='Hello!')]")
        print("   response = chat_model.invoke(messages)")
        print()
        print("   # For completion:")
        print("   response = llm.invoke('Tell me a joke')")

        response = llm.invoke('Who are you')
        print(f"🤖 LLM response: {response}")

        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content='Hello!, who are you ? can you give me you cutoff date')]
        response = chat_model.invoke(messages)
        print(f"🤖 LLM response: {response}")


    except Exception as e:
        logger.error(f"Example execution failed: {str(e)}")
        print(f"❌ Error: {str(e)}")
