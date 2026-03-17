# Admin Panel

The Admin Panel provides a built-in HTTP server for managing and monitoring your ToolRegistry instance. It offers both a REST API and an optional web-based UI for real-time tool management.

## Overview

The Admin Panel is designed with the following principles:

- **Minimalism**: Zero external dependencies - uses only Python's standard library (`http.server`)
- **Zero Configuration**: Works out of the box with sensible defaults
- **Universality**: Compatible with any HTTP client or browser
- **Security**: Built-in token authentication for remote access

### Key Features

- Enable/disable tools and namespaces at runtime
- View tool schemas and metadata
- Monitor execution logs with filtering and statistics
- Export/import registry state
- Web UI for visual management

## Quick Start

### Basic Usage

```python
from toolregistry import ToolRegistry

# Create registry and register tools
registry = ToolRegistry()

@registry.register
def my_tool(x: int) -> int:
    """Multiply input by 2."""
    return x * 2

# Enable the admin panel
info = registry.enable_admin(port=8081)
print(f"Admin panel: {info.url}")
```

### Accessing the Web UI

Once enabled, open your browser and navigate to the URL printed (e.g., `http://localhost:8081`). The web UI provides:

- Tool list with enable/disable toggles
- Namespace management
- Execution log viewer
- State export/import functionality

## Configuration

The `enable_admin()` method accepts the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | The host address to bind to |
| `port` | `int` | `8081` | The port number to listen on |
| `serve_ui` | `bool` | `True` | Whether to serve the web UI at root path |
| `remote` | `bool` | `False` | Whether to allow remote connections |
| `auth_token` | `str \| None` | `None` | Authentication token for API access |

### Configuration Examples

=== "Local Development"

    ```python
    # Default: local access only, no authentication
    info = registry.enable_admin()
    print(f"Admin panel: {info.url}")
    ```

=== "Remote Access"

    ```python
    # Remote access with auto-generated token
    info = registry.enable_admin(remote=True)
    print(f"Admin panel: {info.url}")
    print(f"Token: {info.token}")  # Auto-generated secure token
    ```

=== "Custom Token"

    ```python
    # Remote access with custom token
    info = registry.enable_admin(
        remote=True,
        auth_token="my-secure-token-123"
    )
    ```

=== "API Only"

    ```python
    # Disable web UI, serve API only
    info = registry.enable_admin(serve_ui=False)
    ```

### AdminInfo Object

The `enable_admin()` method returns an `AdminInfo` object with the following attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `host` | `str` | The host address the server is bound to |
| `port` | `int` | The port number the server is listening on |
| `url` | `str` | The full URL to access the admin panel |
| `token` | `str \| None` | The authentication token (if auth is enabled) |

## Execution Logging

The Admin Panel integrates with ToolRegistry's execution logging feature to provide detailed insights into tool usage.

### Enabling Execution Logs

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Enable logging with custom buffer size
log = registry.enable_logging(max_entries=1000)

# Register and use tools...
@registry.register
def calculator_add(a: int, b: int) -> int:
    return a + b

# Enable admin panel to view logs
info = registry.enable_admin()
```

### Log Entry Structure

Each execution log entry contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier (UUID) |
| `tool_name` | `str` | Name of the executed tool |
| `timestamp` | `datetime` | When the execution occurred |
| `status` | `ExecutionStatus` | `success`, `error`, or `disabled` |
| `duration_ms` | `float` | Execution duration in milliseconds |
| `arguments` | `dict` | Input arguments passed to the tool |
| `result` | `Any` | Execution result (for successful executions) |
| `error` | `str \| None` | Error message (for failed executions) |
| `metadata` | `dict` | Additional metadata |

### Querying Logs Programmatically

```python
# Get the execution log instance
log = registry.get_execution_log()

