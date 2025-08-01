"""OpenAI-compatible chat completions endpoints."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
import logging
import json

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.chat_completion_service import ChatCompletionService, LLMClientProtocol
from ....domain.models.chat_completion import ChatCompletionRequest, ChatCompletionResponse
from ....domain.models.completion import CompletionRequest, CompletionResponse
from ....domain.models.llm import LLMProvider
from ..decorators import endpoint_handler

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

@router.post("/chat/completions", response_model=ChatCompletionResponse)
@endpoint_handler("create_chat_completion")
async def create_chat_completion(
    request: ChatCompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service)
) -> ChatCompletionResponse:
    """Create a chat completion.

    Compatible with OpenAI's /v1/chat/completions endpoint.
    Supports both streaming and non-streaming responses.

    Args:
        request (ChatCompletionRequest): Chat completion request
        service (ChatCompletionService): Service instance

    Returns:
        ChatCompletionResponse: Generated chat completion or StreamingResponse
    """
    if request.stream:
        # Return streaming response
        async def generate_stream():
            async for chunk in service.create_chat_completion_stream(request):
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
        response = await service.create_chat_completion(request)
        return response

@router.post("/completions", response_model=CompletionResponse)
@endpoint_handler("create_completion")
async def create_completion(
    request: CompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service)
) -> CompletionResponse:
    """Create a text completion.

    Compatible with OpenAI's /v1/completions endpoint.

    Args:
        request (CompletionRequest): Text completion request
        service (ChatCompletionService): Service instance

    Returns:
        CompletionResponse: Generated text completion
    """
    response = await service.create_completion(request)
    return response

@router.get("/models")
@endpoint_handler("list_models")
async def list_models(
    service: ChatCompletionService = Depends(get_chat_completion_service)
) -> Dict[str, Any]:
    """List available models.

    Compatible with OpenAI's /v1/models endpoint.

    Returns:
        Dict[str, Any]: List of available models
    """
    # This would typically be implemented by fetching from the model service
    # For now, return a placeholder response
    return {
        "object": "list",
        "data": []
    }
