"""User mapper for domain/ORM conversion."""
from typing import List, Optional
from ....domain.models.user import User, ApiKey
from ..models.user_orm import UserORM, ApiKeyORM
from .base import BaseMapper

class UserMapper(BaseMapper[User, UserORM]):
    """Mapper for User domain/ORM conversion."""

    @staticmethod
    def to_domain(orm: UserORM) -> User:
        """Convert UserORM to User domain model.

        Args:
            orm (UserORM): ORM model

        Returns:
            User: Domain model
        """
        # Map groups from relationship to list of names
        groups = [g.name for g in (orm.groups or [])]

        # Convert API keys - ensure they are loaded
        api_keys = []
        if orm.api_keys:  # Check if api_keys relation is loaded
            api_keys = [ApiKeyMapper.to_domain(ak) for ak in orm.api_keys]

        return User(
            id=orm.id,
            username=orm.username,
            email=orm.email,
            is_active=orm.is_active,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            groups=groups,
            api_keys=api_keys
        )

    @staticmethod
    def to_orm(domain: User) -> UserORM:
        """Convert User domain model to UserORM.

        Args:
            domain (User): Domain model

        Returns:
            UserORM: ORM model
        """
        # Do not set groups here; repository will attach GroupORMs
        user_orm = UserORM(
            id=domain.id,
            username=domain.username,
            email=domain.email,
            is_active=domain.is_active,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

        # Convert API keys to ORM
        if domain.api_keys:
            user_orm.api_keys = [ApiKeyMapper.to_orm(ak) for ak in domain.api_keys]

        return user_orm

class ApiKeyMapper(BaseMapper[ApiKey, ApiKeyORM]):
    """Mapper for ApiKey domain/ORM conversion."""

    @staticmethod
    def to_domain(orm: ApiKeyORM) -> ApiKey:
        """Convert ApiKeyORM to ApiKey domain model.

        Args:
            orm (ApiKeyORM): ORM model

        Returns:
            ApiKey: Domain model
        """
        return ApiKey(
            id=orm.id,
            key_hash=orm.key_hash,
            name=orm.name,
            user_id=orm.user_id,
            created_at=orm.created_at,
            expires_at=orm.expires_at,
            is_active=orm.is_active,
            last_used_at=orm.last_used_at
        )

    @staticmethod
    def to_orm(domain: ApiKey) -> ApiKeyORM:
        """Convert ApiKey domain model to ApiKeyORM.

        Args:
            domain (ApiKey): Domain model

        Returns:
            ApiKeyORM: ORM model
        """
        return ApiKeyORM(
            id=domain.id,
            key_hash=domain.key_hash,
            name=domain.name,
            user_id=domain.user_id,
            created_at=domain.created_at,
            expires_at=domain.expires_at,
            is_active=domain.is_active,
            last_used_at=domain.last_used_at
        )
