"""Test script to verify API functionality with generated API key."""
import requests
import json
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/v1"

def test_api_key(api_key: str):
    """Test API endpoints with the provided API key.

    Args:
        api_key (str): API key to test
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    logger.info("🔍 Testing API endpoints...")

    # Test 1: Get users
    try:
        logger.info("Testing GET /admin/users/")
        response = requests.get(f"{BASE_URL}/admin/users/", headers=headers)
        if response.status_code == 200:
            users = response.json()
            logger.info(f"✅ GET /admin/users/ - Found {len(users)} users")
        else:
            logger.error(f"❌ GET /admin/users/ failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ GET /admin/users/ error: {e}")

    # Test 2: Get groups
    try:
        logger.info("Testing GET /admin/groups/")
        response = requests.get(f"{BASE_URL}/admin/groups/", headers=headers)
        if response.status_code == 200:
            groups = response.json()
            logger.info(f"✅ GET /admin/groups/ - Found {len(groups)} groups")
        else:
            logger.error(f"❌ GET /admin/groups/ failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ GET /admin/groups/ error: {e}")

    # Test 3: Get user statistics
    try:
        logger.info("Testing GET /admin/users/statistics")
        response = requests.get(f"{BASE_URL}/admin/users/statistics", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            logger.info(f"✅ GET /admin/users/statistics - {stats}")
        else:
            logger.error(f"❌ GET /admin/users/statistics failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ GET /admin/users/statistics error: {e}")

def main():
    """Main test function."""
    if len(sys.argv) != 2:
        logger.error("Usage: python tools/test_api.py <api_key>")
        logger.info("Example: python tools/test_api.py sk-abc123...")
        return

    api_key = sys.argv[1]
    logger.info(f"Testing with API key: {api_key[:10]}...")

    test_api_key(api_key)

    logger.info("\n🎉 API testing completed!")

if __name__ == "__main__":
    main()
