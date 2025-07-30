"""Model ORM implementation."""
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, DateTime, UniqueConstraint, JSON, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from ....domain.models.llm_model import LlmModelStatus
from .base import Base
from .model_authorization import model_authorization

class ModelORM(Base):
    """SQLAlchemy model for LLM models.

    Attributes:
        id (int): Primary key
        url (str): Model API endpoint URL
        name (str): Model display name
        technical_name (str): Unique technical identifier
        status (ModelStatus): Current model status
        provider (str): LLM provider type
        model_type (str): Discriminator column for polymorphic inheritance
        api_version (Optional[str]): API version for Azure models
        created (datetime): Creation timestamp
        updated (datetime): Last update timestamp
        capabilities (JSON): Model capabilities configuration
        groups (List[GroupORM]): Groups with access to this model
    """
    __tablename__ = "models"

    # Polymorphic configuration
    __mapper_args__ = {
        "polymorphic_identity": "standard",
        "polymorphic_on": "model_type",
    }

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    technical_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    api_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
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
        UniqueConstraint("technical_name", name="uq_technical_name"),
    )

    # Relationships
    groups: Mapped[List["GroupORM"]] = relationship(
        "GroupORM",
        secondary=model_authorization,
        back_populates="models"
    )


class AzureModelORM(ModelORM):
    """SQLAlchemy model for Azure LLM models."""

    __mapper_args__ = {
        "polymorphic_identity": "azure",
    }

    def __init__(self, **kwargs):
        """Initialize Azure model with required api_version."""
        if 'api_version' not in kwargs or not kwargs['api_version']:
            raise ValueError("api_version is required for Azure models")
        super().__init__(**kwargs)