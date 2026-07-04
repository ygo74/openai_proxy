"""Test direct du ChatCompletionService sans passer par FastAPI.

Ce script teste directement le service pour isoler les problèmes de performance
et vérifier si la latence vient de FastAPI ou du service lui-même.
"""
import asyncio
import time
import base64
import sys
import os
from pathlib import Path

# Load .env BEFORE importing anything else
from dotenv import load_dotenv
load_dotenv()  # This loads DATABASE_URL and other env vars

print(f"🔧 DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')}")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.ygo74.fastapi_openai_rag.application.services.chat_completion_service import ChatCompletionService
from src.ygo74.fastapi_openai_rag.domain.models.chat_completion import ChatCompletionRequest, ChatMessage
from src.ygo74.fastapi_openai_rag.domain.models.autenticated_user import AuthenticatedUser
from src.ygo74.fastapi_openai_rag.domain.models.llm_model import LlmModel
from src.ygo74.fastapi_openai_rag.domain.models.llm import LLMProvider
from src.ygo74.fastapi_openai_rag.infrastructure.db.unit_of_work import SQLUnitOfWork
from src.ygo74.fastapi_openai_rag.infrastructure.db.session import get_db
from src.ygo74.fastapi_openai_rag.application.services.config_service import config_service
from src.ygo74.fastapi_openai_rag.config.logging_config import setup_logging


def local_image_to_base64(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


async def test_direct_service():
    """Test ChatCompletionService directement sans FastAPI."""

    # Setup logging
    setup_logging()

# Initialize config (this will use DATABASE_URL from .env)
    config_service.reload_config()

    # Don't call init_database() - it creates tables, we want to use existing DB
    # config_service.init_database()

    print("=" * 80)
    print("🧪 TEST DIRECT DU SERVICE (SANS FASTAPI)")
    print("=" * 80)

    # Prepare image
    image_path = r"C:\Users\Administrator\OneDrive\Images\226px-Jenkins_logo.svg.png"
    print(f"📸 Loading image: {image_path}")
    image_b64 = local_image_to_base64(image_path)
    print(f"   Image size: {len(image_b64)} bytes (base64)")

    # Create authenticated user with models (simulating auth middleware)
    # We need to load models from DB first
    db_gen = get_db()
    db = next(db_gen)

    try:
        # Get models from DB
        from src.ygo74.fastapi_openai_rag.infrastructure.db.repositories.model_repository import SQLModelRepository
        model_repo = SQLModelRepository(db)

        # Debug: Check all models first
        print(f"\n🔍 Debugging: Fetching ALL models from DB...")
        try:
            all_models_raw = model_repo.get_all()
            print(f"   Total models in DB (get_all): {len(all_models_raw)}")
            for m in all_models_raw[:5]:
                print(f"      - {m.name} / {m.technical_name} / provider={m.provider}")
        except Exception as e:
            print(f"   ❌ Error calling get_all(): {e}")

        # Get approved models (simulating what auth does)
        print(f"\n📥 Fetching approved models for group 'admin'...")

        # Try to find gpt-4o or any GPT-4 model
        gpt4o_models = [m for m in all_models_raw if "gpt-4o" in m.name.lower()]

        if not gpt4o_models:
            print("\n❌ No GPT-4 model found in database!")
            print("💡 Using first available model instead...")
            if not all_models_raw:
                print("❌ No models at all in database! Please run setup script first.")
                return
            gpt4o_models = [all_models_raw[0]]

        selected_model = gpt4o_models[0]
        print(f"\n✅ Using model: {selected_model.name} (technical: {selected_model.technical_name})")

        # Create authenticated user (simulating auth result)
        user = AuthenticatedUser(
            id="1",
            username="admin_user",
            type="api_key",
            groups=["admin"],
            models=all_models_raw  # Pre-loaded models like auth does
        )
        print(f"👤 User: {user.username} with {len(user.models)} models")

        # Create service instance
        session_factory = lambda: db
        uow = SQLUnitOfWork(session_factory)
        service = ChatCompletionService(uow)
        print("✅ ChatCompletionService initialized")

        # Create chat request with image using the selected model
        model_name = selected_model.name
        request = ChatCompletionRequest(
            model=model_name,
            messages=[
                ChatMessage(
                    role="user",
                    content=[
                        {"type": "text", "text": "Describe this image"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                        }
                    ]
                )
            ]
        )
        print(f"📝 Request created: model={request.model}, messages={len(request.messages)}")

        # Measure execution time
        print("\n" + "=" * 80)
        print("🚀 CALLING create_chat_completion()...")
        print("=" * 80)

        start_time = time.perf_counter()

        # Direct service call (no FastAPI, no middlewares, no JSON serialization)
        response = await service.create_chat_completion(request, user)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print("\n" + "=" * 80)
        print(f"✅ RESPONSE RECEIVED IN {elapsed_ms:.2f} ms")
        print("=" * 80)

        # Display response details
        print(f"\n📊 Response details:")
        print(f"   ID: {response.id}")
        print(f"   Model: {response.model}")
        print(f"   Created: {response.created}")
        print(f"   Choices: {len(response.choices)}")

        if response.choices:
            content = response.choices[0].message.content
            print(f"   Content: {content[:100]}..." if content else "   Content: None")

        if response.usage:
            print(f"   Usage: {response.usage.prompt_tokens} prompt + {response.usage.completion_tokens} completion = {response.usage.total_tokens} total")

        # Test serialization time (what FastAPI does)
        print(f"\n📦 Testing Pydantic serialization (FastAPI overhead):")
        serialize_start = time.perf_counter()
        serialized = response.model_dump()
        serialize_time = (time.perf_counter() - serialize_start) * 1000
        print(f"   model_dump(): {serialize_time:.2f} ms")

        json_start = time.perf_counter()
        json_str = response.model_dump_json()
        json_time = (time.perf_counter() - json_start) * 1000
        print(f"   model_dump_json(): {json_time:.2f} ms")
        print(f"   JSON size: {len(json_str)} bytes")

        print("\n" + "=" * 80)
        print(f"⏱️  TOTAL SERVICE TIME: {elapsed_ms:.2f} ms")
        print(f"📦 SERIALIZATION OVERHEAD: {json_time:.2f} ms")
        print(f"🎯 EXPECTED FASTAPI TIME: ~{elapsed_ms + json_time:.2f} ms (sans network)")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_direct_service())
