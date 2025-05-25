from fastapi import APIRouter
from typing import Dict, Any
from src.core.models.llm_payload import ChatCompletionRequest
from src.api.v1 import router_v1


@router_v1.post("/chat/completions")
async def chat_completions(payload: ChatCompletionRequest) -> Dict[str, Any]:
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "This is a simulated response."},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }
