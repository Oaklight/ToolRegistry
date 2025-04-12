# Advanced Usage

## Merging Registries

Merging registries allows you to combine tools from multiple registries into one. During the merge process, the `registry name` is used as a prefix (namespace) to clearly distinguish tools from different registries. This ensures that tools are organized and managed effectively.

We recommend organizing tools by similar functionality to form a registry. The `merge` function is intended to centralize multiple registries (functional groups) for convenient presentation to the LLM.

```python
# Example of MCP/OpenAPI mixed registry
openapi_registry = ToolRegistry("openapi_math")
mcp_registry = ToolRegistry("mcp_math")

# Merge MCP registry into OpenAPI registry
mixed_registry = openapi_registry
mixed_registry.merge(mcp_registry)

print(mixed_registry.get_available_tools())  # Tools from both registries
```

```python
 ['openapi_math.add_get', 'openapi_math.subtract_get', 'openapi_math.multiply_get', 'openapi_math.divide_get', 'mcp_math.add', 'mcp_math.subtract', 'mcp_math.multiply', 'mcp_math.divide']
```

## Spinoff Registries

Spinoff registries allow you to extract tools with specific prefixes from an existing registry, typically after a merge operation. During the spinoff process, the prefix is removed from the extracted tools. If the remaining tools in the registry share only one prefix, they will also be downgraded by removing the prefix. This is useful for reorganizing tools or creating specialized registries.

```python
# Example from MCP/OpenAPI mixed registry
openapi_registry2 = mixed_registry.spinoff("openapi_math")

print(openapi_registry2.get_available_tools())  # Tools from openapi registry
print(mixed_registry.get_available_tools())  # Tools with mcp registry
```

```python
['add_get', 'subtract_get', 'multiply_get', 'divide_get']
['add', 'subtract', 'multiply', 'divide']
```

## Tool Parameter Schema

```python
# Get the JSON schema for a tool's parameters
tool_params_schema = registry.get_tools_json("subtract")[0]['function']['parameters']
print(tool_params_schema)
```

```json
{
  "properties": {
    "a": { "title": "A", "type": "integer" },
    "b": { "title": "B", "type": "integer" }
  },
  "required": ["a", "b"],
  "title": "subtractParameters",
  "type": "object"
}
```
