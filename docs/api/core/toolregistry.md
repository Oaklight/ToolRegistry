# ToolRegistry

The central registry class that manages tool registration, execution, and metadata across the ToolRegistry ecosystem.

## Overview

`ToolRegistry` serves as the core orchestrator for tool management in the ToolRegistry library. It provides a unified interface for registering, discovering, and executing tools from various sources including native Python functions, OpenAPI specifications, MCP servers, LangChain tools, and more.

## Key Features

- **Unified Tool Management**: Central registry for all types of tools
- **Async/Sync Support**: Full compatibility with both synchronous and asynchronous execution
- **Namespace Organization**: Support for organizing tools under namespaces
- **Multi-Source Integration**: Seamless integration with various tool sources
- **Metadata Preservation**: Maintains tool descriptions, parameters, and execution metadata
- **Flexible Execution**: Multiple execution modes and concurrency options
- **Change Callbacks**: Subscribe to tool state changes via `on_change()` / `remove_on_change()`
- **Post-Registration Hooks**: Run custom logic after each tool is registered via `add_post_register_hook()`, with optional auto-disable support
- **Tag-Based Bulk Disable**: Disable multiple tools at once by their `ToolTag` values via `disable_by_tags()`

## Architecture

The ToolRegistry follows a registry pattern with the following key responsibilities:

### Core Responsibilities

1. **Tool Registration**: Accept and register tools from various sources
2. **Tool Discovery**: Provide mechanisms to discover available tools
3. **Tool Execution**: Execute tools with proper parameter validation and error handling
4. **Metadata Management**: Maintain and provide access to tool metadata
5. **Namespace Support**: Organize tools under logical namespaces

### Registration Methods

- **Native Registration**: `register()` for direct function/instance registration
- **Class Integration**: `register_from_class()` for Python class method registration. By default, traverses the MRO (Method Resolution Order) to include inherited methods from parent classes. Pass `traverse_mro=False` to register only directly defined methods.
- **OpenAPI Integration**: Integration with OpenAPI specifications
- **MCP Integration**: Support for Model Context Protocol servers
- **LangChain Integration**: Compatibility with LangChain tools

### Execution Models

- **`invoke(tool_name, kwargs)`**: Single-tool execution with full pipeline (permissions, logging, invocation tracking). Used by PTC for IPC callbacks.
- **`execute_tool_calls(tool_calls)`**: Batch execution with concurrency via Thread/Process backends. Used for LLM tool_use responses.
- **`enable_code_execution()`**: Registers a `code_execution` tool for [Programmatic Tool Calling](../../usage/programmatic_tool_calling.md). LLMs can write Python code that orchestrates multiple tool calls.

### Invocation Tracking

All tool executions are logged with an `invocation_id` prefix:

- `tr_sig_` — single `invoke()` calls
- `tr_bat_` — batch `execute_tool_calls()` calls
- `tr_ptc_` — PTC code execution tool calls

Query with `log.get_entries(invocation_id="tr_ptc_...")`.

## API Reference

::: toolregistry.ToolRegistry
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
        separate_signature: true
        show_signature_annotations: true

## Usage Examples

### Basic Tool Registration

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Register a simple function
def add_numbers(a: int, b: int) -> int:
    return a + b

registry.register(add_numbers)
```

### Class Integration

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

class Calculator:
    @staticmethod
    def multiply(a: int, b: int) -> int:
        return a * b

    def divide(self, a: int, b: int) -> float:
        return a / b

# Register all methods from the class
registry.register_from_class(Calculator)
```

### Class Integration with MRO Traversal

```python
from toolregistry import ToolRegistry

class BaseCalculator:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b

class AdvancedCalculator(BaseCalculator):
    @staticmethod
    def multiply(a: int, b: int) -> int:
        return a * b

registry = ToolRegistry()

# Default behavior (traverse_mro=True): includes inherited methods from BaseCalculator
registry.register_from_class(AdvancedCalculator)
print(registry.get_available_tools())
# Output: ['advanced_calculator-add', 'advanced_calculator-multiply']

# With traverse_mro=False: only methods defined directly on AdvancedCalculator
registry2 = ToolRegistry()
registry2.register_from_class(AdvancedCalculator, traverse_mro=False)
print(registry2.get_available_tools())
# Output: ['advanced_calculator-multiply']
```

### Namespace Organization

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Register with custom namespace
registry.register(my_function, namespace="math_utils")

