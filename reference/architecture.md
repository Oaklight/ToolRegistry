# toolregistry Architecture

## Three-Layer Design

```
┌─────────────────────────────────────────────────────┐
│              Transport Layer                        │
│         (toolregistry-server package)               │
│   RouteTable · OpenAPI adapter · MCP adapter        │
└─────────────────────────┬───────────────────────────┘
                          │ imports
┌─────────────────────────▼───────────────────────────┐
│           LLM Orchestration Layer                   │
│              src/toolregistry/llm/                  │
│  tool_calls · content_blocks · discovery ·          │
│  truncation · _rosetta                              │
└─────────────────────────┬───────────────────────────┘
                          │ imports
┌─────────────────────────▼───────────────────────────┐
│            Registry Primitives Layer                │
│           src/toolregistry/ (core)                  │
│  ToolRegistry · Tool · events · executor ·          │
│  _mixins · admin · config                           │
└─────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**Registry Primitives** — the heart of the library. Knows nothing about LLM providers.
Responsible for: tool registration, enable/disable, execution, permissions, event callbacks,
concurrent execution (thread/process), result truncation bookkeeping.

**LLM Orchestration (`llm/`)** — bridges registry output to LLM API wire formats.
Responsible for: normalizing provider tool-call formats to/from internal `ToolCall`,
building assistant messages and tool-result messages, multimodal content block handling,
semantic tool discovery, result truncation policy.

**Transport Layer (separate package)** — serves the registry over a network.
Responsible for: HTTP routing, OpenAPI spec generation, MCP protocol, SSE streaming.
Lives in `toolregistry-server` so the core library has no server dependencies.

---

## Source Tree

```
src/toolregistry/
├── __init__.py               # public API surface
├── tool.py                   # Tool dataclass + schema generation
├── tool_registry.py          # ToolRegistry (assembles all mixins)
├── events.py                 # ChangeEvent / ChangeCallback / PostRegisterHook
├── executor.py               # concurrent execution backend
├── config.py                 # ToolConfig / ProfileConfig / source types
│
├── _mixins/                  # ToolRegistry behaviour, composed at class level
│   ├── callbacks.py          # on_change subscription + PostRegisterHook
│   ├── enable_disable.py     # disable / enable / update_tool_metadata
│   ├── permissions.py        # per-call permission gates
│   ├── registration.py       # register / unregister / merge
│   └── ...
│
├── admin/                    # observability: logging, audit trail
│
├── llm/                      # LLM orchestration (see llm.md)
│   ├── __init__.py
│   ├── tool_calls.py         # ToolCall, build_assistant_message, build_tool_response
│   ├── content_blocks.py     # multimodal ContentBlock helpers
│   ├── discovery.py          # semantic ToolDiscoveryTool
│   ├── truncation.py         # result size enforcement
│   └── _rosetta.py           # schema conversion via llm-rosetta
│
└── _vendor/                  # vendored dependencies (sparse_search, …)
```
