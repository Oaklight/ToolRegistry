# 管理面板

管理面板提供了一个内置的 HTTP 服务器，用于管理和监控您的 ToolRegistry 实例。它同时提供 REST API 和可选的 Web 界面，支持实时工具管理。

## 概述

管理面板的设计遵循以下原则：

- **极简主义**：零外部依赖 - 仅使用 Python 标准库（`http.server`）
- **零配置**：开箱即用，提供合理的默认值
- **通用性**：兼容任何 HTTP 客户端或浏览器
- **安全性**：内置令牌认证，支持远程访问

### 主要功能

- 运行时启用/禁用工具和命名空间
- 查看工具 schema 和元数据
- 监控执行日志，支持过滤和统计
- 导出/导入注册表状态
- Web UI 可视化管理

### 界面截图

![管理面板 - 工具](assets/admin-panel-tools.png)
*工具选项卡：查看和管理所有已注册的工具，支持搜索、过滤和启用/禁用控制。*

![管理面板 - 日志](assets/admin-panel-logs.png)
*日志选项卡：监控执行历史，支持状态过滤和性能统计。*

![管理面板 - 命名空间](assets/admin-panel-namespaces.png)
*命名空间选项卡：管理工具分组，支持命名空间级别的启用/禁用控制。*

## 快速开始

### 基本用法

```python
from toolregistry import ToolRegistry

# 创建注册表并注册工具
registry = ToolRegistry()

@registry.register
def my_tool(x: int) -> int:
    """将输入乘以 2。"""
    return x * 2

# 启用管理面板
info = registry.enable_admin(port=8081)
print(f"管理面板: {info.url}")
```

### 访问 Web UI

启用后，打开浏览器访问打印的 URL（例如 `http://localhost:8081`）。Web UI 提供：

- 工具列表，带启用/禁用开关
- 命名空间管理
- 执行日志查看器
- 状态导出/导入功能

## 配置

`enable_admin()` 方法接受以下参数：

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `host` | `str` | `"127.0.0.1"` | 绑定的主机地址 |
| `port` | `int` | `8081` | 监听的端口号 |
| `serve_ui` | `bool` | `True` | 是否在根路径提供 Web UI |
| `remote` | `bool` | `False` | 是否允许远程连接 |
| `auth_token` | `str \| None` | `None` | API 访问的认证令牌 |

### 配置示例

=== "本地开发"

    ```python
    # 默认：仅本地访问，无需认证
    info = registry.enable_admin()
    print(f"管理面板: {info.url}")
    ```

=== "远程访问"

    ```python
    # 远程访问，自动生成令牌
    info = registry.enable_admin(remote=True)
    print(f"管理面板: {info.url}")
    print(f"令牌: {info.token}")  # 自动生成的安全令牌
    ```

=== "自定义令牌"

    ```python
    # 远程访问，使用自定义令牌
    info = registry.enable_admin(
        remote=True,
        auth_token="my-secure-token-123"
    )
    ```

=== "仅 API"

    ```python
    # 禁用 Web UI，仅提供 API
    info = registry.enable_admin(serve_ui=False)
    ```

### AdminInfo 对象

`enable_admin()` 方法返回一个 `AdminInfo` 对象，包含以下属性：

| 属性 | 类型 | 描述 |
|------|------|------|
| `host` | `str` | 服务器绑定的主机地址 |
| `port` | `int` | 服务器监听的端口号 |
| `url` | `str` | 访问管理面板的完整 URL |
| `token` | `str \| None` | 认证令牌（如果启用了认证） |

## 执行日志

管理面板与 ToolRegistry 的执行日志功能集成，提供工具使用的详细洞察。

### 启用执行日志

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# 启用日志，自定义缓冲区大小
log = registry.enable_logging(max_entries=1000)

# 注册并使用工具...
@registry.register
def calculator_add(a: int, b: int) -> int:
    return a + b

