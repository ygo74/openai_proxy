from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ygo74.fastapi_openai_rag.domain.models.audit_log import AuditLog
from ygo74.fastapi_openai_rag.domain.repositories.audit_log_repository import IAuditLogRepository
from ygo74.fastapi_openai_rag.infrastructure.db.mappers.audit_log_mapper import AuditLogMapper
from ygo74.fastapi_openai_rag.infrastructure.db.models.audit_log_orm import AuditLogORM
from .base_repository import SQLBaseRepository


class AuditLogRepository(SQLBaseRepository[AuditLog, AuditLogORM], IAuditLogRepository):
    """
    Repository for managing audit log entries in the database.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session (Session): Database session
        """
        # Passer la classe GroupMapper directement, pas une instance
        super().__init__(session, AuditLogORM, AuditLogMapper)


    async def get_by_id(self, log_id: int) -> Optional[AuditLog]:
        """
        Get an audit log by its ID.

        Args:
            log_id: The ID of the audit log

        Returns:
            The audit log if found, None otherwise
        """
        query = select(AuditLogORM).where(AuditLogORM.id == log_id)
        result = await self._session.execute(query)
        audit_log_orm = result.scalars().first()

        if audit_log_orm is None:
            return None

        return AuditLogMapper.to_domain(audit_log_orm)

    async def get_recent(self, limit: int = 100) -> List[AuditLog]:
        """
        Get the most recent audit logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of recent audit logs
        """
        query = select(AuditLogORM).order_by(AuditLogORM.timestamp.desc()).limit(limit)
        result = await self._session.execute(query)
        audit_log_orms = result.scalars().all()

        return AuditLogMapper.to_domain_list(audit_log_orms)

