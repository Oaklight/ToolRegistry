# ADR-003: Result Ordering Guarantee in `execute_tool_calls()`

**Date:** 2026-05-19
**Status:** Accepted

## Context

Gemini requires that tool-result messages are returned **in the same order** as the original
tool-call requests. It also does not provide stable call IDs (rosetta auto-generates them and
discards them on the response side). Other providers (OpenAI, Anthropic) correlate results by
call ID and are order-insensitive.

## Decision

`execute_tool_calls()` guarantees result ordering for **enabled** tools by design:

```python
# Results are collected by iterating `handles` in original call order,
# NOT via as_completed() or any completion-order mechanism.
for tc, handle in handles:          # handles built in enabled_calls order
    result = self._collect_handle_result(handle, tc.name)
    tool_responses[tc.id] = result  # dict preserves insertion order (Py 3.7+)
```

`build_tool_response()` preserves the insertion order of the `tool_responses` dict it receives,
so the end-to-end ordering is maintained.

## Scope and Limitations

**Disabled tools** are pre-populated into `tool_responses` by `_classify_tool_calls()` before
enabled tools are processed, which would break ordering if disabled and enabled tool calls were
interleaved in the original list.

This is accepted as a non-issue because:
- `get_schemas()` only exposes enabled tools to the LLM.
- The LLM can only call tools it has schemas for.
- Therefore a disabled tool will never appear in an LLM-generated tool-call list.

The only scenario that could trigger the broken case is manually calling `disable()` on a tool
between `get_schemas()` and `execute_tool_calls()` (a race condition in server mode). This is
considered an edge case and does not warrant the added complexity of a reorder step.