# 启用管理面板以查看日志
info = registry.enable_admin()
```

### 日志条目结构

每个执行日志条目包含：

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | `str` | 唯一标识符（UUID） |
| `tool_name` | `str` | 执行的工具名称 |
| `timestamp` | `datetime` | 执行发生的时间 |
| `status` | `ExecutionStatus` | `success`、`error` 或 `disabled` |
| `duration_ms` | `float` | 执行耗时（毫秒） |
| `arguments` | `dict` | 传递给工具的输入参数 |
| `result` | `Any` | 执行结果（成功执行时） |
| `error` | `str \| None` | 错误信息（失败执行时） |
| `metadata` | `dict` | 附加元数据 |

### 编程方式查询日志

```python
# 获取执行日志实例
log = registry.get_execution_log()

if log:
    # 获取最近的条目
    entries = log.get_entries(limit=10)
    
    # 按工具名称过滤
    calc_entries = log.get_entries(tool_name="calculator_add")
    
    # 按状态过滤
    from toolregistry.admin import ExecutionStatus
    errors = log.get_entries(status=ExecutionStatus.ERROR)
    
    # 获取统计信息
    stats = log.get_stats()
    print(f"总执行次数: {stats['total_entries']}")
    print(f"平均耗时: {stats['avg_duration_ms']:.2f}ms")
```

## REST API 参考

管理面板提供 RESTful API 用于编程访问。

### 认证

当启用认证时（远程模式或自定义令牌），需要在 `Authorization` 头中包含令牌：

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8081/api/tools
```

### API 端点

#### 工具

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/tools` | 列出所有工具及状态 |
| `GET` | `/api/tools/{name}` | 获取单个工具详情 |
| `POST` | `/api/tools/{name}/enable` | 启用工具 |
| `POST` | `/api/tools/{name}/disable` | 禁用工具 |

#### 命名空间

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/namespaces` | 列出所有命名空间 |
| `POST` | `/api/namespaces/{ns}/enable` | 启用命名空间中的所有工具 |
| `POST` | `/api/namespaces/{ns}/disable` | 禁用命名空间中的所有工具 |

#### 执行日志

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/logs` | 获取执行日志 |
| `GET` | `/api/logs/stats` | 获取执行统计 |
| `DELETE` | `/api/logs` | 清除所有日志 |

#### 状态管理

| 方法 | 端点 | 描述 |
|------|------|------|
| `GET` | `/api/state` | 导出当前状态 |
| `POST` | `/api/state` | 导入/恢复状态 |

### API 示例

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

## Web UI 指南

内置的 Web UI 提供了管理 ToolRegistry 的可视化界面。

### 界面概览

Web UI 分为几个部分：

1. **工具面板**：列出所有已注册的工具，带启用/禁用开关
2. **命名空间面板**：显示命名空间，支持批量启用/禁用
3. **日志面板**：显示执行历史，支持过滤选项
4. **状态面板**：提供导出/导入功能

### 工具管理

- 点击工具旁边的开关来启用/禁用
- 禁用的工具会显示原因（如果提供）
- 点击工具名称查看完整 schema

### 命名空间管理

- 一键启用/禁用命名空间中的所有工具
- 查看每个命名空间的工具数量
- 查看启用/禁用分布

### 执行日志查看器

- 按工具名称或状态过滤日志
- 查看执行详情，包括参数和结果
- 需要时清除日志
- 查看聚合统计

### 状态导入/导出

- 将当前禁用状态导出为 JSON
- 导入之前导出的状态
- 适用于备份/恢复场景

## 安全考虑

### 本地访问 vs 远程访问

| 模式 | 绑定地址 | 认证 | 使用场景 |
|------|----------|------|----------|
| 本地（默认） | `127.0.0.1` | 可选 | 开发、测试 |
| 远程 | `0.0.0.0` | 必需 | 生产、多用户 |

### 令牌认证

当 `remote=True` 或提供了 `auth_token` 时：

- 所有 API 请求都需要 `Authorization: Bearer <token>` 头
- 令牌使用常量时间比较，防止时序攻击
- 自动生成的令牌是 32 字符的十六进制字符串（128 位熵）

### 最佳实践

!!! warning "生产部署"
    对于生产部署，请始终：
    
    1. 使用 `remote=True` 并设置强自定义令牌
    2. 部署在反向代理（nginx、Caddy）后面，启用 HTTPS
    3. 使用防火墙规则限制访问
    4. 如果不需要，考虑禁用 Web UI（`serve_ui=False`）

!!! tip "令牌管理"
    - 安全存储令牌（环境变量、密钥管理器）
    - 定期轮换令牌
    - 不同环境使用不同令牌

## 示例

### 带日志的基本用法

```python
from toolregistry import ToolRegistry

