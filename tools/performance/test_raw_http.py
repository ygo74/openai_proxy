"""Test HTTP pur sans SDK OpenAI pour mesurer latence réseau."""
import httpx
import time
import json
import base64
import sys

def local_image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def test_raw_http(image_path: str):
    """Test avec httpx pur (pas de SDK OpenAI)."""

    # Prepare payload
    image_b64 = local_image_to_base64(image_path)
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    }
                ]
            }
        ]
    }

    headers = {
        "Authorization": "Bearer sk-920xAa9zy_C8jixH9Q-9Jdp09_y7RxjXRTKK39HHp54",
        "Content-Type": "application/json"
    }

    # Measure with connection reuse (like SDK should do)
    with httpx.Client(timeout=30.0, http2=True) as client:
        # Warmup (establish connection)
        print("🔥 Warmup request...")
        try:
            warmup_start = time.perf_counter()
            warmup_resp = client.post(
                "http://localhost:8000/v1/chat/completions",
                json=payload,
                headers=headers
            )
            warmup_time = (time.perf_counter() - warmup_start) * 1000
            print(f"   Warmup: {warmup_time:.2f} ms (status: {warmup_resp.status_code})")
        except Exception as e:
            print(f"   Warmup failed: {e}")

        # Real test (connection already open)
        print("\n🚀 Real request (connection reused)...")
        start = time.perf_counter()
        response = client.post(
            "http://localhost:8000/v1/chat/completions",
            json=payload,
            headers=headers
        )
        total_time = (time.perf_counter() - start) * 1000

        print(f"   Total time: {total_time:.2f} ms")
        print(f"   Status: {response.status_code}")
        print(f"   Response size: {len(response.content)} bytes")

        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"   Content preview: {content[:100]}...")

    # Test without connection reuse (new connection each time - like SDK bug?)
    print("\n❄️ Cold request (new connection)...")
    cold_start = time.perf_counter()
    cold_response = httpx.post(
        "http://localhost:8000/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30.0
    )
    cold_time = (time.perf_counter() - cold_start) * 1000
    print(f"   Cold time: {cold_time:.2f} ms")

if __name__ == "__main__":
    image_path = r"C:\Users\Administrator\OneDrive\Images\226px-Jenkins_logo.svg.png"
    test_raw_http(image_path)
