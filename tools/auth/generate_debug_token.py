"""Generate debug JWT tokens for development."""
import argparse
import requests
import json
import logging
from typing import List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/v1"

def generate_token(
    username: str,
    groups: List[str] = None,
    expires_minutes: int = 60,
    sub: Optional[str] = None
) -> dict:
    """Generate a debug JWT token via API.

    Args:
        username (str): Username for the token
        groups (List[str]): List of groups/roles
        expires_minutes (int): Token expiration in minutes
        sub (Optional[str]): Subject claim

    Returns:
        dict: Token response
    """
    url = f"{BASE_URL}/debug/generate-token"
    payload = {
        "username": username,
        "groups": groups or [],
        "expires_minutes": expires_minutes
    }

    if sub:
        payload["sub"] = sub

    try:
        logger.info(f"Generating token for user: {username}")
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            token_data = response.json()
            logger.info("✅ Token generated successfully!")
            return token_data
        else:
            logger.error(f"❌ Failed to generate token: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error generating token: {e}")
        return None

def test_token(token: str):
    """Test a JWT token via API.

    Args:
        token (str): JWT token to test
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Test whoami endpoint
    try:
        logger.info("Testing token with /debug/whoami")
        response = requests.get(f"{BASE_URL}/debug/whoami", headers=headers)
        if response.status_code == 200:
            user_info = response.json()
            logger.info(f"✅ Token valid - User: {user_info['username']}, Groups: {user_info['groups']}")
        else:
            logger.error(f"❌ Token test failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error testing token: {e}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate debug JWT tokens")
    parser.add_argument("username", help="Username for the token")
    parser.add_argument("--groups", nargs="*", default=["user"], help="Groups/roles (default: user)")
    parser.add_argument("--expires", type=int, default=60, help="Token expiration in minutes (default: 60)")
    parser.add_argument("--sub", help="Subject claim (optional)")
    parser.add_argument("--test", action="store_true", help="Test the generated token")

    args = parser.parse_args()

    logger.info("🔑 Debug JWT Token Generator")
    logger.info("=" * 50)

    # Generate token
    token_data = generate_token(
        username=args.username,
        groups=args.groups,
        expires_minutes=args.expires,
        sub=args.sub
    )

    if not token_data:
        return

    # Display results
    logger.info("\n📄 Token Details:")
    logger.info(f"   Username: {token_data['username']}")
    logger.info(f"   Groups: {token_data['groups']}")
    logger.info(f"   Expires in: {token_data['expires_in']} seconds")
    logger.info("\n🔑 JWT Token:")
    logger.info(f"   {token_data['access_token']}")

    # Test token if requested
    if args.test:
        logger.info("\n🧪 Testing token...")
        test_token(token_data['access_token'])

    # Usage examples
    logger.info("\n📚 Usage Examples:")
    logger.info(f'   curl -H "Authorization: Bearer {token_data["access_token"]}" {BASE_URL}/debug/whoami')
    logger.info(f'   curl -H "Authorization: Bearer {token_data["access_token"]}" {BASE_URL}/admin/users/')

if __name__ == "__main__":
    main()
