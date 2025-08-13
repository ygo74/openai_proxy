"""Check Keycloak status and provide troubleshooting information."""
import requests
import subprocess
import logging
import json
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYCLOAK_URL = "http://localhost:8080"

def check_docker_container():
    """Check if Keycloak Docker container is running."""
    try:
        logger.info("🐳 Checking Docker container status...")
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose-backend.yml", "ps"],
            capture_output=True,
            text=True,
            cwd="."
        )

        if result.returncode == 0:
            output = result.stdout
            if "keycloak" in output and "Up" in output:
                logger.info("✅ Keycloak container is running")
                return True
            else:
                logger.warning("⚠️  Keycloak container is not running")
                logger.info("Container status:")
                logger.info(output)
                return False
        else:
            logger.error(f"❌ Failed to check container status: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("❌ Docker not found. Make sure Docker is installed and in PATH")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking container: {e}")
        return False

def check_keycloak_logs():
    """Get Keycloak container logs."""
    try:
        logger.info("📋 Getting Keycloak logs...")
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose-backend.yml", "logs", "--tail", "20", "keycloak"],
            capture_output=True,
            text=True,
            cwd="."
        )

        if result.returncode == 0:
            logger.info("📋 Recent Keycloak logs:")
            print(result.stdout)
            return True
        else:
            logger.error(f"❌ Failed to get logs: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Error getting logs: {e}")
        return False

def test_keycloak_endpoints():
    """Test various Keycloak endpoints."""
    endpoints = [
        (KEYCLOAK_URL + "/", "Main page"),
        (KEYCLOAK_URL + "/realms/master", "Master realm"),
        (KEYCLOAK_URL + "/admin/", "Admin console"),
        (KEYCLOAK_URL + "/realms/master/.well-known/openid_configuration", "OIDC configuration"),
        (KEYCLOAK_URL + "/health", "Health check"),
        (KEYCLOAK_URL + "/health/ready", "Readiness check"),
        (KEYCLOAK_URL + "/health/live", "Liveness check")
    ]

    logger.info("🧪 Testing Keycloak endpoints...")

    for endpoint, description in endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            status = "✅" if response.status_code == 200 else "❌"
            logger.info(f"{status} {description} ({endpoint}): {response.status_code}")

            if response.status_code == 200 and "health" in endpoint:
                try:
                    health_data = response.json()
                    logger.info(f"   📊 Health data: {health_data}")
                except:
                    logger.info("   📊 Health endpoint responded but not JSON")

        except requests.exceptions.ConnectionError:
            logger.error(f"❌ {description} ({endpoint}): Connection refused")
        except requests.exceptions.Timeout:
            logger.error(f"❌ {description} ({endpoint}): Timeout")
        except Exception as e:
            logger.error(f"❌ {description} ({endpoint}): {e}")

def test_admin_token():
    """Test getting admin token."""
    try:
        logger.info("🔑 Testing admin token acquisition...")

        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin"
        }

        response = requests.post(
            f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
            data=data,
            timeout=10
        )

        if response.status_code == 200:
            token_data = response.json()
            logger.info("✅ Admin token obtained successfully")
            logger.info(f"   Token type: {token_data.get('token_type')}")
            logger.info(f"   Expires in: {token_data.get('expires_in')} seconds")
            return True
        else:
            logger.error(f"❌ Failed to get admin token: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Error testing admin token: {e}")
        return False

def main():
    """Main check function."""
    logger.info("🔍 Keycloak Status Checker")
    logger.info("=" * 50)

    # Step 1: Check Docker container
    container_running = check_docker_container()

    # Step 2: Test endpoints
    test_keycloak_endpoints()

    # Step 3: Test admin token
    if container_running:
        test_admin_token()

    # Step 4: Get logs if container is running
    if container_running:
        check_keycloak_logs()

    # Step 5: Provide troubleshooting tips
    logger.info("\n🛠️  Troubleshooting Tips:")
    if not container_running:
        logger.info("1. Start Keycloak: docker compose -f docker-compose-backend.yml up -d")
        logger.info("2. Check if ports are free: netstat -an | findstr :8080")
        logger.info("3. Check Docker: docker ps")
    else:
        logger.info("1. Wait a few more minutes for Keycloak to fully start")
        logger.info("2. Check firewall settings")
        logger.info("3. Try restarting the container: docker compose -f docker-compose-backend.yml restart")

    logger.info("\n📚 Useful Commands:")
    logger.info("- View logs: docker compose -f docker-compose-backend.yml logs -f keycloak")
    logger.info("- Restart: docker compose -f docker-compose-backend.yml restart keycloak")
    logger.info("- Stop/Start: docker compose -f docker-compose-backend.yml down && docker compose -f docker-compose-backend.yml up -d")
    logger.info("- Access admin: http://localhost:8080/admin/ (admin/admin)")

if __name__ == "__main__":
    main()
    main()
