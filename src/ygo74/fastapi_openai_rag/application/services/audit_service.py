import logging
from typing import Dict, Any, List, Optional

from ...domain.unit_of_work import UnitOfWork

from ygo74.fastapi_openai_rag.domain.models.audit_log import AuditLog
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.audit_log_repository import AuditLogRepository


logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for managing audit logs and related operations.
    """

    def __init__(self, uow: UnitOfWork, repository_factory: Optional[callable] = None):
        """
        Initialize the AuditService.

        Args:
            uow: Unit of Work for transaction management
            repository_factory: Optional repository factory for testing
        """
        self._uow = uow
        self._repository_factory = repository_factory or (lambda session: AuditLogRepository(session))
        logger.debug("AuditService initialized with Unit of Work")

    def create_audit_log(self, log_data: Dict[str, Any]) -> Optional[AuditLog]:
        """
        Create a new audit log entry.

        Args:
            log_data: The audit data to record

        Returns:
            The created audit log with ID or None if creation fails
        """
        try:
            # Extract base audit fields from the log_data
            base_fields = {
                "method", "path", "user", "auth_type",
                "status_code", "duration_ms", "timestamp"
            }

            # Extract base fields for the AuditLog model
            audit_data = {k: v for k, v in log_data.items() if k in base_fields}

            # Put any additional fields in metadata
            metadata = {k: v for k, v in log_data.items() if k not in base_fields}

            if metadata:
                audit_data["metadata"] = metadata

            audit_log = AuditLog(**audit_data)

            with self._uow as uow:
                repository = self._repository_factory(uow.session)
                return repository.add(audit_log)

        except Exception as e:
            # Log the error but don't raise, to prevent disrupting the main application flow
            logger.error(f"Failed to create audit log: {str(e)}", exc_info=True)
            return None

    def get_recent_logs(self, limit: int = 100) -> List[AuditLog]:
        """
        Get the most recent audit logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of recent audit logs
        """
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            return repository.get_recent(limit)

    def get_log_by_id(self, log_id: int) -> Optional[AuditLog]:
        """
        Get an audit log by its ID.

        Args:
            log_id: The ID of the audit log

        Returns:
            The audit log if found, None otherwise
        """
        with self._uow as uow:
            repository = self._repository_factory(uow.session)
            return repository.get_by_id(log_id)
