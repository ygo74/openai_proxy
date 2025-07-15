from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from typing import Dict, Any, List
from pydantic import BaseModel
from src.infrastructure.database import get_db
from src.core.application.group_service import GroupService
import logging

groups_router = APIRouter(prefix="/groups", tags=["groups"])
logger = logging.getLogger(__name__)

class GroupRequest(BaseModel):
    name: str
    description: str | None = None

class GroupUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None

class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None = None

@groups_router.post("/", response_model=Dict[str, Any])
async def create_group(request: GroupRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create a new group."""
    logger.info(f"Creating new group with name: {request.name}")
    service = GroupService(db)
    try:
        result = service.add_or_update_group(name=request.name, description=request.description)
        logger.info(f"Group created successfully with id: {result['group'].id}")
        return result
    except ValueError as e:
        logger.error(f"Failed to create group: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@groups_router.put("/{group_id}", response_model=Dict[str, Any])
async def update_group(group_id: int, request: GroupUpdateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Update an existing group."""
    logger.info(f"Updating group {group_id}")
    logger.debug(f"Update data: name={request.name}, description={request.description}")

    service = GroupService(db)
    try:
        result = service.add_or_update_group(
            group_id=group_id,
            name=request.name,
            description=request.description
        )
        logger.info(f"Group {group_id} updated successfully")
        return result
    except NoResultFound as e:
        logger.error(f"Group not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.error(f"Invalid update data: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@groups_router.get("/", response_model=List[GroupResponse])
async def list_groups(db: Session = Depends(get_db)) -> List[GroupResponse]:
    """Get all groups."""
    logger.info("Fetching all groups")
    service = GroupService(db)
    groups = service.get_all_groups()
    logger.debug(f"Found {len(groups)} groups")
    return [GroupResponse(**group) for group in groups]

@groups_router.delete("/{group_id}")
async def remove_group(group_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Delete a group."""
    logger.info(f"Deleting group {group_id}")
    service = GroupService(db)
    try:
        result = service.delete_group(group_id)
        logger.info(f"Group {group_id} deleted successfully")
        return result
    except NoResultFound as e:
        logger.error(f"Failed to delete group: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))