"""User domain model."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class ApiKey(BaseModel):
    """API Key domain model."""
    id: str
    key_hash: str  # Stored hashed, never plain text
    name: Optional[str] = None
    user_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    last_used_at: Optional[datetime] = None

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValueError('API Key ID cannot be empty')
        return v

    @field_validator('key_hash')
    @classmethod
    def validate_key_hash(cls, v):
        if not v or not v.strip():
            raise ValueError('Key hash cannot be empty')
        return v

    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v

class User(BaseModel):
    """User domain model."""
    id: str
    username: str
    email: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    groups: List[str] = Field(default_factory=list)
    api_keys: List[ApiKey] = Field(default_factory=list)

    @field_validator('id')
    @classmethod
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        return v
