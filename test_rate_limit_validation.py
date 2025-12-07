"""Test rate limit validation via Python requests."""
import requests
import json

base_url = "http://localhost:8000"

# Test 1: Valid non-overlapping windows (should succeed)
print("Test 1: Valid non-overlapping windows")
valid_payload = {
    "scope_type": "model",
    "scope_id": 999,
    "enabled": True,
    "windows": [
        {
            "from_time": "00:00:00",
            "to_time": "12:00:00",
            "max_requests": 100,
            "max_tokens": 10000
        },
        {
            "from_time": "12:00:00",
            "to_time": "23:59:59",
            "max_requests": 200,
            "max_tokens": 20000
        }
    ]
}

try:
    response = requests.post(
        f"{base_url}/admin/rate-limits",
        json=valid_payload,
        verify=False
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*80 + "\n")

# Test 2: Overlapping windows (should fail)
print("Test 2: Overlapping windows (should fail)")
overlap_payload = {
    "scope_type": "model",
    "scope_id": 998,
    "enabled": True,
    "windows": [
        {
            "from_time": "00:00:00",
            "to_time": "23:59:59",
            "max_requests": 100,
            "max_tokens": 10000
        },
        {
            "from_time": "00:00:00",
            "to_time": "23:59:59",
            "max_requests": 100,
            "max_tokens": 10000
        }
    ]
}

try:
    response = requests.post(
        f"{base_url}/admin/rate-limits",
        json=overlap_payload,
        verify=False
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*80 + "\n")

# Test 3: Partial overlap (should fail)
print("Test 3: Partial overlap (should fail)")
partial_overlap_payload = {
    "scope_type": "model",
    "scope_id": 997,
    "enabled": True,
    "windows": [
        {
            "from_time": "00:00:00",
            "to_time": "18:00:00",
            "max_requests": 100,
            "max_tokens": 10000
        },
        {
            "from_time": "12:00:00",
            "to_time": "23:59:59",
            "max_requests": 200,
            "max_tokens": 20000
        }
    ]
}

try:
    response = requests.post(
        f"{base_url}/admin/rate-limits",
        json=partial_overlap_payload,
        verify=False
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
