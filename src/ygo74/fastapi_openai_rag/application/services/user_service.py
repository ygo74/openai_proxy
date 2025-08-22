"""User service implementation."""
from typing import List, Optional, Tuple
from datetime import datetime, timezone
import uuid
import hashlib
import secrets
from ...domain.models.user import User, ApiKey
from ...domain.repositories.user_repository import IUserRepository
from ...domain.unit_of_work import UnitOfWork
from ...infrastructure.db.repositories.user_repository import UserRepository
from ...domain.exceptions.entity_not_found_exception import EntityNotFoundError
from ...domain.exceptions.entity_already_exists import EntityAlreadyExistsError
from ...domain.exceptions.validation_error import ValidationError
import logging
from .group_service import GroupService

logger = logging.getLogger(__name__)

class UserService:
    """Service for managing users."""

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None):
        """Initialize service with Unit of Work and optional repository factory.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
            repository_factory (Optional[callable]): Optional factory for testing
        """
        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: UserRepository(session))
        self._group_service = GroupService(uow, repository_factory)
        logger.debug("UserService initialized with Unit of Work")

    def add_or_update_user(self, user_id: Optional[str] = None,
                          username: Optional[str] = None,
                          email: Optional[str] = None,
                          groups: Optional[List[str]] = None) -> Tuple[str, User]:
        """Add a new user or update an existing one.

        Args:
            user_id (Optional[str]): ID of user to update
            username (Optional[str]): Username
            email (Optional[str]): User email
            groups (Optional[List[str]]): User groups

        Returns:
            Tuple[str, User]: Status and user entity

        Raises:
            EntityNotFoundError: If user not found for update
            ValidationError: If required fields missing for creation
            EntityAlreadyExistsError: If user already exists
        """
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)

            if user_id:
                logger.info(f"Updating user {user_id}")
                existing_user: Optional[User] = repository.get_by_id(user_id)
                if not existing_user:
                    logger.error(f"User {user_id} not found for update")
                    raise EntityNotFoundError("User", str(user_id))

                updated_user: User = User(
                    id=user_id,
                    username=username or existing_user.username,
                    email=email or existing_user.email,
                    is_active=existing_user.is_active,
                    created_at=existing_user.created_at,
                    updated_at=datetime.now(timezone.utc),
                    groups=groups if groups is not None else existing_user.groups,
                    api_keys=existing_user.api_keys
                )
                result: User = repository.update(entity=updated_user)
                logger.info(f"User {user_id} updated successfully")
                return ("updated", result)

            logger.info("Creating new user")
            if not username:
                logger.error("Username is required for user creation")
                raise ValidationError("Username is required for new users")

            existing: Optional[User] = repository.get_by_username(username)
            if existing:
                logger.warning(f"User with username {username} already exists")
                raise EntityAlreadyExistsError("User", f"username {username}")

            if email:
                existing_email: Optional[User] = repository.get_by_email(email)
                if existing_email:
                    logger.warning(f"User with email {email} already exists")
                    raise EntityAlreadyExistsError("User", f"email {email}")

            new_user: User = User(
                id=str(uuid.uuid4()),
                username=username,
                email=email,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                groups=groups or [],
                api_keys=[]
            )
            result: User = repository.add(new_user)
            logger.info(f"User created successfully with id {result.id}")
            return ("created", result)

    def get_all_users(self) -> List[User]:
        """Get all users.

        Returns:
            List[User]: List of all user entities
        """
        logger.info("Fetching all users")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            users: List[User] = repository.get_all()
            logger.debug(f"Found {len(users)} users")
            return users

    def get_active_users(self) -> List[User]:
        """Get all active users.

        Returns:
            List[User]: List of active user entities
        """
        logger.info("Fetching all active users")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            users: List[User] = repository.get_active_users()
            logger.debug(f"Found {len(users)} active users")
            return users

    def get_user_by_id(self, user_id: str) -> User:
        """Get user by ID.

        Args:
            user_id (str): User ID

        Returns:
            Optional[User]: User entity if found, None otherwise

        Raises:
            EntityNotFoundError: If user not found
        """
        logger.info(f"Fetching user {user_id}")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            user: Optional[User] = repository.get_by_id(user_id)
            logger.debug(f"User {user_id} {'found' if user else 'not found'}")
            if not user:
                raise EntityNotFoundError("User", str(user_id))
            return user

    def get_user_by_username(self, username: str) -> User:
        """Get user by username.

        Args:
            username (str): Username

        Returns:
            Optional[User]: User entity if found, None otherwise

        Raises:
            EntityNotFoundError: If user not found
        """
        logger.info(f"Fetching user by username: {username}")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            user: Optional[User] = repository.get_by_username(username)
            logger.debug(f"User '{username}' {'found' if user else 'not found'}")
            if not user:
                raise EntityNotFoundError("User", username)
            return user

    def try_get_user_by_username(self, username: str) -> Optional[User]:
        """Try to get user by username without raising exceptions.

        Args:
            username (str): Username

        Returns:
            Optional[User]: User entity if found, None otherwise
        """
        logger.info(f"Trying to fetch user by username: {username}")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            user: Optional[User] = repository.get_by_username(username)
            logger.debug(f"User '{username}' {'found' if user else 'not found'}")
            return user

    def get_user_by_api_key_hash(self, key_hash: str) -> Optional[User]:
        """Get user by API key hash.

        Args:
            key_hash (str): Hashed API key to search for

        Returns:
            Optional[User]: User entity if found with valid API key, None otherwise
        """
        logger.info(f"Fetching user by API key hash")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            user: Optional[User] = repository.find_by_api_key_hash(key_hash)
            logger.debug(f"User with API key hash {'found' if user else 'not found'}")
            return user

    def create_api_key(self, user_id: str, name: Optional[str] = None,
                      expires_at: Optional[datetime] = None) -> Tuple[str, ApiKey]:
        """Create a new API key for a user.

        Args:
            user_id (str): User ID
            name (Optional[str]): API key name
            expires_at (Optional[datetime]): Expiration date

        Returns:
            Tuple[str, ApiKey]: Plain text key and API key entity

        Raises:
            EntityNotFoundError: If user not found
        """
        logger.info(f"Creating API key for user {user_id}")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)

            user: Optional[User] = repository.get_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found for API key creation")
                raise EntityNotFoundError("User", str(user_id))

            # Generate secure random key
            plain_key = f"sk-{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

            api_key = ApiKey(
                id=str(uuid.uuid4()),
                key_hash=key_hash,
                name=name,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                expires_at=expires_at,
                is_active=True
            )

            # Create updated user with new API key
            updated_user = User(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=datetime.now(timezone.utc),
                groups=user.groups,
                api_keys=[*user.api_keys, api_key]  # Add new API key to existing ones
            )

            repository.update(updated_user)
            logger.info(f"API key created successfully for user {user_id}")
            return (plain_key, api_key)

    def deactivate_user(self, user_id: str) -> User:
        """Deactivate a user.

        Args:
            user_id (str): ID of user to deactivate

        Returns:
            User: Deactivated user

        Raises:
            EntityNotFoundError: If user not found
        """
        logger.info(f"Deactivating user {user_id}")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            existing_user: Optional[User] = repository.get_by_id(user_id)
            if not existing_user:
                logger.error(f"User {user_id} not found for deactivation")
                raise EntityNotFoundError("User", str(user_id))

            deactivated_user: User = User(
                id=existing_user.id,
                username=existing_user.username,
                email=existing_user.email,
                is_active=False,
                created_at=existing_user.created_at,
                updated_at=datetime.now(timezone.utc),
                groups=existing_user.groups,
                api_keys=existing_user.api_keys
            )
            result: User = repository.update(entity=deactivated_user)
            logger.info(f"User {user_id} deactivated successfully")
            return result

    def delete_user(self, user_id: str) -> None:
        """Delete a user.

        Args:
            user_id (str): ID of user to delete

        Raises:
            EntityNotFoundError: If user not found
        """
        logger.info(f"Deleting user {user_id}")
        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            # Check if user exists before trying to delete
            existing_user: Optional[User] = repository.get_by_id(user_id)
            if not existing_user:
                logger.error(f"User {user_id} not found for deletion")
                raise EntityNotFoundError("User", str(user_id))

            repository.remove(user_id)
            logger.info(f"User {user_id} deleted successfully")

    def create_user_from_keycloak(
        self,
        username: str,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        keycloak_groups: Optional[List[str]] = None
    ) -> User:
        """
        Create a new user from Keycloak authentication data.

        Args:
            username: User's username from Keycloak
            email: User's email from Keycloak
            first_name: User's first name from Keycloak
            last_name: User's last name from Keycloak
            keycloak_groups: List of group names from Keycloak

        Returns:
            Created User domain model

        Raises:
            ValueError: If user creation fails
        """
        if keycloak_groups is None:
            keycloak_groups = []

        logger.info(f"Creating user from Keycloak: {username}")

        # Ensure all Keycloak groups exist in the groups table
        if keycloak_groups:
            self._group_service.ensure_groups_exist(keycloak_groups)

        # Create user with groups
        new_user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            groups=keycloak_groups,
            api_keys=[]
        )

        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            created_user = repository.add(new_user)
            logger.info(f"User created from Keycloak: {created_user.username}")
            return created_user

    def sync_user_groups_from_keycloak(
        self,
        user_id: str,
        keycloak_groups: List[str]
    ) -> User:
        """
        Synchronize user's groups with Keycloak groups.

        Args:
            user_id: User's database ID
            keycloak_groups: List of group names from Keycloak

        Returns:
            Updated User domain model

        Raises:
            ValueError: If user not found or sync fails
        """
        logger.info(f"Syncing groups for user {user_id} from Keycloak")

        # Ensure all Keycloak groups exist in the groups table
        if keycloak_groups:
            self._group_service.ensure_groups_exist(keycloak_groups)

        with self._uow as uow:
            repository: IUserRepository = self._repository_factory(uow.session)
            user = repository.get_by_id(user_id)
            if not user:
                raise ValueError(f"User with ID {user_id} not found")

            # Update user's groups directly
            updated_user = User(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=datetime.now(timezone.utc),
                groups=keycloak_groups,
                api_keys=user.api_keys
            )

            result = repository.update(updated_user)
            logger.info(f"Groups synced for user {user_id}")
            return result