# 创建注册表
registry = ToolRegistry()

# 注册工具
@registry.register
def greet(name: str) -> str:
    """按名称问候某人。"""
    return f"你好，{name}！"

@registry.register
def calculate(a: int, b: int, op: str = "add") -> int:
    """执行计算。"""
    if op == "add":
        return a + b
    elif op == "subtract":
        return a - b
    else:
        raise ValueError(f"未知操作: {op}")

# 启用执行日志
registry.enable_logging(max_entries=1000)

# 启用管理面板
info = registry.enable_admin(port=8081)
print(f"管理面板: {info.url}")

# 保持脚本运行
import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    registry.disable_admin()
```

### 远程访问配置

```python
from toolregistry import ToolRegistry
import os

registry = ToolRegistry()

# ... 注册工具 ...

# 从环境获取令牌或生成
token = os.environ.get("ADMIN_TOKEN")

# 启用远程访问
info = registry.enable_admin(
    port=8081,
    remote=True,
    auth_token=token  # None = 自动生成
)

print(f"管理面板: {info.url}")
if info.token:
    print(f"令牌: {info.token}")
```

### 与 FastAPI 集成

```python
from fastapi import FastAPI
from toolregistry import ToolRegistry
from contextlib import asynccontextmanager

registry = ToolRegistry()

# 注册工具
@registry.register
def my_tool(x: int) -> int:
    return x * 2

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时启用管理面板
    info = registry.enable_admin(port=8082)
    print(f"管理面板: {info.url}")
    yield
    # 关闭时禁用
    registry.disable_admin()

app = FastAPI(lifespan=lifespan)

@app.post("/execute")
async def execute_tool(name: str, args: dict):
    tool = registry.get_callable(name)
    if tool:
        return {"result": tool(**args)}
    return {"error": "工具未找到"}
```

### 执行日志分析

```python
from toolregistry import ToolRegistry
from toolregistry.admin import ExecutionStatus

registry = ToolRegistry()
log = registry.enable_logging()

# ... 执行工具 ...

# 分析执行模式
stats = log.get_stats()

print(f"总执行次数: {stats['total_entries']}")
print(f"成功率: {stats['by_status'].get('success', 0) / stats['total_entries'] * 100:.1f}%")
print(f"平均耗时: {stats['avg_duration_ms']:.2f}ms")

# 查找执行最多的工具
by_tool = stats['by_tool']
print("\n按工具统计执行次数:")
for tool_name, count in sorted(by_tool.items(), key=lambda x: -x[1]):
    print(f"  {tool_name}: {count}")

# 获取最近的错误
errors = log.get_entries(status=ExecutionStatus.ERROR, limit=5)
for entry in errors:
    print(f"{entry.tool_name} 中的错误: {entry.error}")
```

## 停止管理面板

```python
# 停止管理面板
registry.disable_admin()

# 检查是否运行中
info = registry.get_admin_info()
if info:
    print(f"仍在运行: {info.url}")
else:
    print("管理面板已停止")
```
