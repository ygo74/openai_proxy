from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError, ExpiredSignatureError
from typing import Optional
import hashlib
import logging
import requests
from .autenticated_user import AuthenticatedUser
from ....infrastructure.db.session import get_db
from ....application.services.user_service import UserService
from ....infrastructure.db.unit_of_work import SQLUnitOfWork

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

JWT_SECRET = "fastapi-secret-key"
JWT_ALGO = "HS256"

# Keycloak configuration - adjust these values to match your setup
KEYCLOAK_URL = "http://localhost:8080"  # Your Keycloak server URL
KEYCLOAK_REALM = "fastapi-openai-rag"        # Your realm name

def get_keycloak_public_key():
    """Retrieve Keycloak's public key for JWT verification"""
    try:
        # Get realm configuration
        realm_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
        response = requests.get(realm_url)
        response.raise_for_status()
        realm_info = response.json()

        # Get public key from realm info
        public_key = realm_info.get("public_key")
        if public_key:
            # Format the key for jose library
            return f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
        else:
            logger.error("No public key found in Keycloak realm configuration")
            return None
    except Exception as e:
        logger.error(f"Failed to retrieve Keycloak public key: {e}")
        return None

async def auth_jwt_or_api_key(
    request: Request,
    api_key_header_value: Optional[str] = Security(api_key_header),
    bearer_token: Optional[str] = Security(bearer_scheme),
    db: Session = Depends(get_db)
):
    user_info = None
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    user_service = UserService(uow)

    # Debug logging
    logger.debug(f"API Key Header: {api_key_header_value}")
    logger.debug(f"Bearer Token: {bearer_token}")

    # 1️⃣ Essai API Key (format attendu: "Bearer sk-xxx" ou juste "sk-xxx")
    if api_key_header_value and (api_key_header_value.startswith("sk-") or api_key_header_value.startswith("Bearer sk-")):
        token = api_key_header_value.replace("Bearer ", "").strip()
        # Hash the token to compare with stored hash
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        logger.debug(f"Looking for API key hash: {key_hash[:10]}...")

        # Find user by API key hash using service
        try:
            with uow as unit_of_work:
                user_repo = user_service._repository_factory(unit_of_work.session)
                user = user_repo.find_by_api_key_hash(key_hash)
                if user:
                    logger.info(f"API key authentication successful for user: {user.username}")
                    user_info = AuthenticatedUser(
                        id=user.id,
                        username=user.username,
                        type="api_key",
                        groups=user.groups
                    )
                else:
                    logger.debug("No user found for API key hash")
        except Exception as e:
            logger.error(f"Error finding user by API key: {e}")

    # 2️⃣ Essai JWT OAuth2
    if not user_info and bearer_token:
        try:
            # Extract token from Bearer scheme
            token_str = bearer_token.credentials
            logger.debug(f"Attempting to decode JWT token: {token_str[:20]}...")

            # First, try to decode without verification to check the algorithm
            unverified_header = jwt.get_unverified_header(token_str)
            algorithm = unverified_header.get("alg", "RS256")
            logger.debug(f"JWT token algorithm: {algorithm}")

            payload = None

            # Try Keycloak JWT validation (RS256) first
            if algorithm == "RS256":
                try:
                    public_key = get_keycloak_public_key()
                    if public_key:
                        payload = jwt.decode(
                            token_str,
                            public_key,
                            algorithms=["RS256"],
                            options={"verify_aud": False}  # Skip audience verification for now
                        )
                        logger.debug(f"Keycloak JWT payload decoded successfully: {payload}")
                except Exception as keycloak_error:
                    logger.debug(f"Keycloak JWT validation failed: {keycloak_error}")

            # Fallback to internal JWT validation (HS256)
            if not payload and algorithm == "HS256":
                try:
                    payload = jwt.decode(
                        token_str,
                        JWT_SECRET,
                        algorithms=[JWT_ALGO],
                        audience="fastapi-openai-rag",
                        issuer="fastapi-openai-rag-debug"
                    )
                    logger.debug(f"Internal JWT payload decoded successfully: {payload}")
                except Exception as internal_error:
                    logger.debug(f"Internal JWT validation failed: {internal_error}")

            if payload:
                # Extract username from different possible JWT claims
                username = (payload.get("preferred_username") or
                           payload.get("username") or
                           payload.get("name") or
                           payload.get("sub"))

                if username:
                    logger.debug(f"JWT contains username: {username}")
                    try:
                        user = user_service.get_user_by_username(username)
                        if user:
                            logger.info(f"JWT authentication successful, found user in DB: {user.username}")
                            user_info = AuthenticatedUser(
                                id=user.id,
                                username=user.username,
                                type="jwt",
                                groups=user.groups
                            )
                        else:
                            logger.debug("User from JWT not found in database")
                    except Exception as e:
                        logger.debug(f"Error finding user from JWT in DB: {e}")

                    # Fallback to JWT claims if user not found in DB
                    if not user_info:
                        logger.info(f"JWT authentication successful, using JWT claims for user: {username}")
                        # Extract groups from different possible JWT claims
                        groups = (payload.get("groups") or
                                 payload.get("realm_access", {}).get("roles", []) or
                                 payload.get("resource_access", {}).get("fastapi-client", {}).get("roles", []) or
                                 [])
                        user_info = AuthenticatedUser(
                            id=payload.get("sub", f"jwt-{username}"),
                            username=username,
                            type="jwt",
                            groups=groups
                        )
                else:
                    logger.debug("No username found in JWT payload")
            else:
                logger.debug("Failed to decode JWT token with any method")

        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise HTTPException(status_code=401, detail="Token expired")
        except JWTError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise HTTPException(status_code=401, detail="Invalid JWT token")
        except Exception as e:
            logger.error(f"Unexpected error during JWT validation: {e}")
            raise HTTPException(status_code=401, detail="Token validation failed")

    if not user_info:
        logger.warning("No valid authentication method found")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 🔹 Injecte dans request.scope pour usage middleware
    request.scope["authenticated_user"] = user_info
    logger.info(f"User authenticated successfully: {user_info.username} ({user_info.type})")
    return user_info
