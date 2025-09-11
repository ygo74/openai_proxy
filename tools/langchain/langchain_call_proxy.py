"""Langchain integration for FastAPI OpenAI proxy."""

from typing import Any, List
import logging
import os
import sys
import argparse

# Handle missing langchain_openai dependency
try:
    from langchain_openai import ChatOpenAI, OpenAI  # type: ignore
    langchain_available: bool = True
except ImportError:
    # Provide dummy symbols to satisfy type checkers
    ChatOpenAI = OpenAI = object  # type: ignore
    langchain_available = False
    print("❌ Langchain OpenAI not found!")
    print("📦 To install dependencies, run:")
    print("   pip install langchain-openai")
    print("   # or")
    print("   pip install langchain[openai]")
    print()

log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Validate log level
numeric_level: int = getattr(logging, log_level, logging.INFO)

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
        if not langchain_available:
            raise ImportError(
                "langchain_openai is not installed. Run 'pip install langchain-openai' to install it."
            )

    @staticmethod
    def create_llm(
        proxy_base_url: str,
        proxy_api_key: str,
        model_name: str = "gpt-3.5-turbo-instruct",
        **kwargs: Any
    ) -> Any:
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
            openai_api_base = f"{proxy_base_url.rstrip('/')}/v1"
            logger.debug(f"Creating OpenAI LLM with openai_api_base: {openai_api_base}, model: {model_name}")
            params: dict[str, Any] = {
                "openai_api_base": openai_api_base,
                "openai_api_key": proxy_api_key,
                "model": model_name,
            }
            params.update(kwargs)
            llm: Any = OpenAI(**params)  # type: ignore
            return llm
        except Exception as e:
            logger.error(f"Failed to create OpenAI LLM: {str(e)}")
            raise

    @staticmethod
    def create_chat_model(
        proxy_base_url: str,
        proxy_api_key: str,
        model_name: str = "gpt-3.5-turbo",
        **kwargs: Any
    ) -> Any:
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
            openai_api_base = f"{proxy_base_url.rstrip('/')}/v1"
            logger.debug(f"Creating ChatOpenAI with openai_api_base: {openai_api_base}, model: {model_name}")
            params: dict[str, Any] = {
                "openai_api_base": openai_api_base,
                "openai_api_key": proxy_api_key,
                "model": model_name,
                "streaming": False,
            }
            params.update(kwargs)
            chat: Any = ChatOpenAI(**params)  # type: ignore
            return chat
        except Exception as e:
            logger.error(f"Failed to create ChatOpenAI: {str(e)}")
            raise


# Example usage functions
def create_proxy_chat_model(
    proxy_url: str = "http://localhost:8000",
    api_key: str = "your-proxy-api-key",
    model: str = "gpt-3.5-turbo"
) -> Any:
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
) -> Any:
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

# Define a callback function to handle streamed tokens
def handle_stream(token: str) -> None:
    """Print streamed token incrementally."""
    print(str(token), end="", flush=True)

# Example usage
if __name__ == "__main__":
    if not langchain_available:
        print("Cannot run example: langchain_openai not installed")
        exit(1)

    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="Langchain proxy test script")
    parser.add_argument("--model", default="gpt-4.1", help="Model name to use via the proxy")
    parser.add_argument("--question", default="Who are you?", help="Question to send to the model")
    parser.add_argument("--api-key", default="sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s", help="Proxy API key")
    parser.add_argument("--proxy-url", default="http://localhost:8000", help="Proxy base URL")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        print("✅ Langchain OpenAI is available!")
        print("🚀 Creating proxy instances...")

        chat_model = create_proxy_chat_model(
            proxy_url=args.proxy_url,
            api_key=args.api_key,
            model=args.model
        )
        print("✅ Chat model created successfully")

        llm = create_proxy_llm(
            proxy_url=args.proxy_url,
            api_key=args.api_key,
            model=args.model
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

        # Completion style question
        response = llm.invoke(args.question)
        print(f"🤖 LLM completion response: {response}")

        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=args.question)]
        chat_response = chat_model.invoke(messages)
        print(f"🤖 Chat model response: {chat_response}")

        print("\n🔄 Streaming (chat model):")
        chunks: List[Any] = []
        for chunk in chat_model.stream(messages):  # type: ignore[attr-defined]
            chunks.append(chunk)
            content = getattr(chunk, "content", "")
            if isinstance(content, list):
                content_list: List[Any] = content  # type: ignore[assignment]
                safe_parts: List[str] = [str(part) for part in content_list]
                content = "".join(safe_parts)
            print(str(content), end="|", flush=True)
        print("\n✅ Streaming finished")

    except Exception as e:
        logger.error(f"Example execution failed: {str(e)}")
        print(f"❌ Error: {str(e)}")
