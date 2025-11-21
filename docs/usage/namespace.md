# 命名空间和 ToolRegistry 操作

???+ note "更新日志"
    新增于版本：0.4.1

## 工具注册表中的命名空间

命名空间用于在注册表中组织工具，并在合并和分离等操作期间避免名称冲突。它们充当工具名称的前缀，确保清晰性和分离。

### OpenAI 函数命名约定

从 GPT-4.1 发布（2025年4月14日发布）开始，OpenAI 要求函数名称匹配模式 `^[a-zA-Z0-9_-]+$`。虽然点（.）以前在 GPT-4o 中被接受作为命名空间分隔符，但我们现在使用破折号（-）作为默认分隔符，因为 toolregistry 总是将函数名称规范化为 snake_case。

**此更改在版本 0.4.5 中实施。** 遇到问题的用户应尽快升级。虽然破折号是默认的，但点仍然可用作需要与其他提供者兼容的高级用户的可选分隔符。

### 关键特性

- **标准化**：工具名称使用 `normalize_tool_name` 函数进行规范化，将它们转换为 snake_case 并删除特殊字符、重复字符串和空白。
- **合并行为**：默认情况下，在合并期间，原始注册表名称作为前缀添加到所有工具。当启用 `force_namespace` 时，它强制所有命名空间被替换为发起注册表的名称。
!!! note
    即使只存在一个命名空间，它仍然会被保留。
- **分离行为**：具有特定前缀的工具可以提取到新的注册表中。默认情况下，除非将 `retain_namespace` 设置为 `True`，否则从提取的工具中删除前缀。当适用时，使用 `reduce_namespace` 方法删除前缀。

### 规范化示例

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

## 合并注册表

合并注册表允许您将多个注册表中的工具合并为一个。在合并过程中，`注册表名称` 用作前缀（命名空间）来清楚地区分来自不同注册表的工具。这确保工具得到有效的组织和管理。

### 参数

- `force_namespace`：如果为 `True`，强制所有工具使用发起合并的注册表的名称作为前缀，即使它们已经有命名空间。
- `keep_existing`：如果为 `True`，在名称冲突的情况下保留现有工具；否则覆盖它们。请注意，冲突的风险降低了，因为在合并过程中工具总是以其各自注册表的命名空间为前缀。

### 使用示例

我们建议按相似功能组织工具以形成注册表。`merge` 函数旨在集中多个注册表（功能组）以便向 LLM 展示。

#### 情况 1：默认行为（`force_namespace=False`）

```python
# MCP/OpenAPI 混合注册表示例
openapi_registry = ToolRegistry("openapi_math")
mcp_registry = ToolRegistry("mcp_math")

# 将 MCP 注册表合并到 OpenAPI 注册表
mixed_registry = openapi_registry
mixed_registry.merge(mcp_registry)

print(mixed_registry.get_available_tools())  # 来自两个注册表的工具
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

#### 情况 2：强制命名空间（`force_namespace=True`）

```python
# 带强制命名空间的 MCP/OpenAPI 混合注册表示例
openapi_registry = ToolRegistry("openapi_math")
mcp_registry = ToolRegistry("mcp_math")

# 使用强制命名空间将 MCP 注册表合并到 OpenAPI 注册表
mixed_registry_2 = openapi_registry
mixed_registry_2.merge(mcp_registry, force_namespace=True)

print(mixed_registry_2.get_available_tools())  # 来自两个注册表的工具，带强制命名空间
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

## 分离注册表

分离注册表允许您从现有注册表中提取具有特定前缀的工具，通常在合并操作之后。在分离过程中，除非将 `retain_namespace` 设置为 `True`，否则从提取的工具中删除前缀。如果注册表中的剩余工具只共享一个前缀，除非将 `retain_namespace` 设置为 `True`，否则它们也将通过使用 `reduce_namespace` 方法删除前缀来降级。

### 参数

- `retain_namespace`：如果为 `True`，在当前注册表和新注册表中保留工具的命名空间。如果为 `False`，使用 `reduce_namespace` 方法从新注册表中的工具中删除命名空间。

### 错误处理

- 如果没有找到具有指定前缀的工具，则引发 `ValueError`。

### 使用示例

这是一个保留命名空间的示例：

```python
# 来自 MCP/OpenAPI 混合注册表的示例
openapi_registry_2 = mixed_registry.spinoff("openapi_math", retain_namespace=True)

print(openapi_registry_2.get_available_tools())  # 来自 openapi 注册表的工具，带命名空间
print(mixed_registry.get_available_tools())  # 来自 mcp 注册表的工具
```

```python
['openapi_math.add_get', 'openapi_math.subtract_get', 'openapi_math.multiply_get', 'openapi_math.divide_get']
['mcp_math.add', 'mcp_math.subtract', 'mcp_math.multiply', 'mcp_math.divide']
```

这是另一个不保留命名空间的示例：

```python
# 来自 MCP/OpenAPI 混合注册表的示例
openapi_registry_2 = mixed_registry.spinoff("openapi_math")

print(openapi_registry_2.get_available_tools())  # 来自 openapi 注册表的工具，带命名空间
print(mixed_registry.get_available_tools())  # 来自 mcp 注册表的工具
```

```python
['add_get', 'subtract_get', 'multiply_get', 'divide_get']
['add', 'subtract', 'multiply', 'divide']
