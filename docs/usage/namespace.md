# Namespace and ToolRegistry Manipulation

???+ note "Changelog"
    New in version: 0.4.1

## Namespaces in Tool Registries

Namespaces are used to organize tools within a registry and avoid name conflicts during operations like merging and spinoff. They act as prefixes to tool names, ensuring clarity and separation.

### OpenAI Function Naming Convention

Starting from GPT-4.1 release (April 14, 2025 release), OpenAI requires function names to match the pattern `^[a-zA-Z0-9_-]+$`. While dots (.) were previously accepted as namespace separators in GPT-4o, we now use dashes (-) as the default separator since toolregistry always normalizes function names to snake_case.

**This change was implemented in version 0.4.5.** Users experiencing issues should upgrade as soon as possible. While dashes are the default, dots remain available as an optional separator for advanced users who need compatibility with other providers.

### Tool-Level Namespace Fields

Each `Tool` instance carries structured namespace information through two fields:

- **`namespace`**: Stores the original namespace string (after normalization). Used to determine group membership without parsing the `name` field.
- **`method_name`**: Stores the original method/function name before namespace prefixing. Preserved so that the base name can be recovered unambiguously.

The **`qualified_name`** property returns the registered `name`. The name is
authoritative and is rebuilt from `namespace`, `method_name`, and the registry's
separator whenever a namespace operation runs; it is never parsed back out of
the string.

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

registry.register(multiply, namespace="math_ops")
tool = registry["math_ops-multiply"]

print(tool.namespace)       # 'math_ops'
print(tool.method_name)     # 'multiply'
print(tool.qualified_name)  # 'math_ops-multiply'
```

### Registry-Level Separator (`name_sep`)

`ToolRegistry(name_sep=".")` applies that separator to every registration
source — native functions, class methods, MCP, OpenAPI, and LangChain. Read
it with `registry.name_sep`. `Tool.from_function(..., sep=".")` applies the
same rule when constructing a tool directly.

```python
from toolregistry import ToolRegistry

registry = ToolRegistry(name_sep=".")
registry.register(multiply, namespace="math_ops")

print(registry.get_available_tools())  # ['math_ops.multiply']
```

The registry key is always `tool.name`, and `tool.qualified_name` is the same
string. Changing `registry.name_sep` at runtime re-keys every namespaced tool
(and its override records) so a registry never mixes separators.

### Key Features

- **Standardization**: Tool names are normalized using the `normalize_tool_name` function, converting them to snake_case and removing special characters, repeating strings and whitespace.
- **Merge Behavior**: By default, the original registry name is prefixed to all tools during merging. When `force_namespace` is enabled, it forces all namespaces to be replaced with the initiating registry's name. Incoming tools are re-keyed with the receiving registry's `name_sep`, so merging registries that use different separators is lossless. Override records move with their tools.
!!! note
    Even if only one namespace exists, it will still be retained.
- **Spinoff Behavior**: Tools are selected by their `namespace` field (with a key-prefix fallback for legacy tools), using the registry's `name_sep`. The returned registry inherits that separator. By default, the prefix is removed from the extracted tools unless `retain_namespace` is set to `True`. `reduce_namespace` only flattens tools in the single remaining namespace and leaves unqualified tools untouched.

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
openapi_registry = ToolRegistry("openapi_math", name_sep=".")
mcp_registry = ToolRegistry("mcp_math", name_sep=".")

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
openapi_registry = ToolRegistry("openapi_math", name_sep=".")
mcp_registry = ToolRegistry("mcp_math", name_sep=".")

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

Spinoff registries allow you to extract tools from one namespace into a new registry, typically after a merge operation. Matching uses the registry's `name_sep` and the tool's `namespace` field. During the spinoff process, the prefix is removed from the extracted tools, unless `retain_namespace` is set to `True`. If the remaining tools in the source registry share only one namespace, they will also be downgraded by removing the prefix using the `reduce_namespace` method, unless `retain_namespace` is set to `True`.

### Parameters

- `retain_namespace`: If `True`, keeps the qualified names in the spun-off registry and skips namespace reduction in both registries. If `False`, removes the namespace from the extracted tools using the `reduce_namespace` method. Tools always move: the spun-off tools are removed from the source registry either way.

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

## See Also

- [Core Classes Overview](../api/core.md) -- architecture diagram and component relationships
- [ToolRegistry API Reference](../api/core/toolregistry.md) -- `merge()`, `spinoff()`, and namespace-related methods
