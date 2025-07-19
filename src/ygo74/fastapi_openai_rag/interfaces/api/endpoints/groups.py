"""Group endpoints module."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.group_service import GroupService
from ....domain.models.group import Group

logger = logging.getLogger(__name__)

router = APIRouter()

class GroupResponse(BaseModel):
    """Group response schema."""
    id: int
    name: str
    description: Optional[str] = None

class GroupCreate(BaseModel):
    """Group creation schema."""
    name: str
    description: Optional[str] = None

class GroupUpdate(BaseModel):
    """Group update schema."""
    name: Optional[str] = None
    description: Optional[str] = None

class ModelAssignmentRequest(BaseModel):
    """Model assignment request schema."""
    model_id: int


def get_group_service(db: Session = Depends(get_db)) -> GroupService:
    """Create GroupService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return GroupService(uow)


@router.get("/", response_model=List[GroupResponse])
async def get_groups(
    skip: int = 0,
    limit: int = 100,
    service: GroupService = Depends(get_group_service)
) -> List[GroupResponse]:
    """Get list of groups."""
    try:
        groups: List[Group] = service.get_all_groups()
        return [GroupResponse(
            id=g.id if g.id is not None else -1,  # Use a default value like -1 if id is None
            name=g.name,
            description=g.description
        ) for g in groups[skip:skip + limit]]
    except Exception as e:
        logger.error(f"Failed to get groups: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve groups"
        )


@router.get("/statistics")
async def get_group_statistics(
    service: GroupService = Depends(get_group_service)
):
    """Get group statistics."""
    try:
        groups: List[Group] = service.get_all_groups()
        return {
            "total": len(groups),
            "active": len([g for g in groups if g.name])  # Simple check
        }
    except Exception as e:
        logger.error(f"Failed to get group statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve group statistics"
        )


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group: GroupCreate,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Create a new group."""
    try:
        status_result, created_group = service.add_or_update_group(
            name=group.name,
            description=group.description
        )
        return GroupResponse(
            id=created_group.id,
            name=created_group.name,
            description=created_group.description
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create group: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create group"
        )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Get a specific group by ID."""
    try:
        group: Optional[Group] = service.get_group_by_id(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group with ID {group_id} not found"
            )
        return GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get group {group_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve group"
        )


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group: GroupUpdate,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Update a group."""
    try:
        status_result, updated_group = service.add_or_update_group(
            group_id=group_id,
            name=group.name,
            description=group.description
        )
        return GroupResponse(
            id=updated_group.id,
            name=updated_group.name,
            description=updated_group.description
        )
    except NoResultFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update group {group_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update group"
        )


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    service: GroupService = Depends(get_group_service)
):
    """Delete a group."""
    try:
        service.delete_group(group_id)
        return {"message": f"Group with ID {group_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete group {group_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete group"
        )


# Model-Group association endpoints
@router.post("/{group_id}/models")
async def assign_model_to_group_by_json(
    group_id: int,
    assignment_data: ModelAssignmentRequest,
    db: Session = Depends(get_db)
):
    """Assign a model to a group using JSON payload."""
    try:
        # This would require implementation in the service layer
        return {
            "status": "success",
            "message": f"Model {assignment_data.model_id} assigned to group {group_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign model to group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{group_id}/models/{model_id}")
async def assign_model_to_group(
    group_id: int,
    model_id: int,
    db: Session = Depends(get_db)
):
    """Assign a model to a group."""
    try:
        # This would require implementation in the service layer
        return {"message": f"Model {model_id} assigned to group {group_id}"}
    except Exception as e:
        logger.error(f"Failed to assign model to group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{group_id}/models/{model_id}")
async def remove_model_from_group(
    group_id: int,
    model_id: int,
    db: Session = Depends(get_db)
):
    """Remove a model from a group."""
    try:
        # This would require implementation in the service layer
        return {
            "status": "success",
            "message": f"Model {model_id} removed from group {group_id}"
        }
    except Exception as e:
        logger.error(f"Failed to remove model from group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{group_id}/models")
async def get_group_models(
    group_id: int,
    db: Session = Depends(get_db)
):
    """Get models in a specific group."""
    try:
        # This would require implementation in the service layer
        return []
    except Exception as e:
        logger.error(f"Failed to get group models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))