# Access tools with namespace
available_tools = registry.get_available_tools(namespace="math_utils")
```

### Change Callbacks

```python
from toolregistry import ToolRegistry, ChangeEvent, ChangeEventType

registry = ToolRegistry()

def my_callback(event: ChangeEvent) -> None:
    """Handle tool registry changes."""
    print(f"[{event.event_type.value}] {event.tool_name}")
    if event.reason:
        print(f"  Reason: {event.reason}")

# Register the callback
registry.on_change(my_callback)

# Changes will trigger the callback
def add(a: int, b: int) -> int:
    return a + b

registry.register(add)  # Triggers: [register] add
registry.disable("add", reason="Maintenance")  # Triggers: [disable] add
registry.enable("add")  # Triggers: [enable] add

# Remove callback when no longer needed
registry.remove_on_change(my_callback)
```

### Observability API

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b

registry.register(add)
registry.register(subtract)

# Disable a tool with a reason
registry.disable("subtract", reason="Under maintenance")

# Get status of all tools
status = registry.get_tools_status()
print(status)
# Output:
# [
#     {"name": "add", "enabled": True, "reason": None, "namespace": None},
#     {"name": "subtract", "enabled": False, "reason": "Under maintenance", "namespace": None}
# ]

# Filter to find disabled tools
disabled_tools = [s for s in status if not s["enabled"]]
print(disabled_tools)
# Output: [{"name": "subtract", "enabled": False, "reason": "Under maintenance", "namespace": None}]
```

### Tag-Based Bulk Disable

```python
from toolregistry import ToolRegistry, ToolMetadata, ToolTag

registry = ToolRegistry()

def read_file(path: str) -> str:
    """Read a file from disk."""
    ...

def delete_file(path: str) -> None:
    """Delete a file from disk."""
    ...

def send_email(to: str, body: str) -> None:
    """Send an email."""
    ...

registry.register(read_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.READ_ONLY}))
registry.register(delete_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.DESTRUCTIVE}))
registry.register(send_email, metadata=ToolMetadata(tags={ToolTag.NETWORK}))

# match="any" (default): disable tools that have AT LEAST ONE of the given tags
disabled = registry.disable_by_tags(
    {ToolTag.DESTRUCTIVE, ToolTag.NETWORK},
    match="any",
    reason="Restricted in read-only mode",
)
print(disabled)  # ['delete_file', 'send_email']

# match="all": disable only tools that carry EVERY specified tag
registry2 = ToolRegistry()
registry2.register(read_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.READ_ONLY}))
registry2.register(delete_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.DESTRUCTIVE}))

disabled2 = registry2.disable_by_tags(
    {ToolTag.FILE_SYSTEM, ToolTag.DESTRUCTIVE},
    match="all",
    reason="No destructive filesystem ops allowed",
)
print(disabled2)  # ['delete_file']
```

### Post-Registration Hook

```python
from toolregistry import ToolRegistry, PostRegisterHook, ToolMetadata, ToolTag

registry = ToolRegistry()

# Hook: auto-disable any privileged tool at registration time
def deny_privileged(tool_name: str, tool, registry) -> str | None:
    tags = tool.metadata.tags if tool.metadata else set()
    if ToolTag.PRIVILEGED in tags:
        return f"Privileged tool '{tool_name}' is not allowed in this environment"
    return None

registry.add_post_register_hook(deny_privileged)

def sudo_command(cmd: str) -> str:
    """Run a command with elevated privileges."""
    ...

registry.register(sudo_command, metadata=ToolMetadata(tags={ToolTag.PRIVILEGED}))

print(registry.is_enabled("sudo_command"))     # False
print(registry.get_disable_reason("sudo_command"))
# "Privileged tool 'sudo_command' is not allowed in this environment"

# Multiple hooks are invoked in registration order
def log_all(tool_name: str, tool, registry) -> None:
    print(f"[hook] registered: {tool_name}")

registry.add_post_register_hook(log_all)
```

## Integration Points

The ToolRegistry provides integration points for:

- **OpenAPI Services**: Automatic REST API tool generation
- **MCP Servers**: Model Context Protocol tool discovery
- **LangChain Tools**: LangChain ecosystem integration
- **Native Python**: Direct class and function registration

This makes it a central hub for managing tools from diverse sources within LLM applications.

## See Also

- [Events](../events.md) - Detailed documentation on `ChangeEvent`, `ChangeEventType`, and `ChangeCallback`
