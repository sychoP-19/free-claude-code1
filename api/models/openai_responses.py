"""Pydantic models for the OpenAI Responses API (``/v1/responses``).

Used by Codex CLI v0.134+ which targets the Responses endpoint rather than
the legacy Chat Completions endpoint.  All models use
``ConfigDict(extra="allow")`` so provider-specific fields pass through
without breaking validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Shared base
# =============================================================================
class _ResponsesBase(BaseModel):
    """Forward-compatible base -- unknown fields are kept on the model."""

    model_config = ConfigDict(extra="allow")


# =============================================================================
# Request -- input items
# =============================================================================
class ResponsesInputMessage(_ResponsesBase):
    """Role-based input message (system / user / assistant)."""

    role: Literal["system", "user", "assistant"]
    content: str | list[Any]


class ResponsesFunctionCall(_ResponsesBase):
    """A tool call produced by the assistant, replayed as input."""

    type: Literal["function_call"] = "function_call"
    id: str
    call_id: str
    name: str
    arguments: str


class ResponsesFunctionCallOutput(_ResponsesBase):
    """Tool result fed back as input."""

    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: str


# Union of all legal input items
ResponsesInputItem = Union[
    ResponsesInputMessage,
    ResponsesFunctionCall,
    ResponsesFunctionCallOutput,
]


# =============================================================================
# Request -- tool definitions
# =============================================================================
class ResponsesFunctionTool(_ResponsesBase):
    """A function-type tool definition in the request."""

    type: Literal["function"] = "function"
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


# =============================================================================
# Request -- top-level
# =============================================================================
class ResponsesRequest(_ResponsesBase):
    """``POST /v1/responses`` request body."""

    model: str
    input: str | list[ResponsesInputItem] = []
    tools: list[ResponsesFunctionTool | dict[str, Any]] | None = None
    stream: bool = False
    temperature: float | None = None
    max_output_tokens: int | None = None
    instructions: str | None = None
    previous_response_id: str | None = None
    metadata: dict[str, Any] | None = None


# =============================================================================
# Response -- output items
# =============================================================================
class OutputTextContent(_ResponsesBase):
    """A text part inside a response message output item."""

    type: Literal["output_text"] = "output_text"
    text: str


class ResponsesMessageOutput(_ResponsesBase):
    """An assistant message in the ``output`` array."""

    type: Literal["message"] = "message"
    id: str
    role: Literal["assistant"] = "assistant"
    content: list[OutputTextContent | dict[str, Any]]


class ResponsesOutputFunctionCall(_ResponsesBase):
    """A function-call item in the ``output`` array."""

    type: Literal["function_call"] = "function_call"
    id: str
    call_id: str
    name: str
    arguments: str


ResponsesOutputItem = Union[
    ResponsesMessageOutput,
    ResponsesOutputFunctionCall,
]


# =============================================================================
# Response -- usage
# =============================================================================
class ResponsesUsage(_ResponsesBase):
    """Token usage returned in the response."""

    input_tokens: int = 0
    output_tokens: int = 0


# =============================================================================
# Response -- top-level
# =============================================================================
class ResponsesResponse(_ResponsesBase):
    """Non-streaming ``/v1/responses`` response body."""

    id: str
    object: Literal["response"] = "response"
    model: str
    status: Literal["completed", "in_progress", "incomplete", "failed", "cancelled"] = "completed"
    output: list[ResponsesOutputItem] = Field(default_factory=list)
    usage: ResponsesUsage = Field(default_factory=ResponsesUsage)
    created_at: int = 0
    metadata: dict[str, Any] | None = None


# =============================================================================
# SSE event dataclasses
# =============================================================================
@dataclass(slots=True, frozen=True)
class ResponseCreatedEvent:
    """``response.created``"""

    response: ResponsesResponse


@dataclass(slots=True, frozen=True)
class ResponseInProgressEvent:
    """``response.in_progress``"""

    response: ResponsesResponse


@dataclass(slots=True, frozen=True)
class ResponseOutputItemAddedEvent:
    """``response.output_item.added``"""

    output_index: int
    item: ResponsesOutputItem


@dataclass(slots=True, frozen=True)
class ResponseContentPartAddedEvent:
    """``response.content_part.added``"""

    output_index: int
    content_index: int
    part: OutputTextContent


@dataclass(slots=True, frozen=True)
class ResponseOutputTextDeltaEvent:
    """``response.output_text.delta``"""

    output_index: int
    content_index: int
    delta: str


@dataclass(slots=True, frozen=True)
class ResponseOutputTextDoneEvent:
    """``response.output_text.done``"""

    output_index: int
    content_index: int
    text: str


@dataclass(slots=True, frozen=True)
class ResponseContentPartDoneEvent:
    """``response.content_part.done``"""

    output_index: int
    content_index: int
    part: OutputTextContent


@dataclass(slots=True, frozen=True)
class ResponseOutputItemDoneEvent:
    """``response.output_item.done``"""

    output_index: int
    item: ResponsesOutputItem


@dataclass(slots=True, frozen=True)
class ResponseFunctionCallArgumentsDeltaEvent:
    """``response.function_call_arguments.delta``"""

    output_index: int
    delta: str


@dataclass(slots=True, frozen=True)
class ResponseFunctionCallArgumentsDoneEvent:
    """``response.function_call_arguments.done``"""

    output_index: int
    arguments: str


@dataclass(slots=True, frozen=True)
class ResponseCompletedEvent:
    """``response.completed``"""

    response: ResponsesResponse
