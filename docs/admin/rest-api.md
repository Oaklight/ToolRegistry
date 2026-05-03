# REST API 参考

管理面板提供 RESTful API 用于编程访问。

## 认证

当启用认证时（远程模式或自定义令牌），需要在 `Authorization` 头中包含令牌：

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8081/api/tools
```

## API 端点

### 工具

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/tools` | 列出所有工具及状态 |
| `GET` | `/api/tools/{name}` | 获取单个工具详情 |
| `POST` | `/api/tools/{name}/enable` | 启用工具 |
| `POST` | `/api/tools/{name}/disable` | 禁用工具 |
| `GET` | `/api/tools/{name}/permissions` | 评估工具的权限策略 |
| `PATCH` | `/api/tools/{name}/metadata` | 更新工具元数据（`think_augment`、`defer`） |

### 命名空间

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/namespaces` | 列出所有命名空间 |
| `POST` | `/api/namespaces/{ns}/enable` | 启用命名空间中的所有工具 |
| `POST` | `/api/namespaces/{ns}/disable` | 禁用命名空间中的所有工具 |
| `PATCH` | `/api/namespaces/{ns}/metadata` | 更新命名空间中所有工具的元数据 |

### 执行日志

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/logs` | 获取执行日志 |
| `GET` | `/api/logs/stats` | 获取执行统计 |
| `DELETE` | `/api/logs` | 清除所有日志 |

### 状态管理

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/state` | 导出当前状态 |
| `POST` | `/api/state` | 导入/恢复状态 |

## API 示例

=== "列出工具"

    ```bash
    curl http://localhost:8081/api/tools
    ```

    响应：
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

=== "获取工具详情"

    ```bash
    curl http://localhost:8081/api/tools/calculator_add
    ```

    响应：
    ```json
    {
      "name": "calculator_add",
      "namespace": "calculator",
      "method_name": "add",
      "description": "两数相加",
      "enabled": true,
      "reason": null,
      "schema": {
        "type": "function",
        "function": {
          "name": "calculator_add",
          "description": "两数相加",
          "parameters": {...}
        }
      }
    }
    ```

=== "禁用工具"

    ```bash
    curl -X POST http://localhost:8081/api/tools/calculator_add/disable \
      -H "Content-Type: application/json" \
      -d '{"reason": "维护中"}'
    ```

    响应：
    ```json
    {
      "success": true,
      "message": "Tool 'calculator_add' disabled",
      "reason": "维护中"
    }
    ```

=== "获取日志"

    ```bash
    curl "http://localhost:8081/api/logs?limit=10&status=success"
    ```

    响应：
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

=== "导出状态"

    ```bash
    curl http://localhost:8081/api/state
    ```

    响应：
    ```json
    {
      "disabled": {
        "calculator_add": "维护中"
      },
      "tools": ["calculator_add", "calculator_subtract"]
    }
    ```

=== "更新工具元数据"

    ```bash
    curl -X PATCH http://localhost:8081/api/tools/calculator_add/metadata \
      -H "Content-Type: application/json" \
      -d '{"think_augment": true}'
    ```

    响应：
    ```json
    {
      "success": true,
      "message": "Metadata updated for tool 'calculator_add'",
      "updated": {"think_augment": true}
    }
    ```

=== "更新命名空间元数据"

    ```bash
    curl -X PATCH http://localhost:8081/api/namespaces/calculator/metadata \
      -H "Content-Type: application/json" \
      -d '{"defer": true}'
    ```

    响应：
    ```json
    {
      "success": true,
      "message": "Metadata updated for namespace 'calculator'",
      "tools_updated": 3,
      "updated": {"defer": true}
    }
    ```
