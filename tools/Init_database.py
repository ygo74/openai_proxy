"""Database initialization script to create initial user and API key."""
import requests
import json
import logging
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:8000/v1"
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@localhost.com"
ADMIN_GROUPS = ["admin", "users"]

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_user(username: str, email: str, groups: list) -> Optional[Dict[str, Any]]:
    """Create a new user via API.

    Args:
        username (str): Username
        email (str): Email address
        groups (list): List of groups for the user

    Returns:
        Optional[Dict[str, Any]]: User data if successful, None otherwise
    """
    url = f"{BASE_URL}/admin/users/"
    payload = {
        "username": username,
        "email": email,
        "groups": groups
    }

    try:
        logger.info(f"Creating user: {username}")
        response = requests.post(url, json=payload)

        if response.status_code == 201:
            user_data = response.json()
            logger.info(f"User created successfully: ID {user_data['id']}")
            return user_data
        elif response.status_code == 409:
            logger.warning(f"User {username} already exists")
            # Try to get existing user
            return get_user_by_username(username)
        else:
            logger.error(f"Failed to create user: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating user: {e}")
        return None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username via API.

    Args:
        username (str): Username to search for

    Returns:
        Optional[Dict[str, Any]]: User data if found, None otherwise
    """
    url = f"{BASE_URL}/admin/users/username/{username}"

    try:
        logger.info(f"Getting user by username: {username}")
        response = requests.get(url)

        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"User found: ID {user_data['id']}")
            return user_data
        elif response.status_code == 404:
            logger.warning(f"User {username} not found")
            return None
        else:
            logger.error(f"Failed to get user: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting user: {e}")
        return None

def create_api_key(user_id: str, name: str = "Initial API Key") -> Optional[Dict[str, Any]]:
    """Create an API key for a user.

    Args:
        user_id (str): User ID
        name (str): API key name

    Returns:
        Optional[Dict[str, Any]]: API key data if successful, None otherwise
    """
    url = f"{BASE_URL}/admin/users/{user_id}/api-keys"
    payload = {
        "name": name
    }

    try:
        logger.info(f"Creating API key for user {user_id}")
        response = requests.post(url, json=payload)

        if response.status_code == 201:
            api_key_data = response.json()
            logger.info(f"API key created successfully: {api_key_data['key_info']['id']}")
            logger.info(f"🔑 API KEY: {api_key_data['api_key']}")
            logger.info("⚠️  Save this API key! It won't be shown again.")
            return api_key_data
        else:
            logger.error(f"Failed to create API key: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating API key: {e}")
        return None

def create_admin_group() -> Optional[Dict[str, Any]]:
    """Create admin group via API.

    Returns:
        Optional[Dict[str, Any]]: Group data if successful, None otherwise
    """
    url = f"{BASE_URL}/admin/groups/"
    payload = {
        "name": "admin",
        "description": "Administrator group with full access"
    }

    try:
        logger.info("Creating admin group")
        response = requests.post(url, json=payload)

        if response.status_code == 201:
            group_data = response.json()
            logger.info(f"Admin group created successfully: ID {group_data['id']}")
            return group_data
        elif response.status_code == 409:
            logger.warning("Admin group already exists")
            return {"name": "admin"}  # Return minimal data
        else:
            logger.error(f"Failed to create admin group: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating admin group: {e}")
        return None

def create_users_group() -> Optional[Dict[str, Any]]:
    """Create users group via API.

    Returns:
        Optional[Dict[str, Any]]: Group data if successful, None otherwise
    """
    url = f"{BASE_URL}/admin/groups/"
    payload = {
        "name": "users",
        "description": "Standard users group"
    }

    try:
        logger.info("Creating users group")
        response = requests.post(url, json=payload)

        if response.status_code == 201:
            group_data = response.json()
            logger.info(f"Users group created successfully: ID {group_data['id']}")
            return group_data
        elif response.status_code == 409:
            logger.warning("Users group already exists")
            return {"name": "users"}  # Return minimal data
        else:
            logger.error(f"Failed to create users group: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating users group: {e}")
        return None

def check_server_health() -> bool:
    """Check if the server is running and accessible.

    Returns:
        bool: True if server is accessible, False otherwise
    """
    try:
        response = requests.get(f"http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Server is running and accessible")
            return True
        else:
            logger.error(f"Server responded with status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Server is not accessible: {e}")
        logger.error("Please make sure the FastAPI server is running on http://localhost:8000")
        return False

def main():
    """Main initialization function."""
    logger.info("🚀 Starting database initialization...")

    # Check server health first
    if not check_server_health():
        return

    # Step 1: Create groups
    logger.info("\n📁 Creating groups...")
    admin_group = create_admin_group()
    users_group = create_users_group()

    if not admin_group or not users_group:
        logger.error("❌ Failed to create required groups. Aborting.")
        return

    # Step 2: Create admin user
    logger.info("\n👤 Creating admin user...")
    admin_user = create_user(ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_GROUPS)

    if not admin_user:
        logger.error("❌ Failed to create admin user. Aborting.")
        return

    # Step 3: Create API key for admin user
    logger.info("\n🔑 Creating API key for admin user...")
    api_key_data = create_api_key(admin_user['id'], "Admin Initial API Key")

    if not api_key_data:
        logger.error("❌ Failed to create API key.")
        return

    # Summary
    logger.info("\n✅ Database initialization completed successfully!")
    logger.info("=" * 60)
    logger.info(f"Admin User ID: {admin_user['id']}")
    logger.info(f"Admin Username: {admin_user['username']}")
    logger.info(f"Admin Email: {admin_user['email']}")
    logger.info(f"Admin Groups: {admin_user['groups']}")
    logger.info("=" * 60)
    logger.info("🔑 API Key (save this!):")
    logger.info(f"   {api_key_data['api_key']}")
    logger.info("=" * 60)
    logger.info("\nYou can now use this API key to authenticate requests:")
    logger.info(f'curl -H "Authorization: Bearer {api_key_data["api_key"]}" http://localhost:8000/api/v1/admin/users/')
    logger.info("\nOr test with:")
    logger.info("python tools/test_api.py")

if __name__ == "__main__":
    main()