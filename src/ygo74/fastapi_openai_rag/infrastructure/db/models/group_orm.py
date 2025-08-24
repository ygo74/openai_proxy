"""SQLAlchemy ORM models for groups."""
from typing import List
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from .model_authorization import model_authorization


class GroupORM(Base):
    """ORM model for groups.

    Attributes:
        id (int): Primary key
        name (str): Group name
        description (str): Group description
        created (datetime): Creation timestamp
        updated (datetime): Last update timestamp
        models (List[ModelORM]): Associated models
    """
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    models: Mapped[List["ModelORM"]] = relationship(
        "ModelORM",
        secondary=model_authorization,
        back_populates="groups"
    )