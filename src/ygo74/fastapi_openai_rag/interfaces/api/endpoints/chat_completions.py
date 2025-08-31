"""OpenAI-compatible chat completions endpoints."""
from typing import List, Dict, Any, Union
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime

from ..utils.override_stream_response import OverrideStreamResponse
from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.chat_completion_service import ChatCompletionService
from ....domain.models.chat_completion import ChatCompletionRequest, ChatCompletionResponse
from ....domain.models.completion import CompletionRequest, CompletionResponse
from ..decorators.decorators import endpoint_handler, track_token_usage
from ....domain.models.autenticated_user import AuthenticatedUser
from ..security.auth import auth_jwt_or_api_key
from .models import map_model_list_to_response, ModelResponse
from ..utils.override_stream_response import OverrideStreamResponse
from ..utils.json_encoder import DateTimeEncoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
@track_token_usage()  # Track token usage automatically
async def create_completion(
    request: Request,
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
    response = await service.create_completion(completion_request, user=user)
    return response

@router.post("/chat/completions", response_model=ChatCompletionResponse)
@endpoint_handler("create_chat_completion")
@track_token_usage()  # Track token usage automatically
async def create_chat_completion(
    request: Request,
    chat_completion_request: ChatCompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Any:  # Return type is either ChatCompletionResponse or OverrideStreamResponse
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
    if chat_completion_request.stream:
        # Return streaming response
        async def generate_stream():
            logger.debug("Starting SSE streaming generation")
            try:
                async for chunk in service.create_chat_completion_stream(chat_completion_request, user=user):
                    # Serialize the chunk with proper content type and format
                    if hasattr(chunk, 'model_dump_json'):
                        # For newer Pydantic (v2+)
                        json_str = chunk.model_dump_json()
                    elif hasattr(chunk, 'json'):
                        # For older Pydantic versions
                        json_str = chunk.json()
                    else:
                        # Fallback to manual serialization
                        json_str = json.dumps(chunk, cls=DateTimeEncoder)

                    # Log what we're sending
                    logger.debug(f"Streaming chunk: data: {json_str[:50]}...")

                    # Proper SSE format requires "data: " prefix and double newline
                    # Ensure exact formatting as expected by OpenAI clients
                    formatted_data = f"data: {json_str}\r\n\r\n"
                    yield formatted_data

                logger.debug("Sending [DONE] marker for SSE")
                # Signal the end of the stream with [DONE]
                yield "data: [DONE]\r\n\r\n"

            except Exception as e:
                logger.error(f"Error in stream generation: {str(e)}", exc_info=True)
                # If an error occurs, send it as part of the stream
                error_json = json.dumps({"error": {"message": str(e), "type": "stream_error"}})
                yield f"data: {error_json}\r\n\r\n"
                yield "data: [DONE]\r\n\r\n"

        return OverrideStreamResponse(
            generate_stream(),
            media_type="text/event-stream",  # Correct media type for SSE
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Important for nginx
                "Content-Type": "text/event-stream; charset=utf-8"
            }
        )
    else:
        # Regular response
        response = await service.create_chat_completion(chat_completion_request, user=user)
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
    logger.debug(f"Fetching models for user {user.username} with groups: {user.groups}")

    # Use service to get models based on user groups
    models = service.get_models_for_user(user)

    # Convert domain models to OpenAI API compatible format
    return map_model_list_to_response(models)

