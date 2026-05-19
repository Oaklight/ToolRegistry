"""Unified tool call types and format conversion via llm-rosetta.

Provides :class:`ToolCall` and :class:`ToolCallResult` as toolregistry's
internal representations, plus thin wrappers around llm-rosetta for
converting between provider-specific API formats.
"""

import json
import warnings
from typing import Any, Literal

from pydantic import BaseModel, field_serializer

# ── Format registry ────────────────────────────────────────────────

API_FORMATS = Literal[
    "openai",  # deprecated alias for openai-chat
    "openai-chat",
    "openai-chatcompletion",  # deprecated alias for openai-chat
    "openai-response",
    "anthropic",
    "gemini",
]

_DEPRECATED_API_FORMATS: dict[str, API_FORMATS] = {
    "openai": "openai-chat",
    "openai-chatcompletion": "openai-chat",
}


def _normalize_api_format(api_format: API_FORMATS) -> API_FORMATS:
    """Map deprecated format names to their canonical equivalents.

    Emits a ``DeprecationWarning`` when a deprecated name is used.
    """
    canonical = _DEPRECATED_API_FORMATS.get(api_format)
    if canonical is not None:
        warnings.warn(
            f'api_format="{api_format}" is deprecated, use "{canonical}" instead.',
            DeprecationWarning,
            stacklevel=3,
        )
        return canonical
    return api_format


# ── Rosetta tool ops accessors ─────────────────────────────────────

def _get_tool_ops(api_format: API_FORMATS) -> Any:
    """Return the rosetta ToolOps class for the given format.

    Args:
        api_format: Canonical API format string.

    Returns:
        The corresponding ToolOps class.

    Raises:
        ValueError: If the format is unsupported.
    """
    if api_format == "openai-chat":
        from llm_rosetta.converters.openai_chat import OpenAIChatToolOps
        return OpenAIChatToolOps
    elif api_format == "openai-response":
        from llm_rosetta.converters.openai_responses import OpenAIResponsesToolOps
        return OpenAIResponsesToolOps
    elif api_format == "anthropic":
        from llm_rosetta.converters.anthropic import AnthropicToolOps
        return AnthropicToolOps
    elif api_format == "gemini":
        from llm_rosetta.converters.google_genai import GoogleGenAIToolOps
        return GoogleGenAIToolOps
    raise ValueError(f"Unsupported API format: {api_format}")


# ── Internal types ─────────────────────────────────────────────────


class ToolCall(BaseModel):
    """Toolregistry's normalized tool call representation.

    All provider formats are converted to/from this type via the
    rosetta shim layer below.
    """

    id: str
    """The ID of the tool call."""
    name: str
    """The name of the function to call."""
    arguments: str
    """The arguments in JSON string format."""
    type: Literal["function", "custom"] = "function"
    """The type of the tool call."""

    @classmethod
    def from_tool_call(cls, tool_call: Any) -> "ToolCall":
        """Convert any provider tool call format to ToolCall.

        Delegates format detection and parsing to llm-rosetta, then
        converts through the IR shim.

        Args:
            tool_call: Tool call in any supported provider format
                (dict, Pydantic model, or raw object).

        Returns:
            Normalized ToolCall.

        Raises:
            TypeError: If the format is not recognized by any provider.
        """
        tc_dict = _to_dict(tool_call)

        # Try each provider's parser via rosetta.
        # Vendor-specific formats (anthropic, gemini) are tried before generic
        # OpenAI formats because the OpenAI parsers are lenient and may
        # successfully (but incorrectly) parse Anthropic/Gemini dicts.
        for fmt in ("anthropic", "gemini", "openai-chat", "openai-response"):
            try:
                ops = _get_tool_ops(fmt)
                ir = ops.p_tool_call_to_ir(tc_dict)
                # Sanity check: both tool_name and tool_call_id must be non-empty
                if not ir.get("tool_name") or not ir.get("tool_call_id"):
                    continue
                return _ir_to_toolcall(ir)
            except (KeyError, TypeError, ValueError, AttributeError):
                continue

        raise TypeError(
            f"Unsupported tool call format: {type(tool_call)}. "
            f"Expected OpenAI, Anthropic, or Gemini tool call format."
        )


class ToolCallResult(BaseModel):
    """Result of a single tool call execution."""

    id: str
    """The ID of the tool call."""
    result: Any
    """The result of the tool call."""

    @field_serializer("result")
    def convert_any_field_to_str(self, value: Any) -> str:
        """Convert result to string during serialization."""
        return str(value)


# ── Shim: ToolCall ↔ rosetta IR ────────────────────────────────────


def _toolcall_to_ir(tc: ToolCall) -> dict[str, Any]:
    """Convert a ToolCall to a rosetta IR ToolCallPart dict.

    Currently a near-identity transform since the structures are
    intentionally similar.
    """
    return {
        "type": "tool_call",
        "tool_call_id": tc.id,
        "tool_name": tc.name,
        "tool_input": json.loads(tc.arguments),
        "tool_type": tc.type,
    }


