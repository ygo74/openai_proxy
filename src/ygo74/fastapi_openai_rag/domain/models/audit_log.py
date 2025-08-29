from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class AuditLog(BaseModel):
    """
    Domain model for audit log entries.
    Records API request information for auditing and monitoring.
    """
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    method: str
    path: str
    user: Optional[str] = None
    auth_type: Optional[str] = None
    status_code: int
    duration_ms: float
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        validate_assignment = True
