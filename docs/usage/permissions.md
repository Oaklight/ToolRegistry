# Permission System

ToolRegistry provides a built-in permission system that lets you control which tool calls are allowed, denied, or require explicit confirmation before execution. The system is designed around three concepts: **rules**, **policies**, and **handlers**.

## Overview

The permission system is evaluated during `execute_tool_calls()`. When a tool call arrives, the permission policy checks each rule in order (first match wins). Depending on the matched rule's result, the call is either:

- **Allowed** (`ALLOW`) -- the tool executes normally.
- **Denied** (`DENY`) -- the tool call is rejected with an error message.
- **Escalated** (`ASK`) -- a permission handler is consulted to make the final decision.

If no policy is configured, all tool calls are allowed by default.

## Quick Start

```python
from toolregistry import (
    ToolRegistry,
    PermissionPolicy,
    PermissionRule,
    PermissionResult,
)

registry = ToolRegistry()

# Register some tools
@registry.register
def read_file(path: str) -> str:
    """Read a file from disk."""
    return open(path).read()

@registry.register
def delete_file(path: str) -> str:
    """Delete a file from disk."""
    import os
    os.remove(path)
    return f"Deleted {path}"

# Define a permission policy
policy = PermissionPolicy(
    rules=[
        PermissionRule(
            name="allow_read",
            match=lambda tool, params: tool.name == "read_file",
            result=PermissionResult.ALLOW,
            reason="Reading files is safe",
        ),
        PermissionRule(
            name="block_delete",
            match=lambda tool, params: tool.name == "delete_file",
            result=PermissionResult.DENY,
            reason="File deletion is not allowed",
        ),
    ],
    fallback=PermissionResult.DENY,
)

registry.set_permission_policy(policy)
```

With this policy, `read_file` calls proceed normally, while `delete_file` calls are rejected.

## Core Concepts

### PermissionResult

A three-state enum representing the outcome of a permission check:

| Value | Description |
|-------|-------------|
| `ALLOW` | The tool call is permitted |
| `DENY` | The tool call is rejected |
| `ASK` | The decision is delegated to a handler |

### PermissionRule

A single rule that maps a match predicate to a result. Rules are evaluated in order; the first rule whose `match` returns `True` determines the outcome.

```python
from toolregistry import PermissionRule, PermissionResult

rule = PermissionRule(
    name="ask_for_network_tools",
    match=lambda tool, params: "http" in str(params),
    result=PermissionResult.ASK,
    reason="Tool call involves network access",
)
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Human-readable identifier for the rule |
| `match` | `Callable[[Tool, dict], bool]` | Predicate that receives `(tool, parameters)` |
| `result` | `PermissionResult` | The decision when the rule matches |
| `reason` | `str` | Explanation surfaced in `PermissionRequest` |

### PermissionPolicy

An ordered collection of rules with a fallback result.

```python
from toolregistry import PermissionPolicy, PermissionResult

policy = PermissionPolicy(
    rules=[rule_1, rule_2, rule_3],
    fallback=PermissionResult.DENY,  # safe by default
    handler=my_handler,  # optional policy-level handler
)
```

**Evaluation semantics:** Rules are checked in list order. The first rule whose `match` returns `True` produces the final decision. If no rule matches, the `fallback` result is used.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `rules` | `list[PermissionRule]` | Ordered list of rules |
| `fallback` | `PermissionResult` | Result when no rule matches (default: `DENY`) |
| `handler` | `PermissionHandler \| None` | Optional policy-level handler for `ASK` results |

## Using Tool Tags with Permissions

The permission system works well with `ToolTag` and `ToolMetadata`. You can tag tools and write rules that match on tags rather than tool names, making policies more maintainable.

### ToolTag

Predefined tags for common tool characteristics:

| Tag | Description |
|-----|-------------|
| `READ_ONLY` | Tool only reads data |
| `DESTRUCTIVE` | Tool modifies or deletes data |
| `NETWORK` | Tool requires network access |
| `FILE_SYSTEM` | Tool accesses the file system |
| `SLOW` | Tool may take a long time |
| `PRIVILEGED` | Tool requires elevated permissions |

### ToolMetadata Fields

Beyond tags, `ToolMetadata` provides execution hints:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tags` | `set[ToolTag]` | `set()` | Predefined classification tags |
| `custom_tags` | `set[str]` | `set()` | User-defined tags |
| `timeout` | `float \| None` | `None` | Per-call timeout in seconds |
| `is_concurrency_safe` | `bool` | `True` | Whether the tool can run concurrently |
| `locality` | `"local" \| "remote" \| "any"` | `"any"` | Where the tool executes (local machine, remote server, or either) |

### Tagging Tools

```python
from toolregistry import Tool, ToolMetadata, ToolTag

tool = Tool.from_function(
    my_function,
    metadata=ToolMetadata(
        tags={ToolTag.NETWORK, ToolTag.SLOW},
        custom_tags={"requires_api_key"},
        timeout=30.0,
        locality="remote",
    ),
)
registry.register(tool)
```

### Built-in Rules

ToolRegistry provides pre-built rules that match on `ToolTag` values:

