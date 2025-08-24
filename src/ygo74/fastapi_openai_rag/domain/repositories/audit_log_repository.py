"""Audit log repository interface."""
from abc import abstractmethod
from typing import Optional, List
from ..models.audit_log import AuditLog
from .base import BaseRepository

class IAuditLogRepository(BaseRepository[AuditLog]):
    """Interface for audit log repository operations."""

    @abstractmethod
    async def get_by_id(self, log_id: int) -> Optional[AuditLog]:
        """Get an audit log by its ID.

        Args:
            log_id (int): The ID of the audit log

        Returns:
            Optional[AuditLog]: The audit log if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_recent(self, limit: int = 100) -> List[AuditLog]:
        """Get the most recent audit logs.

        Args:
            limit (int): Maximum number of logs to return

        Returns:
            List[AuditLog]: List of recent audit logs
        """
        pass
