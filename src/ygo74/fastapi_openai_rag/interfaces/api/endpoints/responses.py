"""OpenAI-compatible Responses API endpoint."""
from typing import Dict, Any, AsyncGenerator, cast
import json
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ....infrastructure.db.session import get_db
from ....infrastructure.db.unit_of_work import SQLUnitOfWork
from ....application.services.chat_completion_service import ChatCompletionService
from ....domain.models.autenticated_user import AuthenticatedUser
from ....domain.models.response import ResponsesCreatePayload
from ..decorators.decorators import endpoint_handler
from ..security.auth import auth_jwt_or_api_key
from ..utils.override_stream_response import OverrideStreamResponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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

@router.post("/responses")
@endpoint_handler("create_response")
async def create_response_endpoint(
    request: Request,
    payload: ResponsesCreatePayload,
    service: ChatCompletionService = Depends(get_chat_completion_service),
    user: AuthenticatedUser = Depends(auth_jwt_or_api_key)
) -> Any:
    # Stream pathway - token tracking is handled in the service
    if payload.stream:
        async def event_gen() -> AsyncGenerator[str, None]:
            try:
                # Stream processing is now handled directly by the service
                async for evt in service.create_response_stream(payload, user):
                    try:
                        evt_dict = evt.model_dump()  # type: ignore[attr-defined]
                    except Exception:
                        evt_dict = dict(evt)  # type: ignore[arg-type]
                    yield f"data: {json.dumps(evt_dict)}\r\n\r\n"
                yield "data: [DONE]\r\n\r\n"
            except Exception as e:  # noqa: BLE001
                err_payload = {"error": {"message": str(e), "type": "responses_stream_error"}}
                yield f"data: {json.dumps(err_payload)}\r\n\r\n"
                yield "data: [DONE]\r\n\r\n"
        return OverrideStreamResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8"
            }
        )
    # Non streaming pathway - token tracking is handled in the service
    else:
        return await service.create_response(payload, user)
