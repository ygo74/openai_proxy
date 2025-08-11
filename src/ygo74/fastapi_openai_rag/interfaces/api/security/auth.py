from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError, ExpiredSignatureError
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

    # Debug logging
    logger.debug(f"API Key Header: {api_key_header_value}")
    logger.debug(f"Bearer Token: {bearer_token}")

    # 1️⃣ Essai API Key (format attendu: "Bearer sk-xxx" ou juste "sk-xxx")
    if api_key_header_value and api_key_header_value.startswith("sk-"):
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

            # Decode the JWT token
            payload = jwt.decode(
                token_str,
                JWT_SECRET,
                algorithms=[JWT_ALGO],
                audience="fastapi-openai-rag",  #  Specify expected audience
                issuer="fastapi-openai-rag-debug"  # Specify expected issuer
            )
            logger.debug(f"JWT payload decoded successfully: {payload}")

            # Try to find user by username from JWT
            username = payload.get("username")
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
                    user_info = AuthenticatedUser(
                        id=payload.get("sub", f"jwt-{username}"),
                        username=username,
                        type="jwt",
                        groups=payload.get("groups", [])
                    )
            else:
                logger.debug("No username found in JWT payload")

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
