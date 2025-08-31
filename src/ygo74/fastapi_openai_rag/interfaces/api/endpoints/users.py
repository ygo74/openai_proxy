"""User endpoints module."""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.user_service import UserService
from ....application.services.token_usage_service import TokenUsageService
from ....domain.models.user import User, ApiKey
from ..decorators.decorators import endpoint_handler
from ..security.auth import require_admin_role
from ....domain.models.autenticated_user import AuthenticatedUser
from ....infrastructure.db.repositories.model_repository import SQLModelRepository
from ....infrastructure.db.repositories.group_repository import SQLGroupRepository

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

class GroupsUpdate(BaseModel):
    """Payload model for adding/removing groups on a user."""
    groups: List[str]

class TokenUsageDetailResponse(BaseModel):
    """Token usage detail response schema."""
    id: int
    user_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: datetime
    request_id: Optional[str] = None
    endpoint: str

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Create UserService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return UserService(
        uow,
        model_repository_factory=lambda s: SQLModelRepository(s),
        group_repository_factory=lambda s: SQLGroupRepository(s),
    )

def get_token_usage_service(db: Session = Depends(get_db)) -> TokenUsageService:
    """Create TokenUsageService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return TokenUsageService(uow)

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

@router.get("", response_model=List[UserResponse])
@endpoint_handler("get_users")
async def get_users(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> List[UserResponse]:
    """Get list of users."""
    if active_only:
        users: List[User] = service.get_active_users()
    else:
        users: List[User] = service.get_all_users()

    # Apply pagination
    paginated_users = users[skip:skip + limit]

    return [map_user_to_response(u) for u in paginated_users]

@router.post("", response_model=UserResponse, status_code=201)
@endpoint_handler("create_user")
async def create_user(
    user: UserCreate,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
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
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
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
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> UserResponse:
    """Get a specific user by ID."""
    user: User = service.get_user_by_id(user_id)

    return map_user_to_response(user)

@router.put("/{user_id}", response_model=UserResponse)
@endpoint_handler("update_user")
async def update_user(
    user_id: str,
    user: UserUpdate,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> UserResponse:
    """Update a user."""
    _, updated_user = service.add_or_update_user(
        user_id=user_id,
        username=user.username,
        email=user.email,
        groups=user.groups
    )

    return map_user_to_response(updated_user)

@router.post("/{user_id}/groups/add", response_model=UserResponse)
@endpoint_handler("add_user_groups")
async def add_user_groups(
    user_id: str,
    payload: GroupsUpdate,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> UserResponse:
    """Add one or multiple groups to a user."""
    updated: User = service.add_user_groups(user_id, payload.groups)
    return map_user_to_response(updated)

@router.post("/{user_id}/groups/remove", response_model=UserResponse)
@endpoint_handler("remove_user_groups")
async def remove_user_groups(
    user_id: str,
    payload: GroupsUpdate,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> UserResponse:
    """Remove one or multiple groups from a user."""
    updated: User = service.remove_user_groups(user_id, payload.groups)
    return map_user_to_response(updated)

@router.delete("/{user_id}")
@endpoint_handler("delete_user")
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
):
    """Delete a user."""
    service.delete_user(user_id)
    return {"message": f"User with ID {user_id} deleted successfully"}

@router.post("/{user_id}/deactivate", response_model=UserResponse)
@endpoint_handler("deactivate_user")
async def deactivate_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> UserResponse:
    """Deactivate a user."""
    deactivated_user: User = service.deactivate_user(user_id)

    return map_user_to_response(deactivated_user)

@router.get("/username/{username}", response_model=UserResponse)
@endpoint_handler("get_user_by_username")
async def get_user_by_username(
    username: str,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> UserResponse:
    """Get a user by username."""
    user: User = service.get_user_by_username(username)

    return map_user_to_response(user)

@router.post("/{user_id}/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
@endpoint_handler("create_api_key")
async def create_api_key(
    user_id: str,
    api_key_data: ApiKeyCreate,
    service: UserService = Depends(get_user_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
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

@router.get("/{user_id}/token-usage")
@endpoint_handler("get_user_token_usage")
async def get_user_token_usage(
    user_id: str,
    days: Optional[int] = Query(30, description="Number of days to look back"),
    user_service: UserService = Depends(get_user_service),
    token_service: TokenUsageService = Depends(get_token_usage_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> Dict[str, Any]:
    """
    Get token usage statistics for a specific user.

    Args:
        user_id: The ID of the user
        days: Number of days to look back for statistics

    Returns:
        Dictionary containing token usage statistics
    """
    # Verify user exists
    user = user_service.get_user_by_id(user_id)

    # Calculate date range
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    # Get token usage summary
    usage_summary = token_service.get_user_usage_summary(
        user_id=user.username,
        from_date=from_date,
        to_date=to_date
    )

    # Add user information to the response
    usage_summary["username"] = user.username
    usage_summary["email"] = user.email
    usage_summary["days"] = days

    return usage_summary

@router.get("/{user_id}/token-usage/details")
@endpoint_handler("get_user_token_usage_details")
async def get_user_token_usage_details(
    user_id: str,
    days: Optional[int] = Query(30, description="Number of days to look back"),
    limit: Optional[int] = Query(100, description="Maximum number of records to return"),
    user_service: UserService = Depends(get_user_service),
    token_service: TokenUsageService = Depends(get_token_usage_service),
    authenticated_user: AuthenticatedUser = Depends(require_admin_role)
) -> List[TokenUsageDetailResponse]:
    """
    Get detailed token usage records for a specific user.

    Args:
        user_id: The ID of the user
        days: Number of days to look back
        limit: Maximum number of records to return

    Returns:
        List of detailed token usage records
    """
    # Verify user exists
    user = user_service.get_user_by_id(user_id)

    # Calculate date range
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    # Get detailed token usage records
    usage_details = token_service.get_user_token_usage_details(
        user_id=user.username,
        from_date=from_date,
        to_date=to_date,
        limit=limit
    )

    # Map to response model
    return [
        TokenUsageDetailResponse(
            id=record.id,
            user_id=record.user_id,
            model=record.model,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            timestamp=record.timestamp,
            request_id=record.request_id,
            endpoint=record.endpoint
        ) for record in usage_details
    ]
