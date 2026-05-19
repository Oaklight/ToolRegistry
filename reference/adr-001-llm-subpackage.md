# ADR-001: Consolidate LLM Orchestration into `llm/` Subpackage

**Date:** 2026-05-19
**Status:** Accepted

## Context

Before this change, LLM-related code was scattered across the top-level package:

- `tool_discovery.py` — semantic search tool
- `truncation.py` — result size enforcement
- `_rosetta.py` — schema conversion helpers
- `types/` — provider-specific type definitions (OpenAI Pydantic models, Anthropic shims, Gemini shims)
- `types/content_blocks.py` — multimodal content block types

Additionally, the top-level package contained re-export shims for integrations that had moved to
separate packages (`mcp/`, `openapi/`, `langchain/`, `native/`, `hub/`).

The result was that `toolregistry` core appeared to know about MCP, LangChain, and OpenAPI, even
though those had been extracted into `toolregistry-server`. This blurred the layer boundaries.

## Decision

1. Create `src/toolregistry/llm/` subpackage.
2. Move all LLM-orchestration code into it: `_rosetta`, `content_blocks`, `discovery`,
   `tool_calls` (formerly `types/common.py`), `truncation`.
3. Delete the entire `types/` directory. Provider-specific type knowledge now lives exclusively
   in `llm-rosetta`; toolregistry core is provider-agnostic.
4. Delete deprecated re-export shims (`mcp/`, `openapi/`, `langchain/`, `native/`, `hub/`).
   These are breaking removals, scheduled for 0.11.0.

## Consequences

- Clear boundary: anything that requires knowing about OpenAI/Anthropic/Gemini wire formats
  lives under `llm/`.
- Registry primitives (`tool.py`, `tool_registry.py`, `_mixins/`, `events.py`) remain
  provider-agnostic.
- Callers who imported from `toolregistry.types.*` or the deprecated shim paths must update.
- `llm/` is still part of the core package (not a separate install), so no new optional
  dependency is needed for basic LLM usage.
