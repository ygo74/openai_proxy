"""Chat completion endpoint for V1 API."""
from fastapi import APIRouter, Depends, Request, Body, HTTPException
from typing import Optional, Dict, Any

from .....domain.models.chat_completion import ChatCompletionRequest, ChatCompletionResponse
from .....domain.models.autenticated_user import AuthenticatedUser
from .....application.services.chat_completion_service import ChatCompletionService
from .....infrastructure.db.unit_of_work import SQLUnitOfWork

from ...decorators.decorators import endpoint_handler, require_apikey_or_bearer, track_token_usage

router = APIRouter()

@router.post("/chat/completions", response_model=ChatCompletionResponse)
@endpoint_handler("chat_completion")
@require_apikey_or_bearer()
@track_token_usage()  # Track token usage automatically
async def create_chat_completion(
    request: Request,
    chat_request: ChatCompletionRequest = Body(...),
    user: AuthenticatedUser = None
) -> ChatCompletionResponse:
    """Create a chat completion with the given model."""
    uow = SQLUnitOfWork()
    service = ChatCompletionService(uow)

    # Get user groups for authorization check
    user_groups = user.groups if user else None

    # Handle streaming requests differently if needed
    if chat_request.stream:
        # Implementation for streaming would go here
        pass

    # Process normal request
    try:
        response = await service.create_chat_completion(chat_request, user_groups)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
