---
title: Think-Augmented Tool Calling
summary: Chain-of-thought reasoning injected into tool call schemas
description: How ToolRegistry injects a thought property into every tool schema so LLMs can reason before acting, and how the property is stripped before execution
keywords: think, thought, chain-of-thought, reasoning, tool calling, THINK_PROPERTY
author: Oaklight
---

# Think-Augmented Tool Calling

ToolRegistry automatically injects a `thought` string property into every tool's parameter schema. This gives LLMs a dedicated field to express step-by-step reasoning about **why** they chose a tool and **how** they plan to use it — before the tool actually runs.

???+ note "Changelog"
    New in: [#49](../../pull/49) (Unreleased)
    Reference: [arXiv:2601.18282](https://arxiv.org/abs/2601.18282)

## How It Works

```mermaid
flowchart LR
    subgraph Schema Generation
        Tool["Tool schema"] --> Inject["Inject 'thought' property"]
        Inject --> LLM["Send to LLM"]
    end
    subgraph Execution
        LLM --> Call["LLM calls tool with thought + args"]
        Call --> Strip["Strip 'thought' from args"]
        Strip --> Run["Execute tool function"]
    end
```

1. **Injection**: When a `Tool` is created (via `@registry.register`, `Tool.from_function`, or any integration), `thought` is automatically added to the tool's JSON schema `properties`.
2. **LLM response**: The LLM fills in the `thought` field with its reasoning alongside the actual arguments.
3. **Stripping**: Before the tool function executes, ToolRegistry removes the `thought` parameter so the function receives only its declared arguments.

## Example

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Sunny in {city}"

# The schema sent to the LLM includes "thought"
schema = registry.get_schemas()
print(schema[0]["function"]["parameters"]["properties"].keys())
# dict_keys(['city', 'thought'])
```

When the LLM calls this tool, it might produce:

```json
{
  "name": "get_weather",
  "arguments": {
    "city": "Tokyo",
    "thought": "The user asked about weather in Tokyo, so I should call get_weather with city=Tokyo."
  }
}
```

ToolRegistry strips `thought` before execution — `get_weather` only receives `city="Tokyo"`.

## The `thought` Property Schema

The injected property looks like this in the JSON schema:

```json
{
  "thought": {
    "type": "string",
    "description": "Your step-by-step reasoning about why you chose this tool and how to use it."
  }
}
```

It is **not** marked as `required`, so LLMs may omit it without causing errors.

## Native `thought` Parameters

If your function already has a parameter named `thought`, ToolRegistry preserves it and does **not** override it:

```python
@registry.register
def analyze(data: str, thought: str = "") -> str:
    """Analyze data with optional reasoning."""
    # 'thought' is a real parameter here — it will NOT be stripped
    return f"Analysis of {data} with reasoning: {thought}"
```

ToolRegistry detects native `thought` parameters via introspection and skips both injection and stripping for that tool.

## Scope

Think-augmented injection works across all integration paths:

- Native Python functions (`@registry.register`)
- MCP tools (`register_from_mcp`)
- OpenAPI tools (`register_from_openapi`)
- LangChain tools (`register_from_langchain`)
- Class-based tools (`register_from_class`)
- Manually constructed `Tool` objects
