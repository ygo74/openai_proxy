"""Service for tracking and querying token usage."""
import logging
import uuid
from typing import Dict, Optional, List, Any
from datetime import datetime
from ...domain.models.token_usage import TokenUsage
from ...domain.unit_of_work import UnitOfWork
from ...infrastructure.db.repositories.token_usage_repository import TokenUsageRepository

logger = logging.getLogger(__name__)

class TokenUsageService:
    """Service for managing token usage data."""

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None):
        """Initialize service.

        Args:
            uow (UnitOfWork): Unit of Work for transaction management
            repository_factory (Optional[callable]): Optional repository factory for testing
        """
        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: TokenUsageRepository(session))
        logger.debug("TokenUsageService initialized")

    def record_token_usage(self, user_id: str, model: str, prompt_tokens: int,
                           completion_tokens: int, endpoint: str,
                           request_id: Optional[str] = None) -> TokenUsage:
        """Record token usage for a user.

        Args:
            user_id (str): User identifier
            model (str): Model name used
            prompt_tokens (int): Tokens used in the prompt
            completion_tokens (int): Tokens used in the completion
            endpoint (str): API endpoint used
            request_id (Optional[str]): Associated request ID

        Returns:
            TokenUsage: The recorded token usage entity
        """
        logger.info(f"Recording token usage for user {user_id}: {prompt_tokens} prompt, {completion_tokens} completion")

        # Create token usage domain entity
        token_usage = TokenUsage(
            user_id=user_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            endpoint=endpoint,
            request_id=request_id or str(uuid.uuid4())
        )

        # Persist to database
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            result = repository.add(token_usage)
            logger.debug(f"Token usage recorded successfully with ID {result.id}")
            return result

    def get_user_usage_summary(self, user_id: str, from_date: Optional[datetime] = None,
                              to_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get token usage summary for a user.

        Args:
            user_id (str): User identifier
            from_date (Optional[datetime]): Start date for filtering
            to_date (Optional[datetime]): End date for filtering

        Returns:
            Dict[str, Any]: Summary statistics of token usage
        """
        logger.info(f"Getting usage summary for user {user_id}")

        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            return repository.get_usage_summary_by_user(user_id, from_date, to_date)

    def get_user_token_usage_details(self, user_id: str, from_date: Optional[datetime] = None,
                               to_date: Optional[datetime] = None, limit: int = 100) -> List[TokenUsage]:
        """Get detailed token usage records for a user.

        Args:
            user_id (str): User identifier
            from_date (Optional[datetime]): Start date for filtering
            to_date (Optional[datetime]): End date for filtering
            limit (int): Maximum number of records to return

        Returns:
            List[TokenUsage]: List of detailed token usage records
        """
        logger.info(f"Getting detailed token usage for user {user_id}")

        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            query_filter = {"user_id": user_id}

            if from_date:
                query_filter["from_date"] = from_date

            if to_date:
                query_filter["to_date"] = to_date

            records = repository.get_by_filters(query_filter, limit=limit)
            logger.debug(f"Found {len(records)} token usage records for user {user_id}")
            return records
