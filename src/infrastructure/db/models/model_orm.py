from sqlalchemy import Column, String, DateTime, UniqueConstraint, JSON, Integer, Enum, Table, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.core.models.domain import ModelStatus
from src.infrastructure.db.models.base import Base
from src.infrastructure.db.models.model_authorisation import model_authorisation


class ModelORM(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    name = Column(String, nullable=False)
    technical_name = Column(String, unique=True, nullable=False)
    status = Column(Enum(ModelStatus), nullable=False)
    created = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), nullable=False)
    capabilities = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("technical_name", name="uq_technical_name"),
    )

    groups = relationship("GroupORM", secondary=model_authorisation, back_populates="models")