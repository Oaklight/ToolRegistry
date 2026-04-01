# Best Practices

## Tool Design Principles

### Write Clear Docstrings

ToolRegistry generates parameter schemas and descriptions from your function's docstring and type hints. LLMs rely on these descriptions to decide when and how to call your tools.

```python
@registry.register
def search_documents(query: str, limit: int = 10) -> list[dict]:
    """Search the document index for relevant results.

    Args:
        query: Natural language search query.
        limit: Maximum number of results to return (1-100).

    Returns:
        List of matching documents with title and snippet.
    """
    ...
```

!!! tip
    Use Google-style docstrings — ToolRegistry's schema generator parses `Args:` and `Returns:` sections automatically.

### Use Simple Types

LLMs work best with primitive types (`str`, `int`, `float`, `bool`) and simple containers (`list`, `dict`). Avoid complex custom types as parameters.

```python
# Good — LLM can easily construct these arguments
def create_event(title: str, date: str, attendees: list[str]) -> str: ...

# Avoid — LLM cannot construct a Pydantic model
def create_event(event: EventModel) -> str: ...
```

### Keep Functions Stateless

Tools should depend only on their input parameters, not on external mutable state. This makes tools safe for concurrent execution and easier to test.

```python
# Good — pure function
def celsius_to_fahrenheit(celsius: float) -> float:
    return celsius * 9 / 5 + 32

# Avoid — depends on external state
last_result = None
def celsius_to_fahrenheit(celsius: float) -> float:
    global last_result
    last_result = celsius * 9 / 5 + 32
    return last_result
```

---

## ToolRegistry-Specific Practices

### Classify Tools with ToolMetadata and ToolTag

Use `ToolMetadata` and `ToolTag` to declare behavioral characteristics. This information drives the permission system and execution engine.

```python
from toolregistry import ToolRegistry, Tool, ToolMetadata, ToolTag

registry = ToolRegistry()

# Mark read-only tools
tool = Tool.from_function(
    get_weather,
    metadata=ToolMetadata(
        tags=[ToolTag.READ_ONLY, ToolTag.NETWORK],
        timeout=10.0,
    ),
)
registry.register(tool)

# Mark destructive tools
tool = Tool.from_function(
    delete_file,
    metadata=ToolMetadata(
        tags=[ToolTag.DESTRUCTIVE, ToolTag.FILE_SYSTEM],
    ),
)
registry.register(tool)
```

Available tags: `READ_ONLY`, `DESTRUCTIVE`, `NETWORK`, `FILE_SYSTEM`, `SLOW`, `PRIVILEGED`.

### Design for Concurrent Execution

By default, `execute_tool_calls()` runs multiple tool calls in parallel. If your tool is not safe for concurrent execution (e.g., it writes to a shared file), mark it explicitly:

```python
tool = Tool.from_function(
    write_to_log,
    metadata=ToolMetadata(is_concurrency_safe=False),
)
```

When any tool in a batch has `is_concurrency_safe=False`, the entire batch runs sequentially.

### Use Cooperative Cancellation for Long-Running Tools

Tools that perform long operations should accept an `ExecutionContext` parameter to support timeout and cancellation:

```python
from toolregistry.executor import ExecutionContext

def process_large_dataset(data: list[str], _ctx: ExecutionContext) -> str:
    """Process a large dataset with progress reporting."""
    results = []
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # raises CancelledError if timed out
        results.append(transform(item))
        _ctx.report_progress(
            fraction=(i + 1) / len(data),
            message=f"Processed {i + 1}/{len(data)}",
        )
    return f"Processed {len(results)} items"
```

The `_ctx` parameter is auto-injected by the executor — callers never pass it explicitly. Combine with `ToolMetadata(timeout=30.0)` for hard timeout enforcement.

### Set Timeouts for External Calls

Tools that call external services should always have a timeout to prevent the executor from blocking indefinitely:

```python
tool = Tool.from_function(
    call_external_api,
    metadata=ToolMetadata(timeout=15.0, tags=[ToolTag.NETWORK]),
)
```

### Use Namespaces to Organize Related Tools

When registering multiple tools from a class or external source, use namespaces to avoid name collisions and improve discoverability:

```python
# Class-based tools get automatic namespace
registry.register_from_class(MathTools, namespace="math")
# Registered as: math-add, math-subtract, math-multiply

# MCP tools with namespace
registry.register_from_mcp("http://localhost:8000/mcp", namespace="search")
```

### Clean Up Resources

When using MCP or OpenAPI integrations, use context managers to ensure connections are properly closed:

```python
# Recommended: context manager
with ToolRegistry() as registry:
    registry.register_from_mcp("http://localhost:8000/mcp")
    results = registry.execute_tool_calls(tool_calls)

# Or explicit cleanup
registry = ToolRegistry()
try:
    registry.register_from_mcp("http://localhost:8000/mcp")
    results = registry.execute_tool_calls(tool_calls)
finally:
    registry.close()
```

---

## Security

### Validate at System Boundaries

Trust internal ToolRegistry APIs, but validate inputs that come from external sources (user input, LLM output, external APIs):

```python
@registry.register
def execute_query(sql: str) -> list[dict]:
    """Execute a read-only SQL query."""
    # Validate LLM-generated SQL before execution
    if any(keyword in sql.upper() for keyword in ["DROP", "DELETE", "UPDATE", "INSERT"]):
        return [{"error": "Only SELECT queries are allowed"}]
    return db.execute(sql)
```

### Use the Permission System

For production deployments, configure `PermissionPolicy` to control which tools can be executed:

```python
from toolregistry.permissions import (
    PermissionPolicy,
    ALLOW_READONLY,
    ASK_DESTRUCTIVE,
    DENY_PRIVILEGED,
)

policy = PermissionPolicy(rules=[
    ALLOW_READONLY,      # Auto-allow read-only tools
    ASK_DESTRUCTIVE,     # Require confirmation for destructive tools
    DENY_PRIVILEGED,     # Block privileged tools entirely
])
registry.set_permission_policy(policy)
```

See [Permission System](permissions.md) for the full guide.

---

## Testing

### Test Tools in Isolation

Test your tool functions independently before registering them:

```python
def test_calculate_area():
    assert calculate_area(3.0, 4.0) == 12.0
    assert calculate_area(0.0, 5.0) == 0.0
```

### Test the Full LLM Loop

For integration tests, verify the complete flow: schema generation → tool call → execution → result recovery:

```python
registry = ToolRegistry()
registry.register(calculate_area)

# Verify schema generation
schemas = registry.get_tools_json()
assert len(schemas) == 1
assert schemas[0]["function"]["name"] == "calculate_area"
```
