from pydantic import BaseModel
from typing import Optional
from .llm_model import LlmModel

class AuthenticatedUser(BaseModel):
    id: str
    username: str
    type: str  # "api_key" ou "jwt"
    groups: list[str] = []
    models: list[LlmModel] = []
