"""Token usage repository implementation."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from ....domain.repositories.token_usage_repository import ITokenUsageRepository
from ....domain.models.token_usage import TokenUsage
from ..models.token_usage_orm import TokenUsageORM
from ..mappers.token_usage_mapper import TokenUsageMapper
from .base_repository import SQLBaseRepository

class TokenUsageRepository(SQLBaseRepository[TokenUsage, TokenUsageORM], ITokenUsageRepository):
    """SQL repository implementation for token usage."""

    def __init__(self, session: Session):
        """Initialize repository.

        Args:
            session (Session): SQLAlchemy session
        """
        super().__init__(session, TokenUsageORM, TokenUsageMapper)


    def get_by_user_id(self, user_id: str) -> List[TokenUsage]:
        """Get token usage records by user ID.

        Args:
            user_id (str): User identifier

        Returns:
            List[TokenUsage]: List of token usage records for the user
        """
        query = select(TokenUsageORM).where(TokenUsageORM.user_id == user_id)
        result = self._session.execute(query).scalars().all()
        return TokenUsageMapper.to_domain_list(result)

    def get_usage_summary_by_user(self, user_id: str,
                                 from_date: Optional[datetime] = None,
                                 to_date: Optional[datetime] = None) -> dict:
        """Get token usage summary for a user.

        Args:
            user_id (str): User identifier
            from_date (Optional[datetime]): Start date for filtering
            to_date (Optional[datetime]): End date for filtering

        Returns:
            dict: Summary statistics of token usage
        """
        query = select(
            func.sum(TokenUsageORM.prompt_tokens).label('total_prompt_tokens'),
            func.sum(TokenUsageORM.completion_tokens).label('total_completion_tokens'),
            func.sum(TokenUsageORM.total_tokens).label('total_tokens'),
            func.count().label('request_count')
        ).where(TokenUsageORM.user_id == user_id)

        if from_date:
            query = query.where(TokenUsageORM.timestamp >= from_date)

        if to_date:
            query = query.where(TokenUsageORM.timestamp <= to_date)

        result = self._session.execute(query).first()

        if result:
            return {
                'user_id': user_id,
                'total_prompt_tokens': result.total_prompt_tokens or 0,
                'total_completion_tokens': result.total_completion_tokens or 0,
                'total_tokens': result.total_tokens or 0,
                'request_count': result.request_count or 0,
                'from_date': from_date,
                'to_date': to_date
            }

        return {
            'user_id': user_id,
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'request_count': 0,
            'from_date': from_date,
            'to_date': to_date
        }

    def get_by_filters(self, filters: Dict[str, Any], limit: int = 100) -> List[TokenUsage]:
        """Get token usage records filtered by various criteria.

        Args:
            filters (Dict[str, Any]): Dictionary of filter criteria
            limit (int): Maximum number of records to return

        Returns:
            List[TokenUsage]: Filtered list of token usage records
        """
        query = select(TokenUsageORM)

        # Apply filters
        if "user_id" in filters:
            query = query.where(TokenUsageORM.user_id == filters["user_id"])

        if "model" in filters:
            query = query.where(TokenUsageORM.model == filters["model"])

        if "from_date" in filters:
            query = query.where(TokenUsageORM.timestamp >= filters["from_date"])

        if "to_date" in filters:
            query = query.where(TokenUsageORM.timestamp <= filters["to_date"])

        if "endpoint" in filters:
            query = query.where(TokenUsageORM.endpoint == filters["endpoint"])

        if "request_id" in filters:
            query = query.where(TokenUsageORM.request_id == filters["request_id"])

        # Order by timestamp (most recent first)
        query = query.order_by(TokenUsageORM.timestamp.desc())

        # Apply limit
        query = query.limit(limit)

        result = self._session.execute(query).scalars().all()
        return TokenUsageMapper.to_domain_list(result)
