from typing import List

from ygo74.fastapi_openai_rag.domain.models.audit_log import AuditLog
from ygo74.fastapi_openai_rag.infrastructure.db.models.audit_log_orm import AuditLogORM


class AuditLogMapper:
    """
    Mapper for converting between AuditLog domain model and AuditLogORM database model.
    """

    @staticmethod
    def to_domain(orm: AuditLogORM) -> AuditLog:
        """
        Convert ORM model to domain model.

        Args:
            orm: The ORM model to convert

        Returns:
            The domain model
        """
        return AuditLog(
            id=orm.id,
            timestamp=orm.timestamp,
            method=orm.method,
            path=orm.path,
            user=orm.user,
            auth_type=orm.auth_type,
            status_code=orm.status_code,
            duration_ms=orm.duration_ms,
            metadata=orm.request_metadata
        )

    @staticmethod
    def to_orm(domain: AuditLog) -> AuditLogORM:
        """
        Convert domain model to ORM model.

        Args:
            domain: The domain model to convert

        Returns:
            The ORM model
        """
        return AuditLogORM(
            id=domain.id,
            timestamp=domain.timestamp,
            method=domain.method,
            path=domain.path,
            user=domain.user,
            auth_type=domain.auth_type,
            status_code=domain.status_code,
            duration_ms=domain.duration_ms,
            metadata=domain.metadata
        )

    @staticmethod
    def to_domain_list(orm_list: List[AuditLogORM]) -> List[AuditLog]:
        """
        Convert a list of ORM models to domain models.

        Args:
            orm_list: List of ORM models to convert

        Returns:
            List of domain models
        """
        return [AuditLogMapper.to_domain(orm) for orm in orm_list]
