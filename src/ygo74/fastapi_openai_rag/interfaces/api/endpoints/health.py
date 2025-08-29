"""Health check endpoints."""
from datetime import datetime, timezone
import time
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from ....infrastructure.db.session import get_db
from ....application.services.config_service import config_service
from ..decorators.decorators import endpoint_handler
from ..security.auth import auth_jwt_or_api_key
from ....domain.models.autenticated_user import AuthenticatedUser
from ....domain.models.configuration import AppConfig


logger = logging.getLogger(__name__)

router = APIRouter()

class HealthStatus:
    """Health check status constants."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"

@router.get("/whoami")
@endpoint_handler("whoami")
async def whoami(
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Dict[str, Any]:
    """Get current user information from token.

    Args:
        user (AuthenticatedUser): Authenticated user

    Returns:
        Dict[str, Any]: Current user information
    """
    return {
        "authenticated": True,
        "user_id": user.id,
        "username": user.username,
        "auth_type": user.type,
        "groups": user.groups
    }


@router.get("/health")
@endpoint_handler("health_check")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint.

    Returns:
        Dict[str, Any]: Basic health status
    """
    return {
        "status": HealthStatus.HEALTHY,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "service": "fastapi-openai-rag"
    }

@router.get("/health/detailed")
@endpoint_handler("detailed_health_check")
async def detailed_health_check(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Detailed health check with component status.

    Args:
        db (Session): Database session

    Returns:
        Dict[str, Any]: Detailed health status
    """
    start_time = time.time()
    checks: List[Dict[str, Any]] = []
    overall_status = HealthStatus.HEALTHY

    # Check 1: Database connectivity
    db_status = await check_database(db)
    checks.append(db_status)
    if db_status["status"] != HealthStatus.HEALTHY:
        overall_status = HealthStatus.UNHEALTHY

    # Check 2: Configuration
    config_status = check_configuration()
    checks.append(config_status)
    if config_status["status"] != HealthStatus.HEALTHY and overall_status == HealthStatus.HEALTHY:
        overall_status = HealthStatus.DEGRADED

    # Check 3: Dependencies
    deps_status = check_dependencies()
    checks.append(deps_status)
    if deps_status["status"] != HealthStatus.HEALTHY and overall_status == HealthStatus.HEALTHY:
        overall_status = HealthStatus.DEGRADED

    response_time = round((time.time() - start_time) * 1000, 2)

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "service": "fastapi-openai-rag",
        "response_time_ms": response_time,
        "checks": checks
    }

@router.get("/health/ready")
@endpoint_handler("readiness_check")
async def readiness_check(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Readiness check - indicates if service is ready to accept requests.

    Args:
        db (Session): Database session

    Returns:
        Dict[str, Any]: Readiness status

    Raises:
        HTTPException: If service is not ready
    """
    # Check database connectivity
    db_status = await check_database(db)
    if db_status["status"] != HealthStatus.HEALTHY:
        raise HTTPException(status_code=503, detail="Service not ready - database unavailable")

    # Check configuration
    config_status = check_configuration()
    if config_status["status"] != HealthStatus.HEALTHY:
        raise HTTPException(status_code=503, detail="Service not ready - configuration error")

    return {
        "status": HealthStatus.HEALTHY,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Service is ready"
    }

@router.get("/health/live")
@endpoint_handler("liveness_check")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check - indicates if service is alive.

    Returns:
        Dict[str, Any]: Liveness status
    """
    return {
        "status": HealthStatus.HEALTHY,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Service is alive"
    }

async def check_database(db: Session) -> Dict[str, Any]:
    """Check database connectivity.

    Args:
        db (Session): Database session

    Returns:
        Dict[str, Any]: Database check result
    """
    try:
        start_time = time.time()

        # Simple query to test connectivity
        result = db.execute(text("SELECT 1 as health_check"))
        row = result.fetchone()

        response_time = round((time.time() - start_time) * 1000, 2)

        if row and row[0] == 1:
            return {
                "name": "database",
                "status": HealthStatus.HEALTHY,
                "response_time_ms": response_time,
                "message": "Database connection successful"
            }
        else:
            return {
                "name": "database",
                "status": HealthStatus.UNHEALTHY,
                "response_time_ms": response_time,
                "message": "Database query returned unexpected result"
            }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "name": "database",
            "status": HealthStatus.UNHEALTHY,
            "response_time_ms": 0,
            "message": f"Database connection failed: {str(e)}"
        }

def check_configuration() -> Dict[str, Any]:
    """Check configuration status.

    Returns:
        Dict[str, Any]: Configuration check result
    """
    try:
        # Check if configuration is loaded
        config: AppConfig = config_service.get_config()
        if config:

            # Verify database configuration
            if config.db_type.strip() == "":
                return {
                    "name": "configuration",
                    "status": HealthStatus.UNHEALTHY,
                    "message": "Database configuration missing"
                }

            return {
                "name": "configuration",
                "status": HealthStatus.HEALTHY,
                "message": "Configuration loaded successfully"
            }
        else:
            return {
                "name": "configuration",
                "status": HealthStatus.UNHEALTHY,
                "message": "Configuration not loaded"
            }

    except Exception as e:
        logger.error(f"Configuration health check failed: {e}")
        return {
            "name": "configuration",
            "status": HealthStatus.UNHEALTHY,
            "message": f"Configuration check failed: {str(e)}"
        }

def check_dependencies() -> Dict[str, Any]:
    """Check external dependencies.

    Returns:
        Dict[str, Any]: Dependencies check result
    """
    try:
        # For now, just check that required modules are importable
        import sqlalchemy
        import jose
        import httpx

        return {
            "name": "dependencies",
            "status": HealthStatus.HEALTHY,
            "message": "All dependencies available"
        }

    except ImportError as e:
        logger.error(f"Dependency check failed: {e}")
        return {
            "name": "dependencies",
            "status": HealthStatus.UNHEALTHY,
            "message": f"Missing dependency: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Dependencies health check failed: {e}")
        return {
            "name": "dependencies",
            "status": HealthStatus.UNHEALTHY,
            "message": f"Dependencies check failed: {str(e)}"
        }
