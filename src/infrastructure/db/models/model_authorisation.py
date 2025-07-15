from sqlalchemy import Column, Integer, Table, ForeignKey
from src.infrastructure.db.models.base import Base

model_authorisation = Table(
    "model_authorisation",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True),
    Column("model_id", Integer, ForeignKey("models.id"), primary_key=True)
)