if log:
    # Get recent entries
    entries = log.get_entries(limit=10)
    
    # Filter by tool name
    calc_entries = log.get_entries(tool_name="calculator_add")
    
    # Filter by status
    from toolregistry.admin import ExecutionStatus
    errors = log.get_entries(status=ExecutionStatus.ERROR)
    
    # Get statistics
    stats = log.get_stats()
    print(f"Total executions: {stats['total_entries']}")
    print(f"Average duration: {stats['avg_duration_ms']:.2f}ms")
```

## REST API Reference

The Admin Panel exposes a RESTful API for programmatic access.

### Authentication

When authentication is enabled (remote mode or custom token), include the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8081/api/tools
```

### API Endpoints

#### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tools` | List all tools with status |
| `GET` | `/api/tools/{name}` | Get single tool details |
| `POST` | `/api/tools/{name}/enable` | Enable a tool |
| `POST` | `/api/tools/{name}/disable` | Disable a tool |

#### Namespaces

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/namespaces` | List all namespaces |
| `POST` | `/api/namespaces/{ns}/enable` | Enable all tools in namespace |
| `POST` | `/api/namespaces/{ns}/disable` | Disable all tools in namespace |

#### Execution Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/logs` | Get execution logs |
| `GET` | `/api/logs/stats` | Get execution statistics |
| `DELETE` | `/api/logs` | Clear all logs |

#### State Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/state` | Export current state |
| `POST` | `/api/state` | Import/restore state |

### API Examples

=== "List Tools"

    ```bash
    curl http://localhost:8081/api/tools
    ```

    Response:
    ```json
    {
      "tools": [
        {
          "name": "calculator_add",
          "enabled": true,
          "reason": null,
          "namespace": "calculator"
        }
      ]
    }
    ```

=== "Get Tool Details"

    ```bash
    curl http://localhost:8081/api/tools/calculator_add
    ```

    Response:
    ```json
    {
      "name": "calculator_add",
      "namespace": "calculator",
      "method_name": "add",
      "description": "Add two numbers",
      "enabled": true,
      "reason": null,
      "schema": {
        "type": "function",
        "function": {
          "name": "calculator_add",
          "description": "Add two numbers",
          "parameters": {...}
        }
      }
    }
    ```

=== "Disable Tool"

    ```bash
    curl -X POST http://localhost:8081/api/tools/calculator_add/disable \
      -H "Content-Type: application/json" \
      -d '{"reason": "Under maintenance"}'
    ```

    Response:
    ```json
    {
      "success": true,
      "message": "Tool 'calculator_add' disabled",
      "reason": "Under maintenance"
    }
    ```

=== "Get Logs"

    ```bash
    curl "http://localhost:8081/api/logs?limit=10&status=success"
    ```

    Response:
    ```json
    {
      "entries": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "tool_name": "calculator_add",
          "timestamp": "2024-01-15T10:30:00",
          "status": "success",
          "duration_ms": 1.5,
          "arguments": {"a": 1, "b": 2},
          "result": "3",
          "error": null,
          "metadata": {}
        }
      ],
      "count": 1
    }
    ```

=== "Export State"

    ```bash
    curl http://localhost:8081/api/state
    ```

    Response:
    ```json
    {
      "disabled": {
        "calculator_add": "Under maintenance"
      },
      "tools": ["calculator_add", "calculator_subtract"]
    }
    ```

## Web UI Guide

The built-in web UI provides a visual interface for managing your ToolRegistry.

### Interface Overview

The web UI is organized into several sections:

1. **Tools Panel**: Lists all registered tools with enable/disable toggles
2. **Namespaces Panel**: Shows namespaces with bulk enable/disable controls
3. **Logs Panel**: Displays execution history with filtering options
4. **State Panel**: Provides export/import functionality

### Tool Management

- Click the toggle switch next to a tool to enable/disable it
- Disabled tools show the reason (if provided)
- Click on a tool name to view its full schema

### Namespace Management

- Enable/disable all tools in a namespace with a single click
- View tool counts per namespace
- See enabled/disabled breakdown

### Execution Log Viewer

- Filter logs by tool name or status
- View execution details including arguments and results
- Clear logs when needed
- View aggregate statistics

### State Import/Export

- Export current disabled state as JSON
- Import previously exported state
- Useful for backup/restore scenarios

