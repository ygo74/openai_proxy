from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Integer, String, Float, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from ygo74.fastapi_openai_rag.infrastructure.db.models.base import Base


class AuditLogORM(Base):
    """
    SQLAlchemy ORM model for audit logs.
    Stores API request information in the database.
    """
    __tablename__ = "audit_logs"
    # Add extend_existing=True to prevent conflicts with Alembic migrations
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    user: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    auth_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    request_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
