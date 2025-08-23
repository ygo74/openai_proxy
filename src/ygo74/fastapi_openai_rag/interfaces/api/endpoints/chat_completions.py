"""OpenAI-compatible chat completions endpoints."""
from typing import List
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging
import json

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.chat_completion_service import ChatCompletionService
from ....domain.models.chat_completion import ChatCompletionRequest, ChatCompletionResponse
from ....domain.models.completion import CompletionRequest, CompletionResponse
from ..decorators import endpoint_handler
from ....domain.models.autenticated_user import AuthenticatedUser
from ..security.auth import auth_jwt_or_api_key
from .models import map_model_list_to_response, ModelResponse

logger = logging.getLogger(__name__)

router = APIRouter()

def get_chat_completion_service(db: Session = Depends(get_db)) -> ChatCompletionService:
    """Create ChatCompletionService instance with Unit of Work.

    Args:
        db (Session): Database session

    Returns:
        ChatCompletionService: Service instance
    """
    session_factory = lambda: db
    uow = SQLUnitOfWork(session_factory)
    return ChatCompletionService(uow)

@router.post("/completions", response_model=CompletionResponse)
@endpoint_handler("create_completion")
async def create_completion(
    completion_request: CompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> CompletionResponse:
    """Create a text completion.

    Compatible with OpenAI's /v1/completions endpoint.
    Requires authentication via API key or Bearer token.

    Args:
        completion_request (CompletionRequest): Text completion request
        service (ChatCompletionService): Service instance
        user (AuthenticatedUser): Authenticated user with group memberships

    Returns:
        CompletionResponse: Generated text completion
    """
    # Extract user groups for authorization
    user_groups = user.groups if user else None

    response = await service.create_completion(completion_request, user_groups=user_groups)
    return response

@router.post("/chat/completions", response_model=ChatCompletionResponse)
@endpoint_handler("create_chat_completion")
async def create_chat_completion(
    request: ChatCompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> ChatCompletionResponse:
    """Create a chat completion.

    Compatible with OpenAI's /v1/chat/completions endpoint.
    Supports both streaming and non-streaming responses.

    Args:
        request (ChatCompletionRequest): Chat completion request
        service (ChatCompletionService): Service instance
        user (AuthenticatedUser): Authenticated user with group memberships

    Returns:
        ChatCompletionResponse: Generated chat completion or StreamingResponse
    """
    # Extract user groups for authorization
    user_groups = user.groups if user else None

    if request.stream:
        # Return streaming response
        async def generate_stream():
            async for chunk in service.create_chat_completion_stream(request, user_groups=user_groups):
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
    else:
        # Regular response
        response = await service.create_chat_completion(request, user_groups=user_groups)
        return response

@router.get("/models")
@endpoint_handler("list_models")
async def list_models(
    service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> List[ModelResponse]:
    """List available models.

    Compatible with OpenAI's /v1/models endpoint.
    Returns only models that the user has access to based on their group membership.

    Args:
        service (ChatCompletionService): Chat completion service
        user (AuthenticatedUser): Authenticated user information

    Returns:
        List[ModelResponse]: List of models the user has access to
    """
    # Get all models accessible to the user based on their groups
    user_groups = user.groups
    logger.debug(f"Fetching models for user {user.username} with groups: {user_groups}")

    # Use service to get models based on user groups
    models = service.get_models_for_user(user_groups)

    # Convert domain models to OpenAI API compatible format
    return map_model_list_to_response(models)

