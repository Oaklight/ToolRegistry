# Migration Guide

This guide covers breaking changes and migration steps between major ToolRegistry releases.

## 0.7.x → 0.8.0

### Integration Packages Moved Under `integrations/`

All integration sub-packages (`mcp`, `openapi`, `langchain`, `native`) have been moved under a new `integrations/` parent package. This provides a clearer project structure as the number of integrations grows.

**Before (0.7.x):**

```python
from toolregistry.mcp import MCPClient
from toolregistry.openapi import OpenAPIIntegration
from toolregistry.langchain import LangChainIntegration
from toolregistry.native import NativeIntegration
```

**After (0.8.0):**

```python
from toolregistry.integrations.mcp import MCPClient
from toolregistry.integrations.openapi import OpenAPIIntegration
from toolregistry.integrations.langchain import LangChainIntegration
from toolregistry.integrations.native import NativeIntegration
```

**Import path mapping:**

| Old path (deprecated) | New canonical path |
|---|---|
| `toolregistry.mcp` | `toolregistry.integrations.mcp` |
| `toolregistry.openapi` | `toolregistry.integrations.openapi` |
| `toolregistry.langchain` | `toolregistry.integrations.langchain` |
| `toolregistry.native` | `toolregistry.integrations.native` |

**Backward compatibility:** The old import paths still work but emit a `DeprecationWarning`. They will be removed in a future release. Update your imports at your earliest convenience.

```python
# This still works in 0.8.0 but prints a DeprecationWarning:
from toolregistry.mcp import MCPClient
# DeprecationWarning: Importing from 'toolregistry.mcp' is deprecated.
# Use 'toolregistry.integrations.mcp' instead.
```

**Public API unchanged:** The `ToolRegistry` convenience methods — `register_from_mcp()`, `register_from_openapi()`, `register_from_langchain()`, and `register_from_native()` — continue to work exactly as before with no code changes required.

---

## 0.6.x → 0.7.0

### Executor Backend Architecture

The monolithic `Executor` class has been replaced by a pluggable backend system.

**Before (0.6.x):**

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
# parallel_mode parameter controlled execution
results = registry.execute_tool_calls(tool_calls, parallel_mode="thread")
```

**After (0.7.0):**

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
# Use execution_mode parameter or set_default_execution_mode()
registry.set_default_execution_mode("thread")  # "thread" or "process"
results = registry.execute_tool_calls(tool_calls)

# Or per-call override
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
```

**What changed:**

| 0.6.x | 0.7.0 | Notes |
|-------|-------|-------|
| `parallel_mode` parameter | `execution_mode` parameter | Renamed |
| `Executor` class | `ThreadBackend` / `ProcessPoolBackend` | Pluggable backends |
| No cancellation support | `ExecutionContext` with `check_cancelled()` | Cooperative cancellation |
| No timeout per tool | `ToolMetadata(timeout=5.0)` | Per-tool timeout enforcement |

### New Dependency: llm-rosetta

`llm-rosetta>=0.2.6` is now a core dependency, powering multi-format schema generation. No action needed — it installs automatically.

### New Permission System

The permission system is additive and opt-in. Existing code continues to work without changes. To adopt:

```python
from toolregistry import ToolRegistry, ToolMetadata, ToolTag
from toolregistry.permissions import PermissionPolicy, ALLOW_READONLY, ASK_DESTRUCTIVE

# Classify tools with metadata
registry.register(tool, metadata=ToolMetadata(tags=[ToolTag.READ_ONLY]))

# Set permission policy
policy = PermissionPolicy(rules=[ALLOW_READONLY, ASK_DESTRUCTIVE])
registry.set_permission_policy(policy)
```

### Multi-Format Schema Support

`get_schemas()` now accepts `api_format` values `"anthropic"` and `"gemini"` in addition to the existing OpenAI formats.

```python
# New formats
schemas = registry.get_schemas(api_format="anthropic")
schemas = registry.get_schemas(api_format="gemini")

# Existing formats still work
schemas = registry.get_schemas()  # default: OpenAI chat completion
schemas = registry.get_schemas(api_format="openai-response")
```

---

## 0.5.x → 0.6.0

### Python 3.10+ Required

ToolRegistry 0.6.0 drops support for Python 3.8 and 3.9. Update your Python version to 3.10 or later.

```bash
# Check your Python version
python --version

# If using conda
conda install python=3.11
```

### dill → cloudpickle

The serialization dependency changed from `dill` to `cloudpickle`. This is transparent — no code changes needed, but if you pinned `dill` in your dependencies, you can remove it.

```diff
# pyproject.toml — if you pinned dill
 dependencies = [
     "toolregistry>=0.6.0",
-    "dill>=0.4.0",
 ]
```

### Type Annotation Modernization

If you subclass ToolRegistry internals, note that type annotations now use Python 3.10+ syntax:

```python
# 0.5.x style (still works in 3.10+)
from typing import Optional, List, Dict
def func(x: Optional[str] = None) -> List[Dict[str, int]]: ...

# 0.6.x style
def func(x: str | None = None) -> list[dict[str, int]]: ...
```

---

## 0.4.x → 0.5.0

### `register_from_class()` MRO Default Changed

`traverse_mro` now defaults to `True`, meaning inherited methods from parent classes are automatically registered.

**Before (0.4.x):** Only methods defined directly on the class were registered.

**After (0.5.0):** Methods from parent classes (excluding `object`) are also registered.

To restore the old behavior:

```python
registry.register_from_class(MyClass, traverse_mro=False)
```

### Hub Package Split

The `toolregistry[hub]` optional extra has been removed. Install hub tools as a separate package:

```diff
- pip install toolregistry[hub]
+ pip install toolregistry toolregistry-hub
```

The import path `from toolregistry.hub import ...` still works when both packages are installed.

### MCP SDK Change

The MCP dependency changed from `fastmcp` to the official `mcp` SDK:

```diff
- pip install toolregistry[mcp]  # installed fastmcp
+ pip install toolregistry[mcp]  # now installs mcp>=1.0.0
```

No code changes needed — the `register_from_mcp()` API is unchanged. Transport configuration now supports all four transport types: stdio, SSE, streamable-http, and websocket.
