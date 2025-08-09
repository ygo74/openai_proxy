from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from jose import jwt, JWTError
from typing import Optional
from .autenticated_user import AuthenticatedUser

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

API_KEYS = {"sk-test-123": {"id": "user123", "username": "api_client"}}
JWT_SECRET = "SECRET_JWT"
JWT_ALGO = "HS256"

async def auth_jwt_or_api_key(
    request: Request,
    api_key_header_value: Optional[str] = Security(api_key_header),
    bearer_token: Optional[str] = Security(bearer_scheme)
):
    user_info = None

    # 1️⃣ Essai API Key (format attendu: "Bearer sk-xxx" ou juste "sk-xxx")
    if api_key_header_value:
        token = api_key_header_value.replace("Bearer ", "").strip()
        if token in API_KEYS:
            data = API_KEYS[token]
            user_info = AuthenticatedUser(
                id=data["id"],
                username=data["username"],
                type="api_key",
                groups=["default"]
            )

    # 2️⃣ Essai JWT OAuth2
    if not user_info and bearer_token:
        try:
            payload = jwt.decode(bearer_token.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
            user_info = AuthenticatedUser(
                id=payload.get("sub"),
                username=payload.get("username"),
                type="jwt",
                groups=payload.get("groups", [])
            )
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid JWT token")

    if not user_info:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 🔹 Injecte dans request.scope pour usage middleware
    request.scope["authenticated_user"] = user_info
    return user_info
