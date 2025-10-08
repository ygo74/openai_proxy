"""OpenAI-compatible Embeddings API endpoint."""
from typing import Any
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.chat_completion_service import ChatCompletionService
from ....domain.models.autenticated_user import AuthenticatedUser
from ....domain.models.embedding import EmbeddingCreatePayload, CreateEmbeddingResponse
from ..decorators.decorators import endpoint_handler
from ..security.auth import auth_jwt_or_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

def get_chat_completion_service(db: Session = Depends(get_db)) -> ChatCompletionService:
    """Provide ChatCompletionService with Unit of Work.

    Args:
        db (Session): SQLAlchemy session

    Returns:
        ChatCompletionService: service instance
    """
    session_factory = lambda: db  # noqa: E731
    uow = SQLUnitOfWork(session_factory)
    return ChatCompletionService(uow)

@router.post("/embeddings")
@endpoint_handler("create_embeddings")
async def create_embeddings_endpoint(
    request: Request,
    payload: EmbeddingCreatePayload,
    service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> CreateEmbeddingResponse:
    """Create embeddings for the given input text(s).

    Args:
        request: FastAPI request object
        payload: Embedding creation payload
        service: Chat completion service (handles embeddings too)
        user: Authenticated user

    Returns:
        CreateEmbeddingResponse: OpenAI-compatible embedding response
    """
    logger.info(f"Creating embeddings for user {user.username} with model {payload.model}")

    # Token tracking is handled in the service layer
    return await service.create_embedding(payload, user)
