"""Token usage ORM model."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class TokenUsageORM(Base):
    """ORM model for token usage tracking."""

    __tablename__ = "token_usages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    model = Column(String(255), nullable=False, index=True)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    request_id = Column(String(36), nullable=True)
    endpoint = Column(String(255), nullable=False)
