---
title: Result Size Management
summary: Automatic truncation and persistence for large tool outputs
description: How to configure max_result_size, truncation strategies, and result persistence to prevent oversized tool outputs from bloating LLM context
keywords: truncation, result size, max_result_size, persistence, TruncatedResult
author: Oaklight
---

# Result Size Management

Some tools produce large outputs — database queries, file reads, API responses — that can exceed token limits and bloat the LLM context. ToolRegistry provides automatic result truncation with optional persistence of the full output to a temporary file.

## Overview

When a tool's result exceeds a size limit, ToolRegistry:

1. Writes the **full result** to a temporary file (optional, enabled by default)
2. **Truncates** the result using a configurable strategy
3. Prepends a header with the original size and file path
4. Returns the truncated result to the LLM

## Configuring Size Limits

### Per-Tool Limit

Set `max_result_size` on `ToolMetadata` (in characters):

```python
from toolregistry import Tool, ToolMetadata

def query_database(sql: str) -> str:
    """Execute a SQL query and return results."""
    ...

registry.register(
    Tool.from_function(
        query_database,
        metadata=ToolMetadata(max_result_size=2000),
    )
)
```

### Registry-Wide Default

Set a default limit for all tools via `ToolRegistry`:

```python
from toolregistry import ToolRegistry

registry = ToolRegistry(default_max_result_size=5000)
```

Per-tool `max_result_size` takes precedence over the registry default. Tools with `max_result_size=None` (the default) have no limit unless the registry default is set.

## Truncation Strategies

Two strategies are available via `TruncationStrategy`:

| Strategy | Behavior |
|----------|----------|
| `HEAD` | Keep only the first `max_size` characters |
| `HEAD_TAIL` | Keep the first and last portions with a marker in the middle **(default)** |

### HEAD_TAIL (Default)

Splits the budget between the beginning and end of the result, inserting a marker showing how many characters were omitted:

```
First part of the output...
... (truncated 15000 chars) ...
...last part of the output
```

This preserves both the start (often column headers, initial context) and end (often summary or final results) of the output.

### HEAD

Simply cuts off the result at `max_size` characters. Use when only the beginning matters.

## Truncated Output Format

When truncation occurs, the result sent to the LLM includes a metadata header:

```
[Truncated: 20000 chars -> 2000 chars | full output: /tmp/toolregistry_results/query_database_1711900000_a1b2c3d4e5f6.txt]
First part of the output...
... (truncated 18000 chars) ...
...last part of the output
```

The LLM (or user) can access the full output at the persisted file path.

## Persistence

By default, the full result is written to a temporary file under `/tmp/toolregistry_results/` before truncation. The filename includes:

- Tool name
- Unix timestamp
- Content hash (SHA-256, first 12 chars)

Example: `query_database_1711900000_a1b2c3d4e5f6.txt`

## Programmatic Access

The truncation module can also be used directly:

```python
from toolregistry.truncation import truncate_result, TruncationStrategy

result = truncate_result(
    result_str=very_long_string,
    max_size=2000,
    strategy=TruncationStrategy.HEAD_TAIL,
    tool_name="my_tool",
    persist=True,
)

print(result.truncated)       # True
print(result.original_size)   # 20000
print(result.full_path)       # "/tmp/toolregistry_results/..."
print(result.content)         # truncated content
print(str(result))            # formatted with header
```

### TruncatedResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The (possibly truncated) text content |
| `original_size` | `int` | Original result size in characters |
| `truncated` | `bool` | Whether truncation was applied |
| `full_path` | `str \| None` | Path to the persisted full result |
