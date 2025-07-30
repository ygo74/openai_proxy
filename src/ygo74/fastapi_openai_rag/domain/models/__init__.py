"""Domain models initialization with forward reference resolution."""

from .llm import LLMProvider, TokenUsage, LLMRequestType, BaseLLMRequest, LLMRequest, LLMResponse
from .llm_model import LlmModel, AzureLlmModel, LlmModelStatus
from .group import Group

# Resolve all forward references after imports
try:
    LlmModel.model_rebuild()
    AzureLlmModel.model_rebuild()
    Group.model_rebuild()
except Exception:
    # Forward references will be resolved on first use
    pass

__all__ = [
    'LLMProvider', 'TokenUsage', 'LLMRequestType', 'BaseLLMRequest', 'LLMRequest', 'LLMResponse',
    'LlmModel', 'AzureLlmModel', 'LlmModelStatus',
    'Group'
]