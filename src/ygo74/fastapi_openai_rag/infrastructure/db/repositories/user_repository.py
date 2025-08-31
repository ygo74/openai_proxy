"""User repository for database operations."""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_
from ....domain.models.user import User, ApiKey
from ....domain.repositories.user_repository import IUserRepository
from ..models.user_orm import UserORM, ApiKeyORM
from ..models.group_orm import GroupORM
from ..mappers.user_mapper import UserMapper
from .base_repository import SQLBaseRepository


class UserRepository(SQLBaseRepository[User, UserORM], IUserRepository):
    """Repository for User operations."""

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session (Session): Database session
        """
        super().__init__(session, UserORM, UserMapper)

    def get_by_id(self, id: str) -> Optional[User]:
        """Get user by ID.

        Args:
            id (int): User ID

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(UserORM)
            .options(
                selectinload(UserORM.api_keys),
                selectinload(UserORM.groups),
            )
            .where(UserORM.id == id)
        )

        result = self._session.execute(stmt)
        user_orm = result.scalar_one_or_none()

        if not user_orm:
            return None

        return self._mapper.to_domain(user_orm)

    def get_all(self) -> List[User]:
        """Get all users.

        Returns:
            List[User]: List of all users
        """
        stmt = (
            select(UserORM)
            .options(
                selectinload(UserORM.api_keys),
                selectinload(UserORM.groups),
            )
        )

        result = self._session.execute(stmt)
        user_orms = result.scalars().all()

        return [self._mapper.to_domain(user_orm) for user_orm in user_orms]

    def add(self, entity: User) -> User:
        """Add user to database.

        Args:
            entity (User): User to add

        Returns:
            User: Added user
        """
        user_orm = UserMapper.to_orm(entity)
        # Attach groups via association table
        if entity.groups:
            grp_stmt = select(GroupORM).where(GroupORM.name.in_(entity.groups))
            groups = self._session.execute(grp_stmt).scalars().all()
            user_orm.groups = groups
        self._session.add(user_orm)
        self._session.flush()
        self._session.refresh(user_orm)

        return UserMapper.to_domain(user_orm)

    def update(self, entity: User) -> User:
        """Update user in database.

        Args:
            entity (User): User to update

        Returns:
            User: Updated user
        """
        user_orm = UserMapper.to_orm(entity)
        merged = self._session.merge(user_orm)
        self._session.flush()
        # Update group associations if provided (replace with new set)
        if entity.groups is not None:
            grp_stmt = select(GroupORM).where(GroupORM.name.in_(entity.groups))
            groups = self._session.execute(grp_stmt).scalars().all()
            merged.groups = groups
            self._session.flush()
        updated_orm = self._session.get(UserORM, entity.id)
        return UserMapper.to_domain(updated_orm)

    def remove(self, entity_id: str) -> None:
        """Remove user from database.

        Args:
            entity_id (str): User ID to remove
        """
        user_orm = self._session.get(UserORM, entity_id)
        if user_orm:
            self._session.delete(user_orm)
            self._session.flush()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username (str): Username

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(UserORM)
            .options(
                selectinload(UserORM.api_keys),
                selectinload(UserORM.groups),
            )
            .where(UserORM.username == username, UserORM.is_active == True)
        )

        result = self._session.execute(stmt)
        user_orm = result.scalar_one_or_none()

        if not user_orm:
            return None

        return self._mapper.to_domain(user_orm)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email (str): Email address

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(UserORM)
            .options(
                selectinload(UserORM.api_keys),
                selectinload(UserORM.groups),
            )
            .where(UserORM.email == email, UserORM.is_active == True)
        )

        result = self._session.execute(stmt)
        user_orm = result.scalar_one_or_none()

        if not user_orm:
            return None

        return self._mapper.to_domain(user_orm)

    def find_by_api_key_hash(self, key_hash: str) -> Optional[User]:
        """Find user by API key hash.

        Args:
            key_hash (str): Hashed API key

        Returns:
            Optional[User]: User if found, None otherwise
        """
        stmt = (
            select(ApiKeyORM)
            .options(
                selectinload(ApiKeyORM.user).selectinload(UserORM.api_keys),
                selectinload(ApiKeyORM.user).selectinload(UserORM.groups),
            )
            .where(
                ApiKeyORM.key_hash == key_hash,
                ApiKeyORM.is_active == True,
                ApiKeyORM.expires_at.is_(None) | (ApiKeyORM.expires_at > datetime.now(timezone.utc))
            )
        )

        result = self._session.execute(stmt)
        api_key_orm = result.scalar_one_or_none()

        if not api_key_orm or not api_key_orm.user.is_active:
            return None

        # Update last_used_at
        api_key_orm.last_used_at = datetime.now(timezone.utc)
        self._session.flush()

        return self._mapper.to_domain(api_key_orm.user)

    def get_active_users(self) -> List[User]:
        """Get all active users.

        Returns:
            List[User]: List of active users
        """
        stmt = (
            select(UserORM)
            .options(
                selectinload(UserORM.api_keys),
                selectinload(UserORM.groups),
            )
            .where(UserORM.is_active == True)
        )

        result = self._session.execute(stmt)
        user_orms = result.scalars().all()

        return [self._mapper.to_domain(user_orm) for user_orm in user_orms]

    def add_user_to_group(self, user_id: str, group_name: str) -> None:
        """Add user to a group by updating the relationship.

        Args:
            user_id: User's database ID
            group_name: Name of the group to add
        """
        user_orm = self._session.get(UserORM, user_id)
        if not user_orm:
            return
        group = self._session.execute(
            select(GroupORM).where(GroupORM.name == group_name)
        ).scalar_one_or_none()
        if group and group not in user_orm.groups:
            user_orm.groups.append(group)
            self._session.flush()

    def remove_user_from_group(self, user_id: str, group_name: str) -> None:
        """Remove user from a group by updating the relationship.

        Args:
            user_id: User's database ID
            group_name: Name of the group to remove
        """
        user_orm = self._session.get(UserORM, user_id)
        if not user_orm:
            return
        group = self._session.execute(
            select(GroupORM).where(GroupORM.name == group_name)
        ).scalar_one_or_none()
        if group and group in user_orm.groups:
            user_orm.groups.remove(group)
            self._session.flush()
