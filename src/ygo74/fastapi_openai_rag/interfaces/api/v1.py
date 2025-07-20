"""API version 1 routes."""
from fastapi import APIRouter

from .endpoints import models, groups, chat_completions

router = APIRouter()

# Include the groups router
router.include_router(groups.router, prefix="/groups", tags=["groups"])
# Include the chat completions router (OpenAI-compatible)
router.include_router(chat_completions.router, prefix="", tags=["openai-compatible"])