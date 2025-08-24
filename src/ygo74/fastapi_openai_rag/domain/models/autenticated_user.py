from pydantic import BaseModel
from typing import Optional

class AuthenticatedUser(BaseModel):
    id: str
    username: Optional[str]
    type: str  # "api_key" ou "jwt"
    groups: list[str] = []
