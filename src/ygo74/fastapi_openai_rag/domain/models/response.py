# filepath: c:\devel\fastapi-openai-rag\src\ygo74\fastapi_openai_rag\domain\models\response.py
"""Request payload model for the OpenAI Responses API (POST /v1/responses).

This module intentionally ONLY defines the input payload structure expected by our
endpoint proxy. Parsing / output handling is delegated directly to the official
openai SDK types (Response, ResponseStreamEvent, etc.).

We reuse the OpenAI SDK type hints so downstream code can transparently pass
this model's dict() to `client.responses.create(**payload)`.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Literal, TypeAlias
from pydantic import BaseModel, Field, model_validator, field_validator

# OpenAI SDK types (thin wrappers generated from spec)
from openai.types.responses.response_input_param import ResponseInputParam
from openai.types.responses.response_prompt_param import ResponsePromptParam
from openai.types.responses.response_text_config_param import ResponseTextConfigParam
from openai.types.responses import response_create_params
from openai.types.responses.response_includable import ResponseIncludable
from openai.types.shared_params.reasoning import Reasoning
from openai.types.shared_params.metadata import Metadata

ServiceTier = Literal["auto", "default", "flex", "scale", "priority"]
TruncationStrategy = Literal["auto", "disabled"]

# Re-export selected OpenAI param types for convenience elsewhere
ResponseToolChoice = response_create_params.ToolChoice
# Simplified safe aliases (treat as Any for static type checking in this project)
ConversationParamType: TypeAlias = Any
StreamOptionsType: TypeAlias = Any

class ResponsesCreatePayload(BaseModel):
    """Payload for POST /v1/responses (mirrors openai.responses.create parameters).

    Only fields actually forwarded to the OpenAI SDK are included. Any extra
    proxy-specific metadata should live outside this model.
    """
    # Required (in practice) -------------------------------------------------
    model: str = Field(..., description="Model name (e.g. gpt-4o, o3-mini, etc.)")

    # Core inputs ------------------------------------------------------------
    # OpenAI spec: input is a list[ResponseInputItemParam]; keep lenient normalization but strict runtime typing.
    input: Optional[Union[str, List[Dict[str, Any]]]] = Field(
        None,
        description=(
            "List of input items (messages, tool calls, images, text, etc.). "
            "If a message object (role+content) lacks 'type', it will be auto-set to 'message'."
        ),
    )
    instructions: Optional[str] = Field(
        None, description="System/developer style instructions overriding context."
    )
    conversation: Optional[Any] = None  # ConversationParamType (treated as Any)
    previous_response_id: Optional[str] = Field(
        None, description="Link a previous response for multi-turn continuity."
    )
    prompt: Optional[ResponsePromptParam] = None
    prompt_cache_key: Optional[str] = None

    # Generation controls ----------------------------------------------------
    max_output_tokens: Optional[int] = Field(
        None, ge=1, description="Upper bound for visible + reasoning tokens."
    )
    max_tool_calls: Optional[int] = Field(None, ge=1)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    top_p: Optional[float] = Field(None, ge=0, le=1)
    top_logprobs: Optional[int] = Field(None, ge=0, le=20)
    truncation: Optional[TruncationStrategy] = None

    # Tools / functions ------------------------------------------------------
    # Accept any tool dict: the proxy forwards tools transparently to the upstream API.
    # Some clients (e.g. Codex CLI) send non-standard tool types like "namespace"
    # that are not part of the OpenAI SDK ToolParam union.
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[ResponseToolChoice] = None
    parallel_tool_calls: Optional[bool] = True

    # Reasoning / advanced ---------------------------------------------------
    reasoning: Optional[Reasoning] = None
    service_tier: Optional[ServiceTier] = None
    stream: Optional[bool] = Field(False, description="If True, enable SSE streaming.")
    stream_options: Optional[Any] = None  # StreamOptionsType (treated as Any)
    text: Optional[ResponseTextConfigParam] = Field(
        None, description="Text / JSON schema output configuration."
    )

    # Metadata / identifiers -------------------------------------------------
    metadata: Optional[Metadata] = None
    safety_identifier: Optional[str] = None
    store: Optional[bool] = True
    user: Optional[str] = Field(
        None, description="Deprecated by OpenAI; kept for backward compatibility."
    )
    background: Optional[bool] = Field(
        None, description="If True, create background response (can be cancelled)."
    )
    include: Optional[List[ResponseIncludable]] = Field(
        None, description="Extra fields to include in the response body."
    )

    # Internal proxy-only (NOT forwarded automatically) ---------------------
    extra_headers: Optional[Dict[str, str]] = Field(
        None, description="Optional HTTP headers (proxy layer chooses usage)."
    )
    extra_query: Optional[Dict[str, Any]] = None
    extra_body: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = Field(
        None, description="Optional per-request timeout override (seconds)."
    )

    @field_validator("input", mode="before")
    @classmethod
    def _normalize_input_before(cls, v):  # type: ignore[override]
        """Pre-normalize raw input list before strict type validation.

        Injects:
        - type='message' for message objects lacking it
        - detail='auto' for input_image objects missing detail
        This runs BEFORE Pydantic validates nested required fields, preventing 422.
        """
        if isinstance(v, list):
            new_list = []
            for item in v:
                if isinstance(item, dict) and 'role' in item and 'content' in item:
                    if 'type' not in item:
                        item = {**item, 'type': 'message'}
                    content_val = item.get('content')
                    if isinstance(content_val, list):
                        patched_content = []
                        for c in content_val:
                            if isinstance(c, dict) and c.get('type') == 'input_image' and 'detail' not in c:
                                c = {**c, 'detail': 'auto'}
                            patched_content.append(c)
                        item = {**item, 'content': patched_content}
                new_list.append(item)
            return new_list
        return v

    @field_validator("tools", mode="before")
    @classmethod
    def _normalize_tools_before(cls, v):  # type: ignore[override]
        """Ensure each function tool dict contains required 'strict' field and proper schema.

        Some clients omit 'strict' although spec marks it required (FunctionToolParam.strict).
        When strict=True, Azure requires additionalProperties=False in function parameters schema.
        We default to True and ensure schema compliance.
        """
        if isinstance(v, list):
            patched: List[Any] = []
            for tool in v:
                if isinstance(tool, dict) and tool.get('type') == 'function':
                    tool_copy = dict(tool)
                    # Ensure strict field is present
                    if 'strict' not in tool_copy:
                        tool_copy['strict'] = False
                    # If strict=True, ensure additionalProperties=False in parameters
                    if tool_copy.get('strict') and tool_copy.get('type', None) == 'function':
                        if 'parameters' in tool_copy:
                            params = tool_copy['parameters']
                            if isinstance(params, dict) and 'additionalProperties' not in params:
                                params_copy = dict(params)
                                params_copy['additionalProperties'] = False
                                tool_copy['parameters'] = params_copy
                    patched.append(tool_copy)
                else:
                    patched.append(tool)
            return patched
        return v

    @model_validator(mode="after")
    def _validate_minimum(self) -> "ResponsesCreatePayload":
        """Ensure minimal required semantics.

        OpenAI requires `model` plus either `input` or a conversation linkage
        (conversation / previous_response_id). We enforce a soft check.
        """
        if not self.input and not self.previous_response_id and not self.conversation:
            raise ValueError("Either 'input', 'previous_response_id' or 'conversation' must be provided.")
        return self

    def _normalized_input(self) -> Optional[ResponseInputParam]:
        # After pre-normalization, input already compliant; just return
        return self.input

    def to_openai_kwargs(self) -> Dict[str, Any]:
        """Return dict filtered to parameters accepted by openai.responses.create.

        Excludes proxy-only fields (extra_headers, extra_query, extra_body, timeout).
        """
        allowed = {
            "background": self.background,
            "conversation": self.conversation,
            "include": self.include,
            "input": self._normalized_input(),
            "instructions": self.instructions,
            "max_output_tokens": self.max_output_tokens,
            "max_tool_calls": self.max_tool_calls,
            "metadata": self.metadata,
            "model": self.model,
            "parallel_tool_calls": self.parallel_tool_calls,
            "previous_response_id": self.previous_response_id,
            "prompt": self.prompt,
            "prompt_cache_key": self.prompt_cache_key,
            "reasoning": self.reasoning,
            "safety_identifier": self.safety_identifier,
            "service_tier": self.service_tier,
            "store": self.store,
            "stream": self.stream,
            "stream_options": self.stream_options,
            "temperature": self.temperature,
            "text": self.text,
            "tool_choice": self.tool_choice,
            "tools": self.tools,
            "top_logprobs": self.top_logprobs,
            "top_p": self.top_p,
            "truncation": self.truncation,
            "user": self.user,
        }
        return {k: v for k, v in allowed.items() if v is not None}

__all__ = [
    "ResponsesCreatePayload",
    "ResponseToolChoice",
    "StreamOptionsType",
    "ConversationParamType",
]
