# Examples

## Basic Usage with Logging

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

## Remote Access Configuration

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

## Integration with FastAPI

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

## Execution Log Analysis

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