```python
from toolregistry.permissions.builtin_rules import (
    ALLOW_READONLY,     # Allows tools tagged READ_ONLY
    ASK_DESTRUCTIVE,    # Asks for tools tagged DESTRUCTIVE
    DENY_PRIVILEGED,    # Denies tools tagged PRIVILEGED
    ASK_NETWORK,        # Asks for tools tagged NETWORK
    ASK_FILE_SYSTEM,    # Asks for tools tagged FILE_SYSTEM
)

policy = PermissionPolicy(
    rules=[
        ALLOW_READONLY,
        DENY_PRIVILEGED,
        ASK_DESTRUCTIVE,
        ASK_NETWORK,
        ASK_FILE_SYSTEM,
    ],
    fallback=PermissionResult.DENY,
)

registry.set_permission_policy(policy)
```

## Permission Handlers

When a rule returns `ASK`, the system delegates to a permission handler. Handlers implement a simple protocol:

### Synchronous Handler

```python
from toolregistry import PermissionHandler, PermissionRequest, PermissionResult

class CLIPermissionHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        print(f"Tool: {request.tool_name}")
        print(f"Reason: {request.reason}")
        print(f"Parameters: {request.parameters}")
        answer = input("Allow this call? [y/N] ")
        return PermissionResult.ALLOW if answer.lower() == "y" else PermissionResult.DENY
```

### Asynchronous Handler

```python
from toolregistry import AsyncPermissionHandler, PermissionRequest, PermissionResult

class WebSocketPermissionHandler:
    async def handle(self, request: PermissionRequest) -> PermissionResult:
        response = await ws.ask_user(request.tool_name, request.reason)
        return PermissionResult.ALLOW if response == "yes" else PermissionResult.DENY
```

### PermissionRequest

The context object passed to handlers when a rule returns `ASK`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `tool_name` | `str` | Name of the tool being invoked |
| `parameters` | `dict[str, Any]` | Arguments the caller intends to pass |
| `reason` | `str` | Explanation from the matched rule |
| `rule_name` | `str` | Name of the rule that triggered `ASK` |
| `metadata` | `ToolMetadata` | The tool's metadata for handler reference |

### Registering Handlers

Handlers can be registered at two levels:

1. **Registry level** -- applies to all policies:

    ```python
    registry.set_permission_handler(
        CLIPermissionHandler(),
        fallback=PermissionResult.DENY,
    )
    ```

2. **Policy level** -- takes precedence over registry-level handler:

    ```python
    policy = PermissionPolicy(
        rules=[...],
        handler=WebSocketPermissionHandler(),
    )
    ```

**Resolution order for `ASK` results:**

1. Policy-level handler
2. Registry-level handler
3. Fallback result (defaults to `DENY`)

## Managing Permissions at Runtime

```python
# Set a policy
registry.set_permission_policy(policy)

# Get the current policy
current_policy = registry.get_permission_policy()

# Remove the policy (all calls allowed)
registry.remove_permission_policy()

# Set a handler
registry.set_permission_handler(handler)

# Get the current handler
current_handler = registry.get_permission_handler()

# Remove the handler
registry.remove_permission_handler()
```

## Permission Events

The permission system emits change events that can be observed via the [callback mechanism](../api/events.md):

| Event Type | When |
|------------|------|
| `PERMISSION_DENIED` | A tool call was denied by the policy |
| `PERMISSION_ASKED` | A tool call was escalated to a handler |

```python
from toolregistry import ChangeEvent, ChangeEventType

def permission_monitor(event: ChangeEvent) -> None:
    if event.event_type == ChangeEventType.PERMISSION_DENIED:
        print(f"DENIED: {event.tool_name} - {event.reason}")
    elif event.event_type == ChangeEventType.PERMISSION_ASKED:
        print(f"ASKED: {event.tool_name} - {event.reason}")

registry.on_change(permission_monitor)
```

## Complete Example

```python
from toolregistry import (
    ToolRegistry,
    ToolMetadata,
    ToolTag,
    PermissionPolicy,
    PermissionResult,
    PermissionRequest,
)
from toolregistry.permissions.builtin_rules import (
    ALLOW_READONLY,
    ASK_DESTRUCTIVE,
    DENY_PRIVILEGED,
)

registry = ToolRegistry()

# Register tools with metadata
from toolregistry import Tool

def search_db(query: str) -> str:
    """Search the database."""
    return f"Results for: {query}"

def drop_table(name: str) -> str:
    """Drop a database table."""
    return f"Dropped {name}"

registry.register(
    Tool.from_function(
        search_db,
        metadata=ToolMetadata(tags={ToolTag.READ_ONLY}),
    )
)
registry.register(
    Tool.from_function(
        drop_table,
        metadata=ToolMetadata(tags={ToolTag.DESTRUCTIVE}),
    )
)

# Create a handler
class SimpleHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        print(f"[PERMISSION] {request.tool_name}: {request.reason}")
        return PermissionResult.DENY  # deny by default in this example

# Set up policy and handler
policy = PermissionPolicy(
    rules=[ALLOW_READONLY, ASK_DESTRUCTIVE],
    fallback=PermissionResult.DENY,
)
registry.set_permission_policy(policy)
registry.set_permission_handler(SimpleHandler())

# search_db will be allowed (READ_ONLY tag matches ALLOW_READONLY)
# drop_table will be escalated to handler (DESTRUCTIVE tag matches ASK_DESTRUCTIVE)
```

## See Also

- [Permissions API Reference](../api/permissions.md) -- `PermissionPolicy`, `PermissionRule`, `PermissionResult`, `PermissionHandler` class details
- [Execution Modes](concurrency_modes.md) -- timeout and concurrency-safety settings via `ToolMetadata`
