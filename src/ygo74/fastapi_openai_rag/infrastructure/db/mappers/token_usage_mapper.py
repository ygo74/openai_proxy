"""Mapper between domain and ORM token usage models."""
from typing import List
from ....domain.models.token_usage import TokenUsage
from ..models.token_usage_orm import TokenUsageORM

class TokenUsageMapper:
    """Mapper between domain and ORM token usage models."""

    @staticmethod
    def to_domain(orm: TokenUsageORM) -> TokenUsage:
        """Map ORM model to domain model.

        Args:
            orm (TokenUsageORM): ORM model instance

        Returns:
            TokenUsage: Domain model instance
        """
        return TokenUsage(
            id=orm.id,
            user_id=orm.user_id,
            model=orm.model,
            prompt_tokens=orm.prompt_tokens,
            completion_tokens=orm.completion_tokens,
            total_tokens=orm.total_tokens,
            timestamp=orm.timestamp,
            request_id=orm.request_id,
            endpoint=orm.endpoint
        )

    @staticmethod
    def to_orm(domain: TokenUsage) -> TokenUsageORM:
        """Map domain model to ORM model.

        Args:
            domain (TokenUsage): Domain model instance

        Returns:
            TokenUsageORM: ORM model instance
        """
        return TokenUsageORM(
            id=domain.id,
            user_id=domain.user_id,
            model=domain.model,
            prompt_tokens=domain.prompt_tokens,
            completion_tokens=domain.completion_tokens,
            total_tokens=domain.total_tokens,
            timestamp=domain.timestamp,
            request_id=domain.request_id,
            endpoint=domain.endpoint
        )

    @staticmethod
    def to_domain_list(orm_list: List[TokenUsageORM]) -> List[TokenUsage]:
        """Map list of ORM models to list of domain models.

        Args:
            orm_list (List[TokenUsageORM]): List of ORM models

        Returns:
            List[TokenUsage]: List of domain models
        """
        return [TokenUsageMapper.to_domain(orm) for orm in orm_list]
