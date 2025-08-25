"""Token usage repository interface."""
from abc import abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..models.token_usage import TokenUsage
from .base import BaseRepository

class ITokenUsageRepository(BaseRepository[TokenUsage]):
    """Interface for token usage repository operations."""

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> List[TokenUsage]:
        """Get token usage records by user ID.

        Args:
            user_id (str): User identifier

        Returns:
            List[TokenUsage]: List of token usage records for the user
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_by_filters(self, filters: Dict[str, Any], limit: int = 100) -> List[TokenUsage]:
        """Get token usage records filtered by various criteria.

        Args:
            filters (Dict[str, Any]): Dictionary of filter criteria
            limit (int): Maximum number of records to return

        Returns:
            List[TokenUsage]: Filtered list of token usage records
        """
        pass
