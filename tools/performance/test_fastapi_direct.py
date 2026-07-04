"""Test FastAPI app directly (no network, no Uvicorn) to measure pure framework overhead."""
import asyncio
import time
import json
import base64
from pathlib import Path
import httpx
from dotenv import load_dotenv
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load environment
load_dotenv()

async def test_direct_fastapi():
    """Test FastAPI application directly via ASGI without network stack."""

    # Import app (this initializes everything)
    from src.ygo74.fastapi_openai_rag.main import app

    # Load image
    image_path = Path("C:/Users/Administrator/OneDrive/Images/226px-Jenkins_logo.svg.png")
    image_bytes = image_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    print(f"📸 Image loaded: {len(image_base64)} bytes (base64)")

    # Prepare payload
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
    }

    headers = {
        "Authorization": "Bearer sk-920xAa9zy_C8jixH9Q-9Jdp09_y7RxjXRTKK39HHp54",
        "Content-Type": "application/json"
    }

    print("\n⏱️  Starting DIRECT FastAPI test (no network)...")
    print("=" * 60)

    # Create ASGI client (direct in-memory communication, no TCP/IP)
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        start = time.perf_counter()

        response = await client.post(
            "/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=120.0
        )

        end = time.perf_counter()
        total_time = (end - start) * 1000

        print(f"✅ Response received!")
        print(f"📊 Status: {response.status_code}")
        print(f"⏱️  Total time (FastAPI + processing): {total_time:.2f}ms")
        print(f"📏 Content length: {len(response.content)} bytes")

        if response.status_code == 200:
            data = response.json()
            print(f"🤖 Model: {data.get('model')}")
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"💬 Content preview: {content[:100]}...")
        else:
            print(f"❌ Error: {response.text}")

        print("=" * 60)
        print(f"\n🔍 ANALYSIS:")
        print(f"   Direct FastAPI time: {total_time:.2f}ms")
        print(f"   Expected service time: ~1900-2000ms (from logs)")
        print(f"   FastAPI overhead: {total_time - 1950:.2f}ms")
        print(f"   (Includes: routing, middleware, Pydantic validation, response building)")

if __name__ == "__main__":
    asyncio.run(test_direct_fastapi())
