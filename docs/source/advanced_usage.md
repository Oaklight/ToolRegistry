# Advanced Usage

## Namespaces in Tool Registries

Namespaces are used to organize tools within a registry and avoid name conflicts during operations like merging and spinoff. They act as prefixes to tool names, ensuring clarity and separation.

### Key Features

- **Standardization**: Tool names are normalized using the `normalize_tool_name` function, converting them to snake_case and removing special characters, repeating strings and whitespace.
- **Merge Behavior**: By default, the original registry name is prefixed to all tools during merging. When `force_namespace` is enabled, it forces all namespaces to be replaced with the initiating registry's name. Note: Even if only one namespace exists, it will still be retained.
- **Spinoff Behavior**: Tools with specific prefixes can be extracted into new registries. By default, the prefix is removed from the extracted tools unless `retain_namespace` is set to `True`. The `reduce_namespace` method is used to remove prefixes when applicable.

### Normalization Example

```python
from toolregistry.utils import normalize_tool_name

print(normalize_tool_name("HTTP_Request"))  # 'http_request'
print(normalize_tool_name("add_add_get"))  # 'add_get'
print(normalize_tool_name("calculateTotal"))  # 'calculate_total'
print(normalize_tool_name("OpenAPI service"))  # 'open_api_service'
print(normalize_tool_name("get user info"))  # 'get_user_info'
print(normalize_tool_name("process.data"))  # 'process_data'
print(normalize_tool_name("encode@url"))  # 'encode_url'
```

## Merging Registries

Merging registries allows you to combine tools from multiple registries into one. During the merge process, the `registry name` is used as a prefix (namespace) to clearly distinguish tools from different registries. This ensures that tools are organized and managed effectively.

### Parameters

- `force_namespace`: If `True`, forces all tools to use the name of the registry initiating the merge as a prefix, even if they already have a namespace.
- `keep_existing`: If `True`, preserves existing tools in case of name conflicts; otherwise, overwrites them. Note that the risk of conflicts is reduced because tools are always prefixed with the namespace of their respective registries during the merge process.

### Example Usage

We recommend organizing tools by similar functionality to form a registry. The `merge` function is intended to centralize multiple registries (functional groups) for convenient presentation to the LLM.

#### Case 1: Default Behavior (`force_namespace=False`)

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
['openapi_math.add_get',
 'openapi_math.subtract_get',
 'openapi_math.multiply_get',
 'openapi_math.divide_get',
 'mcp_math.add',
 'mcp_math.subtract',
 'mcp_math.multiply',
 'mcp_math.divide']
```

#### Case 2: Forced Namespace (`force_namespace=True`)

```python
# Example of MCP/OpenAPI mixed registry with forced namespace
openapi_registry = ToolRegistry("openapi_math")
mcp_registry = ToolRegistry("mcp_math")

# Merge MCP registry into OpenAPI registry with forced namespace
mixed_registry_2 = openapi_registry
mixed_registry_2.merge(mcp_registry, force_namespace=True)

print(mixed_registry_2.get_available_tools())  # Tools from both registries with forced namespace
```

```python
['openapi_math.add_get',
 'openapi_math.subtract_get',
 'openapi_math.multiply_get',
 'openapi_math.divide_get',
 'openapi_math.add',
 'openapi_math.subtract',
 'openapi_math.multiply',
 'openapi_math.divide']
```

## Spinoff Registries

Spinoff registries allow you to extract tools with specific prefixes from an existing registry, typically after a merge operation. During the spinoff process, the prefix is removed from the extracted tools, unless `retain_namespace` is set to `True`. If the remaining tools in the registry share only one prefix, they will also be downgraded by removing the prefix using the `reduce_namespace` method, unless `retain_namespace` is set to `True`.

### Parameters

- `retain_namespace`: If `True`, retains the namespace of tools in both the current registry and the new registry. If `False`, removes the namespace from tools in the new registry using the `reduce_namespace` method.

### Error Handling

- Raises `ValueError` if no tools with the specified prefix are found.

### Example Usage

Here is an example where we retain the namespace:

```python
# Example from MCP/OpenAPI mixed registry
openapi_registry_2 = mixed_registry.spinoff("openapi_math", retain_namespace=True)

print(openapi_registry_2.get_available_tools())  # Tools from openapi registry with namespace
print(mixed_registry.get_available_tools())  # Tools with mcp registry
```

```python
['openapi_math.add_get', 'openapi_math.subtract_get', 'openapi_math.multiply_get', 'openapi_math.divide_get']
['mcp_math.add', 'mcp_math.subtract', 'mcp_math.multiply', 'mcp_math.divide']
```

Here is another example where we don't retain the namespace:

```python
# Example from MCP/OpenAPI mixed registry
openapi_registry_2 = mixed_registry.spinoff("openapi_math")

print(openapi_registry_2.get_available_tools())  # Tools from openapi registry with namespace
print(mixed_registry.get_available_tools())  # Tools with mcp registry
```

```python
['add_get', 'subtract_get', 'multiply_get', 'divide_get']
['add', 'subtract', 'multiply', 'divide']
```
