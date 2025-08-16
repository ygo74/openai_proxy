from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError, ExpiredSignatureError
from typing import Optional
import hashlib
import logging
import requests
import os
import time
from cachetools import TTLCache
from .autenticated_user import AuthenticatedUser
from ....infrastructure.db.session import get_db
from ....application.services.user_service import UserService
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....config.settings import settings
from ....infrastructure.llm.retry_handler import KeycloakRetryHandler

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

# --- Keycloak public key cache (cachetools TTL) --------------------------------
_KEYCLOAK_JWKS_CACHE_TTL_SECONDS: int = int(os.getenv("KEYCLOAK_JWKS_CACHE_TTL", "3600"))
_keycloak_pubkey_cache: TTLCache[str, str] = TTLCache(maxsize=16, ttl=_KEYCLOAK_JWKS_CACHE_TTL_SECONDS)

# Create a reusable retry handler instance (sync for requests)
_keycloak_retry_handler = KeycloakRetryHandler()

@_keycloak_retry_handler.create_sync_retry_decorator()
def _fetch_keycloak_realm_config(realm_url: str) -> dict:
    """Fetch Keycloak realm configuration with retry.

    Args:
        realm_url: Realm discovery endpoint URL

    Returns:
        dict: Realm configuration JSON
    """
    resp = requests.get(realm_url, timeout=5)
    resp.raise_for_status()
    return resp.json()

def get_keycloak_public_key(kid: Optional[str] = None) -> Optional[str]:
    """Retrieve Keycloak's public key for JWT verification with TTL cache.

    Args:
        kid: Optional JWT key id (reserved for future JWKS usage)

    Returns:
        PEM-formatted public key or None if retrieval fails
    """
    cache_key = f"{settings.auth.keycloak_url.rstrip('/')}/realms/{settings.auth.keycloak_realm}"
    try:
        cached = _keycloak_pubkey_cache.get(cache_key)
        if cached:
            return cached

        realm_info = _fetch_keycloak_realm_config(cache_key)

        public_key: Optional[str] = realm_info.get("public_key")
        if not public_key:
            logger.error("No public key found in Keycloak realm configuration")
            return _keycloak_pubkey_cache.get(cache_key)

        pem: str = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
        _keycloak_pubkey_cache[cache_key] = pem
        logger.debug("Fetched and cached Keycloak public key from realm endpoint")
        return pem

    except Exception as e:
        logger.error(f"Failed to retrieve Keycloak public key: {e}")
        stale = _keycloak_pubkey_cache.get(cache_key)
        if stale:
            logger.warning("Using stale cached Keycloak public key due to fetch error")
        return stale


async def _authenticate_with_api_key(
    api_key_header_value: str,
    user_service: UserService
) -> Optional[AuthenticatedUser]:
    """
    Authenticate user using API key from Authorization header.

    Args:
        api_key_header_value: The API key value from Authorization header
        user_service: Service to handle user operations

    Returns:
        AuthenticatedUser if authentication successful, None otherwise
    """
    if not (api_key_header_value.startswith("sk-") or api_key_header_value.startswith("Bearer sk-")):
        return None

    token = api_key_header_value.replace("Bearer ", "").strip()
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    logger.debug(f"Looking for API key hash: {key_hash[:10]}...")

    try:
        user = user_service.get_user_by_api_key_hash(key_hash)
        if user:
            logger.info(f"API key authentication successful for user: {user.username}")
            return AuthenticatedUser(
                id=user.id,
                username=user.username,
                type="api_key",
                groups=user.groups
            )
        else:
            logger.debug("No user found for API key hash")
            return None
    except Exception as e:
        logger.error(f"Error finding user by API key: {e}")
        return None

async def _decode_jwt_token(token_str: str) -> Optional[dict]:
    """
    Decode JWT token using appropriate algorithm and key.

    Args:
        token_str: The JWT token string to decode

    Returns:
        Decoded payload dict if successful, None otherwise
    """
    try:
        unverified_header = jwt.get_unverified_header(token_str)
        algorithm = unverified_header.get("alg", "RS256")
        kid: Optional[str] = unverified_header.get("kid")
        logger.debug(f"JWT token algorithm: {algorithm}, kid: {kid}")

        # Try Keycloak JWT validation (RS256) first
        if algorithm == "RS256":
            try:
                public_key = get_keycloak_public_key(kid=kid)
                if public_key:
                    # Build verification options
                    options = {"verify_aud": False}
                    if not settings.auth.oauth_audience:
                        options["verify_aud"] = False

                    # Build decode parameters
                    decode_params = {
                        "token": token_str,
                        "key": public_key,
                        "algorithms": ["RS256"],
                        "options": options
                    }

                    # Add audience if configured
                    if settings.auth.oauth_audience:
                        decode_params["audience"] = settings.auth.oauth_audience

                    # Add issuer if configured
                    if settings.auth.oauth_issuer:
                        decode_params["issuer"] = settings.auth.oauth_issuer

                    payload = jwt.decode(**decode_params)
                    logger.debug("Keycloak JWT payload decoded successfully")
                    return payload
            except Exception as keycloak_error:
                logger.debug(f"Keycloak JWT validation failed: {keycloak_error}")

        # Fallback to internal JWT validation (HS256)
        if algorithm == "HS256":
            try:
                decode_params = {
                    "token": token_str,
                    "key": settings.auth.jwt_secret,
                    "algorithms": [settings.auth.jwt_algorithm]
                }

                # Add audience and issuer for internal tokens
                if settings.auth.oauth_audience:
                    decode_params["audience"] = settings.auth.oauth_audience
                if settings.auth.oauth_issuer:
                    decode_params["issuer"] = settings.auth.oauth_issuer

                payload = jwt.decode(**decode_params)
                logger.debug(f"Internal JWT payload decoded successfully")
                return payload
            except Exception as internal_error:
                logger.debug(f"Internal JWT validation failed: {internal_error}")

        return None
    except Exception as e:
        logger.error(f"Error decoding JWT token: {e}")
        return None

