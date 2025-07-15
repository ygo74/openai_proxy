from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.infrastructure.db.models.base import Base
from src.infrastructure.db.models.model_orm import model_authorisation


class GroupORM(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    models = relationship("ModelORM", secondary=model_authorisation, back_populates="groups")

