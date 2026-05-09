# 迁移指南

本指南涵盖 ToolRegistry 主要版本之间的破坏性变更和迁移步骤。

## 0.8.x → 下一版本

### `HttpxClientConfig` 重命名为 `HttpClientConfig`

`HttpxClientConfig` 类已重命名为 `HttpClientConfig`，以反映核心库不再依赖 httpx。旧名称保留为弃用别名。

**之前：**

```python
from toolregistry.integrations.openapi import HttpxClientConfig
client_config = HttpxClientConfig(base_url="http://localhost:8000")
```

**之后：**

```python
from toolregistry.integrations.openapi import HttpClientConfig
client_config = HttpClientConfig(base_url="http://localhost:8000")
```

旧的导入方式仍然有效，但会发出 `DeprecationWarning`。请尽快更新。

### httpx 移至可选依赖

`httpx` 不再是核心依赖，已移至 `[mcp]` 可选依赖组。如果使用 MCP 集成，请安装：

```bash
pip install toolregistry[mcp]
```

核心 OpenAPI 功能现在使用内置的零依赖 HTTP 客户端。

---

## 0.7.x → 0.8.0

### 集成包移至 `integrations/` 下

所有集成子包（`mcp`、`openapi`、`langchain`、`native`）已移至新的 `integrations/` 父包下。随着集成数量的增长，这提供了更清晰的项目结构。

**之前（0.7.x）：**

```python
from toolregistry.mcp import MCPClient
from toolregistry.openapi import OpenAPIIntegration
from toolregistry.langchain import LangChainIntegration
from toolregistry.native import NativeIntegration
```

**之后（0.8.0）：**

```python
from toolregistry.integrations.mcp import MCPClient
from toolregistry.integrations.openapi import OpenAPIIntegration
from toolregistry.integrations.langchain import LangChainIntegration
from toolregistry.integrations.native import NativeIntegration
```

**导入路径对照：**

| 旧路径（已弃用） | 新的规范路径 |
|---|---|
| `toolregistry.mcp` | `toolregistry.integrations.mcp` |
| `toolregistry.openapi` | `toolregistry.integrations.openapi` |
| `toolregistry.langchain` | `toolregistry.integrations.langchain` |
| `toolregistry.native` | `toolregistry.integrations.native` |

**向后兼容：** 旧导入路径仍然有效，但会发出 `DeprecationWarning`。它们将在未来版本中移除。请尽早更新你的导入路径。

```python
# 这在 0.8.0 中仍然有效，但会打印 DeprecationWarning：
from toolregistry.mcp import MCPClient
# DeprecationWarning: Importing from 'toolregistry.mcp' is deprecated.
# Use 'toolregistry.integrations.mcp' instead.
```

**公开 API 不变：** `ToolRegistry` 的便捷方法——`register_from_mcp()`、`register_from_openapi()`、`register_from_langchain()` 和 `register_from_native()`——继续正常工作，无需代码修改。

---

## 0.6.x → 0.7.0

### 执行器后端架构

单体 `Executor` 类已被可插拔的后端系统替代。

**之前（0.6.x）：**

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
# parallel_mode 参数控制执行方式
results = registry.execute_tool_calls(tool_calls, parallel_mode="thread")
```

**之后（0.7.0）：**

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
# 使用 execution_mode 参数或 set_default_execution_mode()
registry.set_default_execution_mode("thread")  # "thread" 或 "process"
results = registry.execute_tool_calls(tool_calls)

# 或单次调用覆盖
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
```

**变更对照：**

| 0.6.x | 0.7.0 | 说明 |
|-------|-------|------|
| `parallel_mode` 参数 | `execution_mode` 参数 | 重命名 |
| `Executor` 类 | `ThreadBackend` / `ProcessPoolBackend` | 可插拔后端 |
| 无取消支持 | `ExecutionContext` 与 `check_cancelled()` | 协作式取消 |
| 无单工具超时 | `ToolMetadata(timeout=5.0)` | 工具级超时控制 |

### 新依赖：llm-rosetta

`llm-rosetta>=0.2.6` 现在是核心依赖，驱动多格式 Schema 生成。无需操作——自动安装。

### 新权限系统

权限系统是增量式的，默认关闭。现有代码无需修改即可继续工作。如需启用：

```python
from toolregistry import ToolRegistry, ToolMetadata, ToolTag
from toolregistry.permissions import PermissionPolicy, ALLOW_READONLY, ASK_DESTRUCTIVE

# 用元数据分类工具
registry.register(tool, metadata=ToolMetadata(tags=[ToolTag.READ_ONLY]))

# 设置权限策略
policy = PermissionPolicy(rules=[ALLOW_READONLY, ASK_DESTRUCTIVE])
registry.set_permission_policy(policy)
```

### 多格式 Schema 支持

`get_schemas()` 现在除了现有的 OpenAI 格式外，还接受 `api_format` 值 `"anthropic"` 和 `"gemini"`。

```python
# 新格式
schemas = registry.get_schemas(api_format="anthropic")
schemas = registry.get_schemas(api_format="gemini")

# 现有格式仍然有效
schemas = registry.get_schemas()  # 默认：OpenAI chat completion
schemas = registry.get_schemas(api_format="openai-response")
```

---

## 0.5.x → 0.6.0

### 要求 Python 3.10+

ToolRegistry 0.6.0 不再支持 Python 3.8 和 3.9。请将 Python 版本升级到 3.10 或更高。

```bash
# 检查 Python 版本
python --version

# 如果使用 conda
conda install python=3.11
```

### dill → cloudpickle

序列化依赖从 `dill` 更改为 `cloudpickle`。这是透明的——无需代码修改，但如果你在依赖中固定了 `dill`，可以移除它。

```diff
# pyproject.toml — 如果你固定了 dill
 dependencies = [
     "toolregistry>=0.6.0",
-    "dill>=0.4.0",
 ]
```

### 类型注解现代化

如果你继承了 ToolRegistry 内部类，注意类型注解现在使用 Python 3.10+ 语法：

```python
# 0.5.x 风格（在 3.10+ 中仍可用）
from typing import Optional, List, Dict
def func(x: Optional[str] = None) -> List[Dict[str, int]]: ...

# 0.6.x 风格
def func(x: str | None = None) -> list[dict[str, int]]: ...
```

---

## 0.4.x → 0.5.0

### `register_from_class()` MRO 默认值变更

`traverse_mro` 现在默认为 `True`，意味着父类继承的方法也会自动注册。

**之前（0.4.x）：** 只注册直接在类上定义的方法。

**之后（0.5.0）：** 父类（不包括 `object`）的方法也会被注册。

恢复旧行为：

```python
registry.register_from_class(MyClass, traverse_mro=False)
```

### Hub 包拆分

`toolregistry[hub]` 可选依赖已移除。作为独立包安装 hub 工具：

```diff
- pip install toolregistry[hub]
+ pip install toolregistry toolregistry-hub
```

当两个包都安装时，导入路径 `from toolregistry.hub import ...` 仍然有效。

### MCP SDK 变更

MCP 依赖从 `fastmcp` 更改为官方 `mcp` SDK：

```diff
- pip install toolregistry[mcp]  # 安装 fastmcp
+ pip install toolregistry[mcp]  # 现在安装 mcp>=1.0.0
```

无需代码修改——`register_from_mcp()` API 保持不变。传输配置现在支持所有四种传输类型：stdio、SSE、streamable-http 和 websocket。
