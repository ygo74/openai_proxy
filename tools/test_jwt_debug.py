"""Test and debug JWT tokens."""
import requests
import json
import sys
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime
import logging
from fastapi import HTTPException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/v1"
JWT_SECRET = "SECRET_JWT"  # Same as in auth.py
JWT_ALGO = "HS256"

def decode_token_locally(token: str):
    """Decode JWT token locally for debugging."""
    try:
        print(f"🔍 Decoding token: {token[:20]}...")

        # Try with audience and issuer first
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGO],
                audience="fastapi-openai-rag",
                issuer="fastapi-openai-rag-debug"
            )
        except JWTError as e:
            print(f"⚠️  Failed with audience/issuer validation: {e}")
            print("🔄 Trying without audience/issuer validation...")
            # Fallback without audience/issuer validation
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGO],
                options={"verify_aud": False, "verify_iss": False}
            )

        print("✅ Token decoded successfully!")
        print(f"📄 Payload: {json.dumps(payload, indent=2)}")

        # Check expiration
        if 'exp' in payload:
            exp_time = datetime.fromtimestamp(payload['exp'])
            now = datetime.now()
            print(f"⏰ Expires at: {exp_time}")
            print(f"⏰ Current time: {now}")
            if exp_time > now:
                print("✅ Token is not expired")
            else:
                print("❌ Token is expired!")

        return payload
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid JWT token")
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        raise HTTPException(status_code=401, detail="Token validation failed")

def test_token_with_api(token: str):
    """Test token with the API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("\n🌐 Testing token with API...")

    # Test debug whoami endpoint
    try:
        response = requests.get(f"{BASE_URL}/debug/whoami", headers=headers)
        print(f"📡 /debug/whoami - Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python tools/test_jwt_debug.py <jwt_token>")
        print("\nExample:")
        print("python tools/test_jwt_debug.py eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        return

    token = sys.argv[1]

    print("🔧 JWT Token Debugger")
    print("=" * 50)

    # Test local decoding
    payload = decode_token_locally(token)

    if payload:
        # Test with API
        test_token_with_api(token)

    print("\n✨ Debug completed!")

if __name__ == "__main__":
    main()