## Security Considerations

### Local vs Remote Access

| Mode | Binding | Authentication | Use Case |
|------|---------|----------------|----------|
| Local (default) | `127.0.0.1` | Optional | Development, testing |
| Remote | `0.0.0.0` | Required | Production, multi-user |

### Token Authentication

When `remote=True` or `auth_token` is provided:

- All API requests require the `Authorization: Bearer <token>` header
- Tokens are compared using constant-time comparison to prevent timing attacks
- Auto-generated tokens are 32-character hex strings (128 bits of entropy)

### Best Practices

!!! warning "Production Deployment"
    For production deployments, always:
    
    1. Use `remote=True` with a strong custom token
    2. Deploy behind a reverse proxy (nginx, Caddy) with HTTPS
    3. Restrict access using firewall rules
    4. Consider disabling the web UI (`serve_ui=False`) if not needed

!!! tip "Token Management"
    - Store tokens securely (environment variables, secrets manager)
    - Rotate tokens periodically
    - Use different tokens for different environments

## Examples

### Basic Usage with Logging

```python
from toolregistry import ToolRegistry

# Create registry
registry = ToolRegistry()

# Register tools
@registry.register
def greet(name: str) -> str:
    """Greet a person by name."""
    return f"Hello, {name}!"

@registry.register
def calculate(a: int, b: int, op: str = "add") -> int:
    """Perform a calculation."""
    if op == "add":
        return a + b
    elif op == "subtract":
        return a - b
    else:
        raise ValueError(f"Unknown operation: {op}")

# Enable execution logging
registry.enable_logging(max_entries=1000)

# Enable admin panel
info = registry.enable_admin(port=8081)
print(f"Admin panel: {info.url}")

# Keep the script running
import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    registry.disable_admin()
```

### Remote Access Configuration

```python
from toolregistry import ToolRegistry
import os

registry = ToolRegistry()

# ... register tools ...

# Get token from environment or generate
token = os.environ.get("ADMIN_TOKEN")

# Enable remote access
info = registry.enable_admin(
    port=8081,
    remote=True,
    auth_token=token  # None = auto-generate
)

print(f"Admin panel: {info.url}")
if info.token:
    print(f"Token: {info.token}")
```

### Integration with FastAPI

```python
from fastapi import FastAPI
from toolregistry import ToolRegistry
from contextlib import asynccontextmanager

registry = ToolRegistry()

# Register tools
@registry.register
def my_tool(x: int) -> int:
    return x * 2

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enable admin panel on startup
    info = registry.enable_admin(port=8082)
    print(f"Admin panel: {info.url}")
    yield
    # Disable on shutdown
    registry.disable_admin()

app = FastAPI(lifespan=lifespan)

@app.post("/execute")
async def execute_tool(name: str, args: dict):
    tool = registry.get_callable(name)
    if tool:
        return {"result": tool(**args)}
    return {"error": "Tool not found"}
```

### Execution Log Analysis

```python
from toolregistry import ToolRegistry
from toolregistry.admin import ExecutionStatus

registry = ToolRegistry()
log = registry.enable_logging()

# ... execute tools ...

# Analyze execution patterns
stats = log.get_stats()

print(f"Total executions: {stats['total_entries']}")
print(f"Success rate: {stats['by_status'].get('success', 0) / stats['total_entries'] * 100:.1f}%")
print(f"Average duration: {stats['avg_duration_ms']:.2f}ms")

# Find slowest tools
by_tool = stats['by_tool']
print("\nExecutions by tool:")
for tool_name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
    print(f"  {tool_name}: {count}")

# Get recent errors
errors = log.get_entries(status=ExecutionStatus.ERROR, limit=5)
for entry in errors:
    print(f"Error in {entry.tool_name}: {entry.error}")
```

## Stopping the Admin Panel

```python
# Stop the admin panel
registry.disable_admin()

# Check if running
info = registry.get_admin_info()
if info:
    print(f"Still running at {info.url}")
else:
    print("Admin panel stopped")
```
