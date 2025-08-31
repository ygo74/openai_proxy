"""Model ORM implementation."""
from typing import Dict, Any, List  # removed Optional
from sqlalchemy import String, DateTime, UniqueConstraint, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from ....domain.models.llm_model import LlmModelStatus
from .base import Base
from .model_authorization import model_authorization
from .group_orm import GroupORM

class ModelORM(Base):
    """SQLAlchemy model for LLM models without polymorphism.

    Attributes:
        id (int): Primary key
        url (str): Model API endpoint URL
        name (str): Model display name
        technical_name (str): Unique technical identifier
        status (LlmModelStatus): Current model status
        provider (str): LLM provider type
        created (datetime): Creation timestamp
        updated (datetime): Last update timestamp
        capabilities (JSON): Model capabilities configuration
        groups (List[GroupORM]): Groups with access to this model
    """
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    technical_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[LlmModelStatus] = mapped_column(
        SQLEnum(LlmModelStatus),
        nullable=False,
        default=LlmModelStatus.NEW
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    capabilities: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )

    __table_args__ = (
        UniqueConstraint("name", "technical_name", name="uq_name_technical_name"),
    )

    # Relationships
    groups: Mapped[List["GroupORM"]] = relationship(
        "GroupORM",
        secondary=model_authorization,
        back_populates="models"
    )