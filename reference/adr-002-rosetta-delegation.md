# ADR-002: Delegate All Format Conversion to llm-rosetta

**Date:** 2026-05-19
**Status:** Accepted

## Context

`toolregistry` originally maintained its own Pydantic models for each provider's tool-call
wire format (OpenAI `ChatCompletionMessageToolCall`, `ResponseFunctionToolCall`, Anthropic
`ToolUseBlock`, Gemini `FunctionCall`). This meant:

- Duplicated provider knowledge in core
- Schema validation duplicated what llm-rosetta already does
- Adding a new provider required changes in both `toolregistry` and `llm-rosetta`

`llm-rosetta` was introduced as a dedicated format-conversion library with an IR
(Intermediate Representation) at its centre.

## Decision

Fully delegate all provider ↔ IR conversion to `llm-rosetta`.
Maintain a thin **shim** between toolregistry's `ToolCall` and rosetta's IR:

```
Provider format  ←→  rosetta IR  ←→  ToolCall (toolregistry internal)
```

The shim (`_toolcall_to_ir` / `_ir_to_toolcall`) is intentionally a near-identity transform
because the structures are deliberately similar. Its purpose is stability isolation: if rosetta's
IR changes, only the shim needs updating, not every call-site.

### Parser ordering in `ToolCall.from_tool_call()`

When auto-detecting format, parsers are tried in this order:

```
anthropic → gemini → openai-chat → openai-response
```

Vendor-specific parsers come first because the OpenAI parsers are lenient and may silently
accept (and misparse) Anthropic or Gemini dicts. A sanity check is applied after each attempt:
if `tool_name` or `tool_call_id` is empty in the resulting IR, the parse is rejected.

### Gemini name resolution in `build_tool_response()`

Gemini's `functionResponse` uses the **function name** as the identifier, not a call ID.
Since `execute_tool_calls()` returns results keyed by call ID, `build_tool_response()` builds
a `name_map` (`call_id → function_name`) from the `tool_calls` argument and substitutes before
passing to rosetta.

## Consequences

- All OpenAI Pydantic model imports removed from toolregistry core.
- Test fixtures changed from Pydantic model instances to plain dicts.
- New providers are added solely in `llm-rosetta`; toolregistry core only needs a new
  `_get_tool_ops()` branch.
- `toolregistry` no longer has a direct `openai` package dependency for type validation.