async def _authenticate_with_jwt_payload(
    payload: dict,
    user_service: UserService
) -> Optional[AuthenticatedUser]:
    """
    Create AuthenticatedUser from JWT payload.

    Args:
        payload: Decoded JWT payload
        user_service: Service to handle user operations

    Returns:
        AuthenticatedUser if successful, None otherwise
    """
    # Extract username from different possible JWT claims
    username = (payload.get("preferred_username") or
               payload.get("username") or
               payload.get("name") or
               payload.get("sub"))

    if not username:
        logger.debug("No username found in JWT payload")
        return None

    logger.debug(f"JWT contains username: {username}")

    # Try to find user in database first
    try:
        user = user_service.get_user_by_username(username)
        if user:
            logger.info(f"JWT authentication successful, found user in DB: {user.username}")
            return AuthenticatedUser(
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
    logger.info(f"JWT authentication successful, using JWT claims for user: {username}")
    # Extract groups from different possible JWT claims
    groups = (payload.get("groups") or
             payload.get("realm_access", {}).get("roles", []) or
             payload.get("resource_access", {}).get("fastapi-client", {}).get("roles", []) or
             [])

    return AuthenticatedUser(
        id=payload.get("sub", f"jwt-{username}"),
        username=username,
        type="jwt",
        groups=groups
    )

async def _authenticate_with_bearer_token(
    bearer_token: str,
    user_service: UserService
) -> Optional[AuthenticatedUser]:
    """
    Authenticate user using JWT Bearer token.

    Args:
        bearer_token: The bearer token credentials
        user_service: Service to handle user operations

    Returns:
        AuthenticatedUser if authentication successful, None otherwise
    """
    try:
        logger.debug(f"Attempting to decode JWT token: {bearer_token[:20]}...")

        # Decode the JWT token
        payload = await _decode_jwt_token(bearer_token)
        if not payload:
            logger.debug("Failed to decode JWT token with any method")
            return None

        # Create authenticated user from payload
        return await _authenticate_with_jwt_payload(payload, user_service)

    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid JWT token")
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        raise HTTPException(status_code=401, detail="Token validation failed")

async def auth_jwt_or_api_key(
    request: Request,
    api_key_header_value: Optional[str] = Security(api_key_header),
    bearer_token: Optional[str] = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> AuthenticatedUser:
    """
    Authenticate user using either API key or JWT Bearer token.

    Args:
        request: FastAPI request object
        api_key_header_value: API key from Authorization header
        bearer_token: Bearer token from Authorization header
        db: Database session

    Returns:
        AuthenticatedUser instance

    Raises:
        HTTPException: If authentication fails
    """
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    user_service = UserService(uow)

    # Debug logging
    logger.debug(f"API Key Header: {api_key_header_value}")
    logger.debug(f"Bearer Token: {bearer_token}")

    user_info = None

    # 1️⃣ Try API Key authentication
    if api_key_header_value:
        user_info = await _authenticate_with_api_key(api_key_header_value, user_service)

    # 2️⃣ Try JWT Bearer token authentication
    if not user_info and bearer_token:
        user_info = await _authenticate_with_bearer_token(bearer_token.credentials, user_service)

    if not user_info:
        logger.warning("No valid authentication method found")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 🔹 Injecte dans request.scope pour usage middleware
    request.scope["authenticated_user"] = user_info
    logger.info(f"User authenticated successfully: {user_info.username} ({user_info.type})")
    return user_info
    user_info = None

    # 1️⃣ Try API Key authentication
    if api_key_header_value:
        user_info = await _authenticate_with_api_key(api_key_header_value, user_service)

    # 2️⃣ Try JWT Bearer token authentication
    if not user_info and bearer_token:
        user_info = await _authenticate_with_bearer_token(bearer_token.credentials, user_service)

    if not user_info:
        logger.warning("No valid authentication method found")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 🔹 Injecte dans request.scope pour usage middleware
    request.scope["authenticated_user"] = user_info
    logger.info(f"User authenticated successfully: {user_info.username} ({user_info.type})")
    return user_info
