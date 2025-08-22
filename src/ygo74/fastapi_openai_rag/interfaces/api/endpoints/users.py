"""User endpoints module."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.user_service import UserService
from ....domain.models.user import User, ApiKey
from ..decorators import endpoint_handler

logger = logging.getLogger(__name__)

router = APIRouter()

class ApiKeyResponse(BaseModel):
    """API Key response schema."""
    id: str
    name: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    last_used_at: Optional[datetime] = None

class UserResponse(BaseModel):
    """User response schema."""
    id: str
    username: str
    email: Optional[EmailStr] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    groups: List[str] = []
    api_keys: List[ApiKeyResponse] = []

class UserCreate(BaseModel):
    """User creation schema."""
    username: str
    email: Optional[EmailStr] = None
    groups: Optional[List[str]] = None

class UserUpdate(BaseModel):
    """User update schema."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    groups: Optional[List[str]] = None

class ApiKeyCreate(BaseModel):
    """API Key creation schema."""
    name: Optional[str] = None
    expires_at: Optional[datetime] = None

class ApiKeyCreateResponse(BaseModel):
    """API Key creation response with plain text key."""
    api_key: str
    key_info: ApiKeyResponse

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Create UserService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return UserService(uow)


def map_user_to_response(user: User) -> UserResponse:
    """Map User domain model to UserResponse schema."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        groups=user.groups,
        api_keys=[map_api_key_to_response(ak) for ak in user.api_keys]
    )

def map_api_key_to_response(api_key: ApiKey) -> ApiKeyResponse:
    """Map ApiKey domain model to ApiKeyResponse schema."""
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at
    )

@router.get("/", response_model=List[UserResponse])
@endpoint_handler("get_users")
async def get_users(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    service: UserService = Depends(get_user_service)
) -> List[UserResponse]:
    """Get list of users."""
    if active_only:
        users: List[User] = service.get_active_users()
    else:
        users: List[User] = service.get_all_users()

    # Apply pagination
    paginated_users = users[skip:skip + limit]

    return [map_user_to_response(u) for u in paginated_users]

@router.post("/", response_model=UserResponse, status_code=201)
@endpoint_handler("create_user")
async def create_user(
    user: UserCreate,
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Create a new user."""
    _, created_user = service.add_or_update_user(
        username=user.username,
        email=user.email,
        groups=user.groups
    )

    return map_user_to_response(created_user)


@router.get("/statistics")
@endpoint_handler("get_user_statistics")
async def get_user_statistics(
    service: UserService = Depends(get_user_service)
) -> Dict[str, Any]:
    """Get user statistics."""
    all_users: List[User] = service.get_all_users()
    active_users: List[User] = service.get_active_users()

    total_api_keys = sum(len(u.api_keys) for u in all_users)
    active_api_keys = sum(len([ak for ak in u.api_keys if ak.is_active]) for u in all_users)

    stats = {
        "total_users": len(all_users),
        "active_users": len(active_users),
        "inactive_users": len(all_users) - len(active_users),
        "total_api_keys": total_api_keys,
        "active_api_keys": active_api_keys
    }

    return stats

@router.get("/{user_id}", response_model=UserResponse)
@endpoint_handler("get_user")
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Get a specific user by ID."""
    user: User = service.get_user_by_id(user_id)

    return map_user_to_response(user)

@router.put("/{user_id}", response_model=UserResponse)
@endpoint_handler("update_user")
async def update_user(
    user_id: str,
    user: UserUpdate,
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Update a user."""
    _, updated_user = service.add_or_update_user(
        user_id=user_id,
        username=user.username,
        email=user.email,
        groups=user.groups
    )

    return map_user_to_response(updated_user)

@router.delete("/{user_id}")
@endpoint_handler("delete_user")
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """Delete a user."""
    service.delete_user(user_id)
    return {"message": f"User with ID {user_id} deleted successfully"}

@router.post("/{user_id}/deactivate", response_model=UserResponse)
@endpoint_handler("deactivate_user")
async def deactivate_user(
    user_id: str,
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Deactivate a user."""
    deactivated_user: User = service.deactivate_user(user_id)

    return map_user_to_response(deactivated_user)

@router.get("/username/{username}", response_model=UserResponse)
@endpoint_handler("get_user_by_username")
async def get_user_by_username(
    username: str,
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Get a user by username."""
    user: User = service.get_user_by_username(username)

    return map_user_to_response(user)

@router.post("/{user_id}/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
@endpoint_handler("create_api_key")
async def create_api_key(
    user_id: str,
    api_key_data: ApiKeyCreate,
    service: UserService = Depends(get_user_service)
) -> ApiKeyCreateResponse:
    """Create a new API key for a user."""
    plain_key, api_key = service.create_api_key(
        user_id=user_id,
        name=api_key_data.name,
        expires_at=api_key_data.expires_at
    )

    return ApiKeyCreateResponse(
        api_key=plain_key,
        key_info=map_api_key_to_response(api_key)
    )
