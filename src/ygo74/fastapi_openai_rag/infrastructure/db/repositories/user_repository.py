"""User repository for database operations."""
from datetime import datetime
import json
from typing import Optional, List
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_
from ....domain.models.user import User, ApiKey
from ....domain.repositories.user_repository import IUserRepository
from ..models.user_orm import UserORM, ApiKeyORM
from ..models.group_orm import GroupORM
from ..mappers.user_mapper import UserMapper
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.base_repository import SQLBaseRepository


class UserRepository(SQLBaseRepository[User, UserORM], IUserRepository):
    """Repository for User operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session (Session): Database session
        """
        self.session = session

    def get_by_id(self, entity_id: str) -> Optional[User]:
        """Get user by ID.

        Args:
            entity_id (str): User ID

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(UserORM)
            .options(selectinload(UserORM.api_keys))
            .where(UserORM.id == entity_id)
        )

        result = self.session.execute(stmt)
        user_orm = result.scalar_one_or_none()

        if not user_orm:
            return None

        return UserMapper.to_domain(user_orm)

    def get_all(self) -> List[User]:
        """Get all users.

        Returns:
            List[User]: List of all users
        """
        stmt = (
            select(UserORM)
            .options(selectinload(UserORM.api_keys))  #  Ensure API keys are loaded
        )

        result = self.session.execute(stmt)
        user_orms = result.scalars().all()

        return [UserMapper.to_domain(user_orm) for user_orm in user_orms]

    def add(self, entity: User) -> User:
        """Add user to database.

        Args:
            entity (User): User to add

        Returns:
            User: Added user
        """
        user_orm = UserMapper.to_orm(entity)
        self.session.add(user_orm)
        self.session.flush()
        self.session.refresh(user_orm)

        return UserMapper.to_domain(user_orm)

    def update(self, entity: User) -> User:
        """Update user in database.

        Args:
            entity (User): User to update

        Returns:
            User: Updated user
        """
        user_orm = UserMapper.to_orm(entity)
        self.session.merge(user_orm)
        self.session.flush()

        # Refresh to get updated data
        updated_orm = self.session.get(UserORM, entity.id)
        return UserMapper.to_domain(updated_orm)

    def remove(self, entity_id: str) -> None:
        """Remove user from database.

        Args:
            entity_id (str): User ID to remove
        """
        user_orm = self.session.get(UserORM, entity_id)
        if user_orm:
            self.session.delete(user_orm)
            self.session.flush()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username (str): Username

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(UserORM)
            .options(selectinload(UserORM.api_keys))
            .where(UserORM.username == username, UserORM.is_active == True)
        )

        result = self.session.execute(stmt)
        user_orm = result.scalar_one_or_none()

        if not user_orm:
            return None

        return UserMapper.to_domain(user_orm)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email (str): Email address

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(UserORM)
            .options(selectinload(UserORM.api_keys))
            .where(UserORM.email == email, UserORM.is_active == True)
        )

        result = self.session.execute(stmt)
        user_orm = result.scalar_one_or_none()

        if not user_orm:
            return None

        return UserMapper.to_domain(user_orm)

    def find_by_api_key_hash(self, key_hash: str) -> Optional[User]:
        """Find user by API key hash.

        Args:
            key_hash (str): Hashed API key

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(ApiKeyORM)
            .options(selectinload(ApiKeyORM.user).selectinload(UserORM.api_keys))
            .where(
                ApiKeyORM.key_hash == key_hash,
                ApiKeyORM.is_active == True,
                ApiKeyORM.expires_at.is_(None) | (ApiKeyORM.expires_at > datetime.utcnow())
            )
        )

        result = self.session.execute(stmt)
        api_key_orm = result.scalar_one_or_none()

        if not api_key_orm or not api_key_orm.user.is_active:
            return None

        # Update last_used_at
        api_key_orm.last_used_at = datetime.utcnow()
        self.session.flush()

        return UserMapper.to_domain(api_key_orm.user)

    def get_active_users(self) -> List[User]:
        """Get all active users.

        Returns:
            List[User]: List of active users
        """
        stmt = (
            select(UserORM)
            .options(selectinload(UserORM.api_keys))  # Ensure API keys are loaded
            .where(UserORM.is_active == True)
        )

        result = self.session.execute(stmt)
        user_orms = result.scalars().all()

        return [UserMapper.to_domain(user_orm) for user_orm in user_orms]

    def add_user_to_group(self, user_id: int, group_name: str) -> None:
        """
        Add user to a group by updating the JSON groups field.

        Args:
            user_id: User's database ID
            group_name: Name of the group to add
        """
        user_orm = self.session.get(UserORM, user_id)
        if user_orm:
            current_groups = json.loads(user_orm.groups) if user_orm.groups else []
            if group_name not in current_groups:
                current_groups.append(group_name)
                user_orm.groups = json.dumps(current_groups)

    def remove_user_from_group(self, user_id: int, group_name: str) -> None:
        """
        Remove user from a group by updating the JSON groups field.

        Args:
            user_id: User's database ID
            group_name: Name of the group to remove
        """
        user_orm = self.session.get(UserORM, user_id)
        if user_orm:
            current_groups = json.loads(user_orm.groups) if user_orm.groups else []
            if group_name in current_groups:
                current_groups.remove(group_name)
                user_orm.groups = json.dumps(current_groups)
