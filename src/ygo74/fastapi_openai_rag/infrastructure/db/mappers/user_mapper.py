"""User mapper for domain/ORM conversion."""
import json
from typing import List, Optional
from ....domain.models.user import User, ApiKey
from ..models.user_orm import UserORM, ApiKeyORM

class UserMapper:
    """Mapper for User domain/ORM conversion."""

    @staticmethod
    def to_domain(orm: UserORM) -> User:
        """Convert UserORM to User domain model.

        Args:
            orm (UserORM): ORM model

        Returns:
            User: Domain model
        """
        # Parse groups from JSON string
        groups = json.loads(orm.groups) if orm.groups else []

        # Convert API keys - ensure they are loaded
        api_keys = []
        if orm.api_keys:  # Check if api_keys relation is loaded
            api_keys = [
                ApiKey(
                    id=ak.id,
                    key_hash=ak.key_hash,
                    name=ak.name,
                    user_id=ak.user_id,
                    created_at=ak.created_at,
                    expires_at=ak.expires_at,
                    is_active=ak.is_active,
                    last_used_at=ak.last_used_at
                ) for ak in orm.api_keys
            ]

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
        groups_json = json.dumps(domain.groups) if domain.groups else None

        user_orm = UserORM(
            id=domain.id,
            username=domain.username,
            email=domain.email,
            is_active=domain.is_active,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            groups=groups_json
        )

        # Convert API keys to ORM
        if domain.api_keys:
            user_orm.api_keys = [
                ApiKeyORM(
                    id=ak.id,
                    key_hash=ak.key_hash,
                    name=ak.name,
                    user_id=ak.user_id,
                    created_at=ak.created_at,
                    expires_at=ak.expires_at,
                    is_active=ak.is_active,
                    last_used_at=ak.last_used_at
                ) for ak in domain.api_keys
            ]

        return user_orm

class ApiKeyMapper:
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
