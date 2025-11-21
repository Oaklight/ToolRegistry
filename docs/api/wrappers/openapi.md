# OpenAPIToolWrapper

Wrapper class that provides both synchronous and asynchronous methods for OpenAPI tool calls.

## Overview

`OpenAPIToolWrapper` serves as the specialized wrapper for OpenAPI/Swagger REST APIs, providing seamless HTTP communication between ToolRegistry and RESTful services. It handles the complexities of HTTP protocol communication, including parameter processing, method handling, and response management.

## Key Features

- **REST API Integration**: Full support for RESTful API operations
- **HTTP Method Support**: Handles GET, POST, PUT, DELETE, and other HTTP methods
- **Parameter Processing**: Automatic processing of query parameters and request bodies
- **HTTP Client Integration**: Uses httpx for both synchronous and asynchronous HTTP operations
- **Error Handling**: Comprehensive HTTP error handling with status code management
- **Response Processing**: Automatic JSON response parsing and error handling

## Architecture

The OpenAPIToolWrapper extends `BaseToolWrapper` with OpenAPI-specific functionality:

### Core Components

1. **HTTP Client Management**: Configures and manages httpx client instances
2. **Method Handling**: Routes requests to appropriate HTTP methods
3. **Parameter Mapping**: Processes arguments into HTTP request parameters
4. **Response Processing**: Handles HTTP responses and error conditions

### Request Flow

```
Tool Call Request
    ↓
Parameter Processing
    ↓
HTTP Method Selection
    ↓
Request Construction
    ↓
HTTP Execution
    ↓
Response Processing
    ↓
Result Normalization
```

## API Reference

::: toolregistry.openapi.integration.OpenAPIToolWrapper
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Usage Examples

### Basic OpenAPI Tool Wrapper

```python
from toolregistry.openapi.integration import OpenAPIToolWrapper
from toolregistry.utils import HttpxClientConfig

# Configure HTTP client
client_config = HttpxClientConfig(
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

### POST Request with Body

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

## HTTP Method Support

### GET Requests

```python
# Query parameters
wrapper = OpenAPIToolWrapper(
    client_config, "search_users", "GET", "/users",
    params=["query", "limit", "offset"]
)

# Results in: GET /users?query=john&limit=10&offset=0
result = wrapper(query="john", limit=10, offset=0)
```

### POST/PUT Requests

```python
# JSON body
wrapper = OpenAPIToolWrapper(
    client_config, "update_user", "PUT", "/users/{id}",
    params=["id", "name", "email"]
)

# Results in: PUT /users/123 with JSON body
result = wrapper(id="123", name="Jane Doe", email="jane@example.com")
```

### DELETE Requests

```python
# DELETE with path parameters
wrapper = OpenAPIToolWrapper(
    client_config, "delete_user", "DELETE", "/users/{id}",
    params=["id"]
)

result = wrapper(id="123")
```

## Configuration Patterns

### Basic Configuration

```python
client_config = HttpxClientConfig(
    base_url="https://api.example.com"
)
```

### Authenticated Configuration

```python
client_config = HttpxClientConfig(
    base_url="https://api.example.com",
    headers={
        "Authorization": "Bearer your-token",
        "Content-Type": "application/json"
    }
)
```

### Timeout Configuration

```python
client_config = HttpxClientConfig(
    base_url="https://api.example.com",
    timeout=30.0
)
```

## Error Handling

The wrapper provides comprehensive HTTP error handling:

### HTTP Status Errors

```python
try:
    result = wrapper(user_id="999")  # User not found
except httpx.HTTPStatusError as e:
    print(f"HTTP Error: {e.response.status_code}")
    print(f"Response: {e.response.text}")
```

### Network Errors

```python
try:
    result = wrapper(param="value")
except httpx.RequestError as e:
    print(f"Request failed: {e}")
```

### Automatic Error Handling

```python
# HTTP errors automatically raise exceptions
# 4xx and 5xx status codes trigger HTTPStatusError
# Network issues trigger RequestError
```

## Response Processing

### JSON Responses

```python
# Automatic JSON parsing
wrapper = OpenAPIToolWrapper(client_config, "get_data", "GET", "/data")
result = wrapper()  # Returns parsed JSON object

# If response is not JSON, returns raw text
# Non-JSON-serializable content is converted to string
```

### Content Types

- **application/json**: Automatically parsed to Python objects
- **text/plain**: Returns as string
- **Other types**: Returns raw content or string representation

## Integration Patterns

### With OpenAPI Integration

```python
from toolregistry import ToolRegistry
from toolregistry.openapi import OpenAPIIntegration

registry = ToolRegistry()
openapi_integration = OpenAPIIntegration(registry)

# Automatically creates OpenAPIToolWrapper instances
# for each endpoint in the OpenAPI spec
await openapi_integration.register_openapi_tools_async(
    client_config, openapi_spec
)
```

### Manual Wrapper Creation

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

The OpenAPIToolWrapper provides robust HTTP communication capabilities, making it ideal for integrating RESTful APIs into the ToolRegistry ecosystem while maintaining the standardized tool interface.
