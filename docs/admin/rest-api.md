# REST API Reference

The Admin Panel exposes a RESTful API for programmatic access.

## Authentication

When authentication is enabled (remote mode or custom token), include the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8081/api/tools
```

## API Endpoints

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tools` | List all tools with status |
| `GET` | `/api/tools/{name}` | Get single tool details |
| `POST` | `/api/tools/{name}/enable` | Enable a tool |
| `POST` | `/api/tools/{name}/disable` | Disable a tool |
| `GET` | `/api/tools/{name}/permissions` | Evaluate permission policy for a tool |
| `PATCH` | `/api/tools/{name}/metadata` | Update tool metadata (`think_augment`, `defer`) |

### Namespaces

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/namespaces` | List all namespaces |
| `POST` | `/api/namespaces/{ns}/enable` | Enable all tools in namespace |
| `POST` | `/api/namespaces/{ns}/disable` | Disable all tools in namespace |
| `PATCH` | `/api/namespaces/{ns}/metadata` | Update metadata for all tools in namespace |

### Execution Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/logs` | Get execution logs |
| `GET` | `/api/logs/stats` | Get execution statistics |
| `DELETE` | `/api/logs` | Clear all logs |

### State Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/state` | Export current state |
| `POST` | `/api/state` | Import/restore state |

## API Examples

=== "List Tools"

    ```bash
    curl http://localhost:8081/api/tools
    ```

    Response:
    ```json
    {
      "tools": [
        {
          "name": "calculator_add",
          "enabled": true,
          "reason": null,
          "namespace": "calculator"
        }
      ]
    }
    ```

=== "Get Tool Details"

    ```bash
    curl http://localhost:8081/api/tools/calculator_add
    ```

    Response:
    ```json
    {
      "name": "calculator_add",
      "namespace": "calculator",
      "method_name": "add",
      "description": "Add two numbers",
      "enabled": true,
      "reason": null,
      "schema": {
        "type": "function",
        "function": {
          "name": "calculator_add",
          "description": "Add two numbers",
          "parameters": {...}
        }
      }
    }
    ```

=== "Disable Tool"

    ```bash
    curl -X POST http://localhost:8081/api/tools/calculator_add/disable \
      -H "Content-Type: application/json" \
      -d '{"reason": "Under maintenance"}'
    ```

    Response:
    ```json
    {
      "success": true,
      "message": "Tool 'calculator_add' disabled",
      "reason": "Under maintenance"
    }
    ```

=== "Get Logs"

    ```bash
    curl "http://localhost:8081/api/logs?limit=10&status=success"
    ```

    Response:
    ```json
    {
      "entries": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "tool_name": "calculator_add",
          "timestamp": "2024-01-15T10:30:00",
          "status": "success",
          "duration_ms": 1.5,
          "arguments": {"a": 1, "b": 2},
          "result": "3",
          "error": null,
          "metadata": {}
        }
      ],
      "count": 1
    }
    ```

=== "Export State"

    ```bash
    curl http://localhost:8081/api/state
    ```

    Response:
    ```json
    {
      "disabled": {
        "calculator_add": "Under maintenance"
      },
      "tools": ["calculator_add", "calculator_subtract"]
    }
    ```

=== "Update Tool Metadata"

    ```bash
    curl -X PATCH http://localhost:8081/api/tools/calculator_add/metadata \
      -H "Content-Type: application/json" \
      -d '{"think_augment": true}'
    ```

    Response:
    ```json
    {
      "success": true,
      "message": "Metadata updated for tool 'calculator_add'",
      "updated": {"think_augment": true}
    }
    ```

=== "Update Namespace Metadata"

    ```bash
    curl -X PATCH http://localhost:8081/api/namespaces/calculator/metadata \
      -H "Content-Type: application/json" \
      -d '{"defer": true}'
    ```

    Response:
    ```json
    {
      "success": true,
      "message": "Metadata updated for namespace 'calculator'",
      "tools_updated": 3,
      "updated": {"defer": true}
    }
    ```
