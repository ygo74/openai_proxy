"""Setup Keycloak configuration for FastAPI OpenAI RAG application."""
import requests
import json
import logging
import time
from typing import Dict, Any, Optional, List

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keycloak configuration
KEYCLOAK_URL = "http://localhost:8080"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
REALM_NAME = "fastapi-openai-rag"
CLIENT_ID = "fastapi-app"
CLIENT_SECRET = "fastapi-secret-key"

# Test users
TEST_USERS = [
    {
        "username": "admin_user",
        "email": "admin@example.com",
        "firstName": "Admin",
        "lastName": "User",
        "password": "admin123",
        "roles": ["admin", "user"]
    },
    {
        "username": "regular_user",
        "email": "user@example.com",
        "firstName": "Regular",
        "lastName": "User",
        "password": "user123",
        "roles": ["user"]
    },
    {
        "username": "test_user",
        "email": "test@example.com",
        "firstName": "Test",
        "lastName": "User",
        "password": "test123",
        "roles": ["user"]
    }
]

class KeycloakAdmin:
    """Keycloak administration client."""

    def __init__(self, base_url: str, username: str, password: str):
        """Initialize Keycloak admin client.

        Args:
            base_url (str): Keycloak base URL
            username (str): Admin username
            password (str): Admin password
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None

    def wait_for_keycloak(self, timeout: int = 60) -> bool:
        """Wait for Keycloak to be ready.

        Args:
            timeout (int): Timeout in seconds

        Returns:
            bool: True if Keycloak is ready, False otherwise
        """
        logger.info("Waiting for Keycloak to be ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Try the health endpoints on port 8080
                response = requests.get(f"{self.base_url}/health", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Keycloak health endpoint is accessible!")
                    return True

                # Try readiness endpoint
                response = requests.get(f"{self.base_url}/health/ready", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Keycloak readiness endpoint is accessible!")
                    return True

                # Try liveness endpoint
                response = requests.get(f"{self.base_url}/health/live", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Keycloak liveness endpoint is accessible!")
                    return True

                # Fallback to main endpoint
                response = requests.get(f"{self.base_url}/", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Keycloak main endpoint is accessible!")

                    # Also try the realms endpoint to make sure it's fully ready
                    try:
                        realms_response = requests.get(f"{self.base_url}/realms/master", timeout=5)
                        if realms_response.status_code == 200:
                            logger.info("✅ Keycloak is fully ready!")
                            return True
                    except requests.exceptions.RequestException:
                        logger.info("⏳ Keycloak starting up, waiting for realms...")

            except requests.exceptions.RequestException as e:
                logger.debug(f"Connection attempt failed: {e}")

            logger.info("⏳ Waiting for Keycloak...")
            time.sleep(5)

        logger.error("❌ Keycloak is not ready after timeout")
        logger.error("💡 Make sure Keycloak is running with: docker compose -f docker-compose-backend.yml up -d")
        logger.error("💡 Check Keycloak logs with: docker compose -f docker-compose-backend.yml logs keycloak")
        logger.error("💡 Try manual health check: curl http://localhost:8080/health")
        return False

    def get_admin_token(self) -> bool:
        """Get admin access token.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Getting admin access token...")
            data = {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.username,
                "password": self.password
            }

            response = requests.post(
                f"{self.base_url}/realms/master/protocol/openid-connect/token",
                data=data
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                logger.info("✅ Admin token obtained successfully")
                return True
            else:
                logger.error(f"❌ Failed to get admin token: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error getting admin token: {e}")
            return False

    def make_admin_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> requests.Response:
        """Make authenticated admin request.

        Args:
            method (str): HTTP method
            endpoint (str): API endpoint
            data (Optional[Dict]): Request data

        Returns:
            requests.Response: Response object
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        url = f"{self.base_url}/admin/realms{endpoint}"

        if method.upper() == "GET":
            return requests.get(url, headers=headers)
        elif method.upper() == "POST":
            return requests.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            return requests.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            return requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

    def create_realm(self, realm_name: str) -> bool:
        """Create a new realm.

        Args:
            realm_name (str): Name of the realm

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Creating realm: {realm_name}")

            # Check if realm already exists
            response = self.make_admin_request("GET", f"/{realm_name}")
            if response.status_code == 200:
                logger.info(f"⚠️  Realm {realm_name} already exists")
                return True

            realm_data = {
                "realm": realm_name,
                "displayName": "FastAPI OpenAI RAG",
                "enabled": True,
                "registrationAllowed": True,
                "loginWithEmailAllowed": True,
                "duplicateEmailsAllowed": False,
                "resetPasswordAllowed": True,
                "editUsernameAllowed": True,
                "bruteForceProtected": True
            }

            response = self.make_admin_request("POST", "", realm_data)

            if response.status_code == 201:
                logger.info(f"✅ Realm {realm_name} created successfully")
                return True
            else:
                logger.error(f"❌ Failed to create realm: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error creating realm: {e}")
            return False

    def create_client(self, realm_name: str, client_id: str, client_secret: str) -> bool:
        """Create a client in the realm.

        Args:
            realm_name (str): Realm name
            client_id (str): Client ID
            client_secret (str): Client secret

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Creating client: {client_id}")

            client_data = {
                "clientId": client_id,
                "name": "FastAPI Application",
                "description": "FastAPI OpenAI RAG Application Client",
                "enabled": True,
                "clientAuthenticatorType": "client-secret",
                "secret": client_secret,
                "redirectUris": ["http://localhost:8000/*"],
                "webOrigins": ["http://localhost:8000"],
                "protocol": "openid-connect",
                "publicClient": False,
                "bearerOnly": False,
                "consentRequired": False,
                "standardFlowEnabled": True,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": True,
                "serviceAccountsEnabled": True,
                "authorizationServicesEnabled": True,
                "defaultClientScopes": ["web-origins", "role_list", "profile", "roles", "email"],
                "optionalClientScopes": ["address", "phone", "offline_access", "microprofile-jwt"]
            }

            response = self.make_admin_request("POST", f"/{realm_name}/clients", client_data)

            if response.status_code == 201:
                logger.info(f"✅ Client {client_id} created successfully")
                return True
            else:
                logger.error(f"❌ Failed to create client: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error creating client: {e}")
            return False

    def create_realm_roles(self, realm_name: str, roles: List[str]) -> bool:
        """Create realm roles.

        Args:
            realm_name (str): Realm name
            roles (List[str]): List of role names

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Creating realm roles: {roles}")

            for role in roles:
                role_data = {
                    "name": role,
                    "description": f"Role for {role} users",
                    "composite": False
                }

                response = self.make_admin_request("POST", f"/{realm_name}/roles", role_data)

                if response.status_code == 201:
                    logger.info(f"✅ Role {role} created successfully")
                elif response.status_code == 409:
                    logger.info(f"⚠️  Role {role} already exists")
                else:
                    logger.error(f"❌ Failed to create role {role}: {response.status_code} - {response.text}")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Error creating roles: {e}")
            return False

    def create_user(self, realm_name: str, user_data: Dict[str, Any]) -> bool:
        """Create a user in the realm.

        Args:
            realm_name (str): Realm name
            user_data (Dict[str, Any]): User data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            username = user_data["username"]
            logger.info(f"Creating user: {username}")

            keycloak_user = {
                "username": username,
                "email": user_data["email"],
                "firstName": user_data["firstName"],
                "lastName": user_data["lastName"],
                "enabled": True,
                "emailVerified": True,
                "credentials": [{
                    "type": "password",
                    "value": user_data["password"],
                    "temporary": False
                }]
            }

            response = self.make_admin_request("POST", f"/{realm_name}/users", keycloak_user)

            if response.status_code == 201:
                logger.info(f"✅ User {username} created successfully")

                # Get user ID from location header
                user_id = response.headers["Location"].split("/")[-1]

                # Assign roles
                return self.assign_user_roles(realm_name, user_id, user_data["roles"])
            elif response.status_code == 409:
                logger.info(f"⚠️  User {username} already exists")
                return True
            else:
                logger.error(f"❌ Failed to create user {username}: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            return False

    def assign_user_roles(self, realm_name: str, user_id: str, roles: List[str]) -> bool:
        """Assign roles to a user.

        Args:
            realm_name (str): Realm name
            user_id (str): User ID
            roles (List[str]): List of role names

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Assigning roles {roles} to user {user_id}")

            # Get available realm roles
            response = self.make_admin_request("GET", f"/{realm_name}/roles")
            if response.status_code != 200:
                logger.error(f"❌ Failed to get realm roles: {response.status_code}")
                return False

            available_roles = response.json()
            role_mappings = []

            for role_name in roles:
                role_obj = next((r for r in available_roles if r["name"] == role_name), None)
                if role_obj:
                    role_mappings.append({
                        "id": role_obj["id"],
                        "name": role_obj["name"]
                    })

            if role_mappings:
                response = self.make_admin_request(
                    "POST",
                    f"/{realm_name}/users/{user_id}/role-mappings/realm",
                    role_mappings
                )

                if response.status_code == 204:
                    logger.info("✅ Roles assigned successfully")
                    return True
                else:
                    logger.error(f"❌ Failed to assign roles: {response.status_code} - {response.text}")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Error assigning roles: {e}")
            return False

def main():
    """Main setup function."""
    logger.info("🚀 Starting Keycloak setup...")
    logger.info("=" * 60)

    admin = KeycloakAdmin(KEYCLOAK_URL, ADMIN_USERNAME, ADMIN_PASSWORD)

    # Step 1: Wait for Keycloak
    if not admin.wait_for_keycloak():
        logger.error("❌ Keycloak setup failed - server not ready")
        return

    # Step 2: Get admin token
    if not admin.get_admin_token():
        logger.error("❌ Keycloak setup failed - cannot get admin token")
        return

    # Step 3: Create realm
    if not admin.create_realm(REALM_NAME):
        logger.error("❌ Keycloak setup failed - cannot create realm")
        return

    # Step 4: Create realm roles
    roles = ["admin", "user"]
    if not admin.create_realm_roles(REALM_NAME, roles):
        logger.error("❌ Keycloak setup failed - cannot create roles")
        return

    # Step 5: Create client
    if not admin.create_client(REALM_NAME, CLIENT_ID, CLIENT_SECRET):
        logger.error("❌ Keycloak setup failed - cannot create client")
        return

    # Step 6: Create test users
    logger.info("\n👥 Creating test users...")
    all_users_created = True
    for user_data in TEST_USERS:
        if not admin.create_user(REALM_NAME, user_data):
            all_users_created = False

    if not all_users_created:
        logger.error("❌ Some users could not be created")
        return

    # Success summary
    logger.info("\n✅ Keycloak setup completed successfully!")
    logger.info("=" * 60)
    logger.info(f"🏰 Realm: {REALM_NAME}")
    logger.info(f"🔑 Client ID: {CLIENT_ID}")
    logger.info(f"🔐 Client Secret: {CLIENT_SECRET}")
    logger.info(f"🌐 Keycloak URL: {KEYCLOAK_URL}")
    logger.info(f"🔗 Realm URL: {KEYCLOAK_URL}/realms/{REALM_NAME}")
    logger.info(f"🔗 Admin Console: {KEYCLOAK_URL}/admin/")

    logger.info("\n👥 Test Users Created:")
    for user in TEST_USERS:
        logger.info(f"   Username: {user['username']} | Password: {user['password']} | Roles: {user['roles']}")

    logger.info("\n📚 Next Steps:")
    logger.info("1. Update your FastAPI configuration with the client credentials")
    logger.info("2. Test authentication with the created users")
    logger.info("3. Use the JWT tokens for API access")

    # Generate sample JWT request
    logger.info(f"\n🧪 Test token generation:")
    logger.info(f"curl -X POST '{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token' \\")
    logger.info(f"  -H 'Content-Type: application/x-www-form-urlencoded' \\")
    logger.info(f"  -d 'client_id={CLIENT_ID}' \\")
    logger.info(f"  -d 'client_secret={CLIENT_SECRET}' \\")
    logger.info(f"  -d 'grant_type=password' \\")
    logger.info(f"  -d 'username=admin_user' \\")
    logger.info(f"  -d 'password=admin123'")

if __name__ == "__main__":
    main()
