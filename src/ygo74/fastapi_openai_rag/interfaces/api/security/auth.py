from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from typing import Optional
import hashlib
import logging
from .autenticated_user import AuthenticatedUser
from ....infrastructure.db.session import get_db
from ....application.services.user_service import UserService
from ....infrastructure.db.unit_of_work import SQLUnitOfWork

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

JWT_SECRET = "SECRET_JWT"
JWT_ALGO = "HS256"

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

    # 1️⃣ Essai API Key (format attendu: "Bearer sk-xxx" ou juste "sk-xxx")
    if api_key_header_value:
        token = api_key_header_value.replace("Bearer ", "").strip()
        # Hash the token to compare with stored hash
        key_hash = hashlib.sha256(token.encode()).hexdigest()

        # Find user by API key hash using service
        try:
            with uow as unit_of_work:
                user_repo = user_service._repository_factory(unit_of_work.session)
                user = user_repo.find_by_api_key_hash(key_hash)
                if user:
                    user_info = AuthenticatedUser(
                        id=user.id,
                        username=user.username,
                        type="api_key",
                        groups=user.groups
                    )
        except Exception as e:
            logger.debug(f"Error finding user by API key: {e}")

    # 2️⃣ Essai JWT OAuth2
    if not user_info and bearer_token:
        try:
            payload = jwt.decode(bearer_token.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
            # Try to find user by username from JWT
            username = payload.get("username")
            if username:
                try:
                    user = user_service.get_user_by_username(username)
                    if user:
                        user_info = AuthenticatedUser(
                            id=user.id,
                            username=user.username,
                            type="jwt",
                            groups=user.groups
                        )
                except:
                    # Fallback to JWT claims if user not found in DB
                    user_info = AuthenticatedUser(
                        id=payload.get("sub"),
                        username=username,
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
