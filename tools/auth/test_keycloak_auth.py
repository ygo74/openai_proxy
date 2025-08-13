"""Test Keycloak authentication and token generation."""
import requests
import json
import logging
import argparse
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
REALM_NAME = "fastapi-openai-rag"
CLIENT_ID = "fastapi-app"
CLIENT_SECRET = "fastapi-secret-key"
FASTAPI_URL = "http://localhost:8000/v1"

def get_access_token(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Get access token from Keycloak.

    Args:
        username (str): Username
        password (str): Password

    Returns:
        Optional[Dict[str, Any]]: Token data if successful, None otherwise
    """
    try:
        logger.info(f"Getting access token for user: {username}")

        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "password",
            "username": username,
            "password": password
        }

        response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token",
            data=data
        )

        if response.status_code == 200:
            token_data = response.json()
            logger.info("✅ Access token obtained successfully")
            logger.info(f"   Token type: {token_data.get('token_type')}")
            logger.info(f"   Expires in: {token_data.get('expires_in')} seconds")
            return token_data
        else:
            logger.error(f"❌ Failed to get token: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ Error getting token: {e}")
        return None

def test_fastapi_endpoint(token: str, endpoint: str = "/debug/whoami") -> bool:
    """Test FastAPI endpoint with Keycloak token.

    Args:
        token (str): Access token
        endpoint (str): Endpoint to test

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Testing FastAPI endpoint: {endpoint}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(f"{FASTAPI_URL}{endpoint}", headers=headers)

        if response.status_code == 200:
            logger.info("✅ FastAPI endpoint test successful")
            logger.info(f"   Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            logger.error(f"❌ FastAPI endpoint test failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Error testing FastAPI endpoint: {e}")
        return False

def decode_token_info(token: str):
    """Display token information without validation.

    Args:
        token (str): JWT token
    """
    try:
        import base64

        # Split token parts
        parts = token.split(".")
        if len(parts) != 3:
            logger.error("❌ Invalid JWT token format")
            return

        # Decode header
        header = json.loads(base64.b64decode(parts[0] + "=="))

        # Decode payload
        payload = json.loads(base64.b64decode(parts[1] + "=="))

        logger.info("🔍 Token Information:")
        logger.info(f"   Algorithm: {header.get('alg')}")
        logger.info(f"   Type: {header.get('typ')}")
        logger.info(f"   Subject: {payload.get('sub')}")
        logger.info(f"   Username: {payload.get('preferred_username')}")
        logger.info(f"   Email: {payload.get('email')}")
        logger.info(f"   Realm Roles: {payload.get('realm_access', {}).get('roles', [])}")
        logger.info(f"   Audience: {payload.get('aud')}")
        logger.info(f"   Issuer: {payload.get('iss')}")

    except Exception as e:
        logger.error(f"❌ Error decoding token: {e}")

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test Keycloak authentication")
    parser.add_argument("--username", default="admin_user", help="Username (default: admin_user)")
    parser.add_argument("--password", default="admin123", help="Password (default: admin123)")
    parser.add_argument("--endpoint", default="/debug/whoami", help="FastAPI endpoint to test")
    parser.add_argument("--no-test", action="store_true", help="Skip FastAPI endpoint test")

    args = parser.parse_args()

    logger.info("🔐 Keycloak Authentication Test")
    logger.info("=" * 50)

    # Step 1: Get access token
    token_data = get_access_token(args.username, args.password)
    if not token_data:
        return

    access_token = token_data["access_token"]

    # Step 2: Display token info
    logger.info("\n📄 Token Details:")
    decode_token_info(access_token)

    # Step 3: Test FastAPI endpoint
    if not args.no_test:
        logger.info("\n🧪 Testing FastAPI Integration:")
        test_fastapi_endpoint(access_token, args.endpoint)

    # Step 4: Display usage examples
    logger.info("\n📚 Usage Examples:")
    logger.info("Test other endpoints:")
    logger.info(f'curl -H "Authorization: Bearer {access_token[:20]}..." {FASTAPI_URL}/admin/users/')
    logger.info(f'curl -H "Authorization: Bearer {access_token[:20]}..." {FASTAPI_URL}/admin/groups/')

if __name__ == "__main__":
    main()
