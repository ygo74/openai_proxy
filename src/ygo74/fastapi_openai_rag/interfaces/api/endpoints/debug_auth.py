"""Debug authentication endpoints for development."""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from jose import jwt, JWTError, ExpiredSignatureError
import logging

from ..decorators import endpoint_handler
from ..security.auth import JWT_SECRET, JWT_ALGO, auth_jwt_or_api_key
from ..security.autenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

router = APIRouter()

class TokenRequest(BaseModel):
    """Token generation request."""
    username: str
    groups: List[str] = []
    expires_minutes: int = 60
    sub: Optional[str] = None

class TokenResponse(BaseModel):
    """Token generation response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    groups: List[str]

@router.post("/generate-token", response_model=TokenResponse)
@endpoint_handler("generate_debug_token")
async def generate_debug_token(
    token_request: TokenRequest
) -> TokenResponse:
    """Generate a debug JWT token for development.

    ⚠️ WARNING: This endpoint should ONLY be used in development!

    Args:
        token_request (TokenRequest): Token generation parameters

    Returns:
        TokenResponse: Generated JWT token
    """
    logger.warning("🚨 DEBUG: Generating development JWT token")

    # Create token payload
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=token_request.expires_minutes)

    payload = {
        "sub": token_request.sub or f"debug-{token_request.username}",
        "username": token_request.username,
        "groups": token_request.groups,
        "iat": now.timestamp(),
        "exp": expires_at.timestamp(),
        "iss": "fastapi-openai-rag-debug",
        "aud": "fastapi-openai-rag"
    }

    # Generate token
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

    logger.info(f"Generated debug token for user: {token_request.username}")
    logger.debug(f"Token payload: {payload}")

    return TokenResponse(
        access_token=token,
        expires_in=token_request.expires_minutes * 60,
        username=token_request.username,
        groups=token_request.groups
    )

@router.post("/verify-token")
@endpoint_handler("verify_token")
async def verify_token(
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Dict[str, Any]:
    """Verify and decode the current token.

    Args:
        user (AuthenticatedUser): Authenticated user from token

    Returns:
        Dict[str, Any]: Token verification result
    """
    return {
        "valid": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "type": user.type,
            "groups": user.groups
        },
        "message": "Token is valid"
    }

@router.get("/whoami")
@endpoint_handler("whoami")
async def whoami(
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Dict[str, Any]:
    """Get current user information from token.

    Args:
        user (AuthenticatedUser): Authenticated user

    Returns:
        Dict[str, Any]: Current user information
    """
    return {
        "authenticated": True,
        "user_id": user.id,
        "username": user.username,
        "auth_type": user.type,
        "groups": user.groups
    }

@router.get("/admin-test")
@endpoint_handler("admin_test")
async def admin_test(
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Dict[str, Any]:
    """Test endpoint requiring admin role.

    Args:
        user (AuthenticatedUser): Authenticated user

    Returns:
        Dict[str, Any]: Admin test result

    Raises:
        HTTPException: If user is not admin
    """
    if "admin" not in user.groups:
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin role required."
        )

    return {
        "message": "Admin access granted!",
        "user": user.username,
        "groups": user.groups
    }

@router.get("/decode-token/{token}")
@endpoint_handler("decode_token")
async def decode_token(token: str) -> Dict[str, Any]:
    """Decode a JWT token (for debugging).

    ⚠️ WARNING: This endpoint should ONLY be used in development!

    Args:
        token (str): JWT token to decode

    Returns:
        Dict[str, Any]: Decoded token payload
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        logger.info(f"Successfully decoded token for user: {payload.get('username')}")
        return {
            "valid": True,
            "payload": payload,
            "expires_at": datetime.fromtimestamp(payload.get('exp', 0)).isoformat() if payload.get('exp') else None
        }
    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid JWT token")
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}")
        raise HTTPException(status_code=401, detail="Token validation failed")
