# OpenAPIToolWrapper

提供同步和异步方法用于 OpenAPI 工具调用的包装器类。

## 概览

`OpenAPIToolWrapper` 是专门为 OpenAPI/Swagger REST API 设计的包装器，提供 ToolRegistry 与 RESTful 服务之间的无缝 HTTP 通信。它处理 HTTP 协议通信的复杂性，包括参数处理、方法处理和响应管理。

## 主要特性

- **REST API 集成**：全面支持 RESTful API 操作
- **HTTP 方法支持**：处理 GET、POST、PUT、DELETE 及其他 HTTP 方法
- **参数处理**：自动处理查询参数和请求体
- **HTTP 客户端集成**：使用内置 HTTP 客户端实现同步和异步 HTTP 操作
- **错误处理**：全面的 HTTP 错误处理和状态码管理
- **响应处理**：自动 JSON 响应解析和错误处理

## 架构

OpenAPIToolWrapper 通过 OpenAPI 特定功能扩展了 `BaseToolWrapper`：

### 核心组件

1. **HTTP 客户端管理**：配置和管理 HTTP 客户端实例
2. **方法处理**：将请求路由到适当的 HTTP 方法
3. **参数映射**：将参数处理为 HTTP 请求参数
4. **响应处理**：处理 HTTP 响应和错误条件

### 请求流程

```
工具调用请求
    ↓
参数处理
    ↓
HTTP 方法选择
    ↓
请求构建
    ↓
HTTP 执行
    ↓
响应处理
    ↓
结果规范化
```

## API 参考

::: toolregistry.integrations.openapi.integration.OpenAPIToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 使用示例

### 基本 OpenAPI 工具包装器

```python
from toolregistry.integrations.openapi.integration import OpenAPIToolWrapper
from toolregistry.utils import HttpClientConfig

# Configure HTTP client
client_config = HttpClientConfig(
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer token"}
)

# Create wrapper for GET request
get_wrapper = OpenAPIToolWrapper(
    client_config=client_config,
    name="get_user",
    method="GET",
    path="/users/{user_id}",
    params=["user_id"]
)

# Execute tool
result = get_wrapper(user_id="123")  # Sync
result = await get_wrapper(user_id="123")  # Async
```

### 带请求体的 POST 请求

```python
# Create wrapper for POST request
post_wrapper = OpenAPIToolWrapper(
    client_config=client_config,
    name="create_user",
    method="POST",
    path="/users",
    params=["name", "email", "age"]
)

# Execute with request body
result = post_wrapper(
    name="John Doe",
    email="john@example.com",
    age=30
)
```

## HTTP 方法支持

### GET 请求

```python
# Query parameters
wrapper = OpenAPIToolWrapper(
    client_config, "search_users", "GET", "/users",
    params=["query", "limit", "offset"]
)

# Results in: GET /users?query=john&limit=10&offset=0
result = wrapper(query="john", limit=10, offset=0)
```

### POST/PUT 请求

```python
# JSON body
wrapper = OpenAPIToolWrapper(
    client_config, "update_user", "PUT", "/users/{id}",
    params=["id", "name", "email"]
)

# Results in: PUT /users/123 with JSON body
result = wrapper(id="123", name="Jane Doe", email="jane@example.com")
```

### DELETE 请求

```python
# DELETE with path parameters
wrapper = OpenAPIToolWrapper(
    client_config, "delete_user", "DELETE", "/users/{id}",
    params=["id"]
)

result = wrapper(id="123")
```

## 配置模式

### 基本配置

```python
client_config = HttpClientConfig(
    base_url="https://api.example.com"
)
```

### 认证配置

```python
client_config = HttpClientConfig(
    base_url="https://api.example.com",
    headers={
        "Authorization": "Bearer your-token",
        "Content-Type": "application/json"
    }
)
```

### 超时配置

```python
client_config = HttpClientConfig(
    base_url="https://api.example.com",
    timeout=30.0
)
```

## 错误处理

该包装器提供全面的 HTTP 错误处理：

### HTTP 状态错误

```python
try:
    result = wrapper(user_id="999")  # User not found
except Exception as e:
    print(f"HTTP Error: {e}")
```

### 网络错误

```python
try:
    result = wrapper(param="value")
except Exception as e:
    print(f"Request failed: {e}")
```

### 自动错误处理

```python
# HTTP errors automatically raise exceptions
# 4xx and 5xx status codes trigger HttpStatusError
# Network issues trigger HttpConnectionError
```

## 响应处理

### JSON 响应

```python
# Automatic JSON parsing
wrapper = OpenAPIToolWrapper(client_config, "get_data", "GET", "/data")
result = wrapper()  # Returns parsed JSON object

# If response is not JSON, returns raw text
# Non-JSON-serializable content is converted to string
```

### 内容类型

- **application/json**：自动解析为 Python 对象
- **text/plain**：返回字符串
- **其他类型**：返回原始内容或字符串表示

## 集成模式

### 与 OpenAPI 集成配合使用

```python
from toolregistry import ToolRegistry
from toolregistry.integrations.openapi import OpenAPIIntegration

registry = ToolRegistry()
openapi_integration = OpenAPIIntegration(registry)

# Automatically creates OpenAPIToolWrapper instances
# for each endpoint in the OpenAPI spec
await openapi_integration.register_openapi_tools_async(
    client_config, openapi_spec
)
```

### 手动创建包装器

```python
# Direct wrapper usage for specific endpoints
wrapper = OpenAPIToolWrapper(
    client_config=client_config,
    name="custom_endpoint",
    method="POST",
    path="/custom/path",
    params=["param1", "param2"]
)
```

OpenAPIToolWrapper 提供了强大的 HTTP 通信能力，使其成为将 RESTful API 集成到 ToolRegistry 生态系统的理想选择，同时保持标准化的工具接口。
