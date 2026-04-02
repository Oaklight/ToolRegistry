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

![管理面板 - 工具](../assets/admin-panel-tools.png)
*工具选项卡：查看和管理所有已注册的工具，支持搜索、过滤和启用/禁用控制。*

![管理面板 - 日志](../assets/admin-panel-logs.png)
*日志选项卡：监控执行历史，支持状态过滤和性能统计。*

![管理面板 - 命名空间](../assets/admin-panel-namespaces.png)
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
