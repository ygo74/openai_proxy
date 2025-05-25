from typing import Any
from sqlalchemy import Column, String, DateTime, UniqueConstraint, JSON, Integer, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from enum import Enum as PyEnum

Base = declarative_base()

class ModelStatus(PyEnum):
    NEW = "NEW"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"

class Model(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    name = Column(String, nullable=False)
    technical_name = Column(String, unique=True, nullable=False)
    status = Column(Enum(ModelStatus), nullable=False)
    created = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    capabilities = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("technical_name", name="uq_technical_name"),
    )