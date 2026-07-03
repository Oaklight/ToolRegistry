# 迁移指南

本指南涵盖 ToolRegistry 主要版本之间的破坏性变更和迁移步骤。

## 0.12.x → 0.13.0

### 新增：程序化工具调用 (PTC)

LLM 现在可以编写 Python 代码调用已注册的工具：

```python
registry.enable_code_execution()  # 注册 "code_execution" 工具
# pip install toolregistry[ptc]
```

详见[程序化工具调用指南](usage/programmatic_tool_calling.md)。

### 新增：`registry.invoke()`

单工具执行，走完整 pipeline（权限、日志）：

```python
result = registry.invoke("add", {"a": 1, "b": 2})
```

需要权限检查和日志时，替代直接调用 `tool.run()`。

### 新增：调用追踪

执行日志条目现在有 `invocation_id` 字段：

```python
registry.enable_logging()
registry.invoke("add", {"a": 1, "b": 2})

log = registry.get_execution_log()
entries = log.get_entries(invocation_id="tr_sig_...")
```

### `runtimes/` 包变更

`CodeResult` 和 `CodeRuntime` 已从 `toolregistry.runtimes` 移除，现由 [`codecell`](https://pypi.org/project/codecell/) 包提供。

**之前：**
```python
from toolregistry.runtimes import CodeResult, CodeRuntime  # ← ImportError
```

**之后：**
```python
from codecell import CodeResult, SubprocessRuntime  # pip install codecell
```

`ToolProjection`、`DirectProjection`、`validate_namespace()` 和 `namespace_to_callables()` 仍在 `toolregistry.runtimes` 中。

## 0.11.x → 0.12.0

### `Tool.run()` / `arun()` 不再吞没异常

`Tool.run()` 和 `arun()` 之前会捕获异常并返回类似 `"Error executing tool_name: ..."` 的错误字符串。从 v0.12.0 起，它们直接抛出异常——与之前 `run_raw()`/`arun_raw()` 的行为一致。

`run_raw()` 和 `arun_raw()` 现在是 `run()` / `arun()` 的废弃别名。

**之前（v0.10–v0.11）：**

```python
tool = registry.get_tool("divide")
result = tool.run({"a": 10, "b": 0})
# result == "Error executing divide: division by zero"  ← 不抛异常
```

**之后（v0.12+）：**

```python
tool = registry.get_tool("divide")
try:
    result = tool.run({"a": 10, "b": 0})
except ZeroDivisionError:
    print("不能除以零！")

# run_raw() 仍可用但会发出 DeprecationWarning
# 直接使用 run() 即可。
```

### `Tool.callable` 现在是 `BaseToolWrapper`

原生工具的 `Tool.callable` 不再是裸 Python 函数，而是 `BaseToolWrapper` 子类。如需访问原始未包装的函数，使用新的 `tool.fn` 属性。

**之前：**

```python
tool = Tool.from_function(my_func)
assert tool.callable == my_func            # 可以
sig = inspect.signature(tool.callable)     # 拿到真实签名
```

**之后：**

```python
tool = Tool.from_function(my_func)
assert tool.fn == my_func                  # 使用 .fn
sig = inspect.signature(tool.fn)           # 使用 .fn 做内省
```

### Sync/Async 透明调用

所有工具现在都支持 `run()` 和 `arun()`，无论底层函数是同步还是异步：

```python
# 同步工具
sync_tool = Tool.from_function(sync_add)
sync_tool.run({"a": 1, "b": 2})           # 直接调用
await sync_tool.arun({"a": 1, "b": 2})    # 通过 asyncio.to_thread

# 异步工具
async_tool = Tool.from_function(async_add)
async_tool.run({"a": 1, "b": 2})          # 通过 asyncio.run
await async_tool.arun({"a": 1, "b": 2})   # 直接 await
```

## 0.8.x → 0.10.0

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
