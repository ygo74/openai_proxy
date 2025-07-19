"""Group endpoints module."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.group_service import GroupService
from ....domain.models.group import Group
from ..decorators import endpoint_handler

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


def get_group_service(db: Session = Depends(get_db)) -> GroupService:
    """Create GroupService instance with Unit of Work."""
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return GroupService(uow)


@router.get("/", response_model=List[GroupResponse])
@endpoint_handler("get_groups")
async def get_groups(
    skip: int = 0,
    limit: int = 100,
    service: GroupService = Depends(get_group_service)
) -> List[GroupResponse]:
    """Get list of groups."""
    groups: List[Group] = service.get_all_groups()

    # Apply pagination
    paginated_groups = groups[skip:skip + limit]

    return [GroupResponse(
        id=g.id if g.id is not None else -1,
        name=g.name,
        description=g.description
    ) for g in paginated_groups]


@router.post("/", response_model=GroupResponse, status_code=201)
@endpoint_handler("create_group")
async def create_group(
    group: GroupCreate,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Create a new group."""
    status_result, created_group = service.add_or_update_group(
        name=group.name,
        description=group.description
    )
    return GroupResponse(
        id=created_group.id,
        name=created_group.name,
        description=created_group.description
    )


@router.get("/statistics")
@endpoint_handler("get_group_statistics")
async def get_group_statistics(
    service: GroupService = Depends(get_group_service)
) -> Dict[str, Any]:
    """Get group statistics."""
    groups: List[Group] = service.get_all_groups()

    stats = {
        "total": len(groups),
        "active": len([g for g in groups if g.name and g.name.strip()])
    }

    return stats


@router.get("/{group_id}", response_model=GroupResponse)
@endpoint_handler("get_group")
async def get_group(
    group_id: int,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Get a specific group by ID."""
    group: Group = service.get_group_by_id(group_id)
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description
    )


@router.put("/{group_id}", response_model=GroupResponse)
@endpoint_handler("update_group")
async def update_group(
    group_id: int,
    group: GroupUpdate,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Update a group."""
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


@router.delete("/{group_id}")
@endpoint_handler("delete_group")
async def delete_group(
    group_id: int,
    service: GroupService = Depends(get_group_service)
):
    """Delete a group."""
    service.delete_group(group_id)
    return {"message": f"Group with ID {group_id} deleted successfully"}


@router.get("/name/{name}", response_model=GroupResponse)
@endpoint_handler("get_group_by_name")
async def get_group_by_name(
    name: str,
    service: GroupService = Depends(get_group_service)
) -> GroupResponse:
    """Get a group by name."""
    group: Group = service.get_group_by_name(name)
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description
    )


@router.get("/search/", response_model=List[GroupResponse])
@endpoint_handler("search_groups")
async def search_groups_by_name(
    name: str,
    service: GroupService = Depends(get_group_service)
) -> List[GroupResponse]:
    """Search groups by name (partial match)."""
    groups: List[Group] = service.get_all_groups()

    # Simple name filtering
    filtered_groups = [g for g in groups if name.lower() in g.name.lower()]

    return [GroupResponse(
        id=g.id,
        name=g.name,
        description=g.description
    ) for g in filtered_groups]