"""Base SQLAlchemy ORM model."""
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime
import logging

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Base class for all ORM models."""

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc)
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )

# Import all models to ensure they are registered with Base.metadata
logger.debug("Importing ORM models...")

try:
    from .model_orm import ModelORM, AzureModelORM
    logger.debug("ModelORM and AzureModelORM imported")
except ImportError as e:
    logger.warning(f"Could not import ModelORM: {e}")

try:
    from .group_orm import GroupORM
    logger.debug("GroupORM imported")
except ImportError as e:
    logger.warning(f"Could not import GroupORM: {e}")

try:
    from .user_orm import UserORM
    logger.debug("UserORM imported")
except ImportError as e:
    logger.warning(f"Could not import UserORM: {e}")

try:
    from .model_authorization import model_authorization
    logger.debug("model_authorization table imported")
except ImportError as e:
    logger.warning(f"Could not import model_authorization: {e}")

logger.info(f"Base metadata contains {len(Base.metadata.tables)} tables: {list(Base.metadata.tables.keys())}")