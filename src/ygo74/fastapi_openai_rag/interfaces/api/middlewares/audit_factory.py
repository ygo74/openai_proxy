from typing import List, Optional

from ygo74.fastapi_openai_rag.application.services.audit_service import AuditService
from ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig, HttpForwarderConfig
from ygo74.fastapi_openai_rag.infrastructure.db.repositories.audit_log_repository import AuditLogRepository
from ygo74.fastapi_openai_rag.interfaces.api.middlewares.audit import (
    AuditMiddleware, BaseForwarder, PrintForwarder, HTTPForwarder
)
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from fastapi import FastAPI

class AuditFactory:
    """
    Factory class for creating audit-related components.
    """

    @staticmethod
    def create_audit_service() -> AuditService:
        """Create AuditService instance with Unit of Work.

        Returns:
            AuditService: Configured audit service with proper session management
        """
        # Create unit of work that uses SessionManager internally
        uow = SQLUnitOfWork()

        # Return the audit service with the unit of work
        return AuditService(uow)

    @staticmethod
    def get_audit_service() -> AuditService:
        """Get a properly configured audit service instance.

        Returns:
            AuditService: The audit service instance
        """
        return AuditFactory.create_audit_service()

    @staticmethod
    def create_forwarders(config: AppConfig) -> List[BaseForwarder]:
        """
        Create a list of forwarders based on configuration.

        Args:
            config: AppConfig instance with forwarder settings

        Returns:
            List of configured forwarders
        """
        forwarders: List[BaseForwarder] = []

        # Configure print forwarder if enabled
        if config.forwarders.print.enabled:
            forwarders.append(PrintForwarder(level=config.forwarders.print.level))

        # Configure HTTP forwarders
        for http_config in config.forwarders.http:
            if http_config.enabled:
                forwarders.append(
                    HTTPForwarder(
                        url=http_config.url,
                        headers=http_config.headers,
                        retry_count=http_config.retry_count,
                        timeout_seconds=http_config.timeout_seconds
                    )
                )

        return forwarders

    @staticmethod
    def create_audit_middleware(
        app: FastAPI,
        config: Optional[AppConfig] = None,
        audit_service: Optional[AuditService] = None,
        forwarders: Optional[List[BaseForwarder]] = None
    ):
        """
        Create and configure the AuditMiddleware.

        Args:
            app: The ASGI application
            config: Application configuration
            audit_service: Optional pre-configured audit service
            forwarders: Optional pre-configured list of forwarders

        Returns:
            Configured AuditMiddleware
        """
        # Create components if not provided
        if audit_service is None and (config is None or config.audit.db_enabled):
            audit_service = AuditFactory.create_audit_service()

        if forwarders is None and config is not None:
            forwarders = AuditFactory.create_forwarders(config)
        elif forwarders is None:
            forwarders = []

        app.add_middleware(AuditMiddleware, audit_service=audit_service, forwarders=forwarders)
