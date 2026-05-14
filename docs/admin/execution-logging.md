# Execution Logging

The Admin Panel integrates with ToolRegistry's execution logging feature to provide detailed insights into tool usage.

## Enabling Execution Logs

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

## Log Entry Structure

Each execution log entry contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier (UUID) |
| `tool_name` | `str` | Name of the executed tool |
| `timestamp` | `datetime` | When the execution occurred |
| `status` | `ExecutionStatus` | `success`, `error`, `timeout`, or `disabled` |
| `duration_ms` | `float` | Execution duration in milliseconds |
| `arguments` | `dict` | Input arguments passed to the tool |
| `result` | `Any` | Execution result (for successful executions) |
| `error` | `str \| None` | Error message (for failed executions) |
| `exception_type` | `str \| None` | Qualified exception class name, e.g. `"ValueError"` |
| `traceback` | `str \| None` | Formatted traceback string from the exception |
| `metadata` | `dict` | Additional metadata |

## Querying Logs Programmatically

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