def _ir_to_toolcall(ir: dict[str, Any]) -> ToolCall:
    """Convert a rosetta IR ToolCallPart dict to a ToolCall.

    Currently a near-identity transform since the structures are
    intentionally similar.  tool_type values outside the ToolCall
    Literal ("function" | "custom") are normalized to "function".
    """
    tool_input = ir.get("tool_input", {})
    raw_type = ir.get("tool_type", "function")
    tc_type = raw_type if raw_type in ("function", "custom") else "function"
    return ToolCall(
        id=ir["tool_call_id"],
        name=ir["tool_name"],
        arguments=json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
        type=tc_type,
    )


def _to_dict(obj: Any) -> Any:
    """Convert a Pydantic model or similar object to a dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


# ── Public API ─────────────────────────────────────────────────────


def convert_tool_calls(tool_calls: list[Any]) -> list[ToolCall]:
    """Convert a list of provider tool calls to ToolCall objects.

    Args:
        tool_calls: Tool call objects in any supported format.

    Returns:
        Normalized ToolCall list.
    """
    return [ToolCall.from_tool_call(tc) for tc in tool_calls]


def build_assistant_message(
    tool_calls: list[ToolCall],
    *,
    api_format: API_FORMATS = "openai-chat",
) -> list[dict[str, Any]]:
    """Build assistant message containing tool calls in the target format.

    Args:
        tool_calls: Normalized ToolCall list.
        api_format: Target API format.

    Returns:
        Assistant message(s) as list of dicts.

    Raises:
        ValueError: If the API format is unsupported.
    """
    api_format = _normalize_api_format(api_format)
    ops = _get_tool_ops(api_format)

    ir_calls = [_toolcall_to_ir(tc) for tc in tool_calls if tc.name and tc.arguments]
    provider_calls = [ops.ir_tool_call_to_p(ir) for ir in ir_calls]

    if api_format == "openai-chat":
        return [{"role": "assistant", "tool_calls": provider_calls}]
    elif api_format == "openai-response":
        return provider_calls
    elif api_format == "anthropic":
        return [{"role": "assistant", "content": provider_calls}]
    elif api_format == "gemini":
        return [{"role": "model", "parts": provider_calls}]
    raise ValueError(f"Unsupported API format: {api_format}")


def build_tool_response(
    tool_responses: dict[str, str | list],
    *,
    api_format: API_FORMATS = "openai-chat",
    tool_calls: list[ToolCall] | None = None,
) -> list[dict[str, Any]]:
    """Build tool result messages in the target format.

    Args:
        tool_responses: Mapping of tool call IDs to results.
        api_format: Target API format.
        tool_calls: Optional ToolCall list for Gemini name resolution.

    Returns:
        Tool result messages in the specified format.

    Raises:
        ValueError: If the API format is unsupported.
    """
    from .content_blocks import content_blocks_to_text, is_content_block_list

    def _to_text(result: str | list) -> str:
        if isinstance(result, list) and is_content_block_list(result):
            return content_blocks_to_text(result)
        return str(result)

    api_format = _normalize_api_format(api_format)
    ops = _get_tool_ops(api_format)

    # Build name map for Gemini (needs function name instead of call ID)
    name_map: dict[str, str] = {}
    if tool_calls:
        name_map = {tc.id: tc.name for tc in tool_calls}

    ir_results = []
    for call_id, result in tool_responses.items():
        ir = {
            "type": "tool_result",
            # Gemini requires function name instead of call ID;
            # rosetta's ir_tool_result_to_p uses tool_call_id as the name field
            "tool_call_id": name_map.get(call_id, call_id) if api_format == "gemini" else call_id,
            "result": _to_text(result),
        }
        ir_results.append(ir)

    provider_results = [ops.ir_tool_result_to_p(ir) for ir in ir_results]

    if api_format == "openai-chat":
        # Each tool result is a separate message
        return provider_results
    elif api_format == "openai-response":
        return provider_results
    elif api_format == "anthropic":
        return [{"role": "user", "content": provider_results}]
    elif api_format == "gemini":
        return [{"role": "user", "parts": provider_results}]
    raise ValueError(f"Unsupported API format: {api_format}")


# ── Deprecated aliases ─────────────────────────────────────────────


def recover_assistant_message(
    tool_calls: list[ToolCall],
    *,
    api_format: API_FORMATS = "openai-chat",
) -> list[dict[str, Any]]:
    """Deprecated: use :func:`build_assistant_message` instead."""
    warnings.warn(
        "recover_assistant_message() is deprecated, use build_assistant_message() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_assistant_message(tool_calls, api_format=api_format)


def recover_tool_message(
    tool_responses: dict[str, str | list],
    *,
    api_format: API_FORMATS = "openai-chat",
    tool_calls: list[ToolCall] | None = None,
) -> list[dict[str, Any]]:
    """Deprecated: use :func:`build_tool_response` instead."""
    warnings.warn(
        "recover_tool_message() is deprecated, use build_tool_response() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_tool_response(
        tool_responses, api_format=api_format, tool_calls=tool_calls
    )
