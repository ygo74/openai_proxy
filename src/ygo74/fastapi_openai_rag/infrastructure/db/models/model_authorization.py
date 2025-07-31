"""Model authorization association table."""
from sqlalchemy import Table, Column, Integer, ForeignKey
from .base import Base

metadata = Base.metadata

model_authorization = Table(
    "model_authorization",
    metadata,
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True),
    Column("model_id", Integer, ForeignKey("models.id"), primary_key=True)
)