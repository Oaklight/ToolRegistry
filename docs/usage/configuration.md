---
title: 声明式配置
summary: 通过 JSONC 或 YAML 配置文件加载工具源
description: 在配置文件中定义 Python 类、MCP 服务器和 OpenAPI 端点，并将其解析为类型化对象以进行工具注册。
---

# 声明式配置

`toolregistry.config` 模块允许你在 JSONC 或 YAML 文件中定义工具源，并将其解析为类型化的 Python 对象。这将**加载什么工具**与**如何注册**解耦。

## 快速开始

```python
from toolregistry.config import load_config

config = load_config("tools.yaml")

for source in config.tools:
    print(source)
```

## 配置文件格式

支持 JSONC（`.json`、`.jsonc`）和 YAML（`.yaml`、`.yml`）两种格式，根据文件扩展名自动检测。

### YAML 示例

```yaml
mode: denylist
disabled:
  - filesystem

tools:
  # Python 类
  - type: python
    class: toolregistry_hub.calculator.Calculator
    namespace: calculator

  # Python 模块（所有公开函数）
  - type: python
    module: my_package.tools
    namespace: custom

  # OpenAPI 端点
  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: external_api
    auth:
      type: bearer
      token_env: EXTERNAL_API_TOKEN

  # MCP 服务器（stdio）
  - type: mcp
    transport: stdio
    command: ["python", "-m", "mcp_server"]
    namespace: mcp_tools
    env:
      DEBUG: "1"

  # MCP 服务器（SSE）
  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    namespace: remote_mcp

  # MCP 服务器（streamable-http，别名 "http"）
  - type: mcp
    transport: http
    url: http://localhost:8080/mcp
    namespace: remote_mcp2
```

### JSONC 示例

```jsonc
{
  "mode": "denylist",
  "disabled": ["filesystem"],
  "tools": [
    {
      "type": "python",
      "class": "toolregistry_hub.calculator.Calculator",
      "namespace": "calculator"
    },
    {
      // 通过 SSE 连接的 MCP 服务器
      "type": "mcp",
      "transport": "sse",
      "url": "http://localhost:8080/sse",
      "namespace": "remote_mcp"
    }
  ]
}
```

## 工具源类型

### `python` — Python 类或模块

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | `"python"` | 是 | 源类型标识 |
| `class` | string | `class`/`module` 二选一 | 完整的类路径（如 `"pkg.Calculator"`） |
| `module` | string | `class`/`module` 二选一 | 完整的模块路径（如 `"pkg.tools"`） |
| `namespace` | string | 否 | 注册工具的命名空间 |
| `enabled` | bool | 否 | 按源启用/禁用（默认：`true`） |

指定 `class` 时，消费者调用 `register_from_class()`。指定 `module` 时，消费者注册模块中所有公开的可调用对象。

!!! note "旧版格式"
    旧版格式 `{"module": "pkg", "class": "Cls"}`（不含 `type` 字段）仍然支持。类型自动推断为 `"python"`，`class_path` 合并为 `"pkg.Cls"`。

### `mcp` — MCP 服务器

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | `"mcp"` | 是 | 源类型标识 |
| `transport` | string | 是 | `"stdio"`、`"sse"`、`"streamable-http"` 或 `"http"` |
| `command` | string 或 list | 仅 stdio | 启动服务器的命令 |
| `url` | string | 仅 sse/http | 服务器 URL |
| `env` | dict | 否 | stdio 子进程的环境变量 |
| `headers` | dict | 否 | 网络传输的 HTTP 头 |
| `namespace` | string | 否 | 注册工具的命名空间 |
| `persistent` | bool | 否 | 保持连接（默认：`true`） |
| `enabled` | bool | 否 | 按源启用/禁用（默认：`true`） |

!!! tip "`http` 别名"
    `transport: "http"` 是 `"streamable-http"` 的简写，内部会自动归一化。

### `openapi` — OpenAPI 端点

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | `"openapi"` | 是 | 源类型标识 |
| `url` | string | 是 | OpenAPI 规范的 URL |
| `namespace` | string | 否 | 注册工具的命名空间 |
| `auth` | object | 否 | 认证配置 |
| `base_url` | string | 否 | 覆盖规范中的 `servers[0].url` |
| `enabled` | bool | 否 | 按源启用/禁用（默认：`true`） |

#### 认证配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | `"bearer"` | `"bearer"` 或 `"header"` |
| `token` | string | — | 字面量 token 值 |
| `token_env` | string | — | 环境变量名（解析时读取） |
| `header_name` | string | `"Authorization"` | 自定义头名称（用于 `type: "header"`） |

如果同时指定了 `token_env` 和 `token`，`token_env` 优先。

## 过滤模式

### 拒绝列表（默认）

加载所有源，**排除**命名空间匹配 `disabled` 中模式的源：

```yaml
mode: denylist
disabled:
  - filesystem
  - web/dangerous
```

### 允许列表

**仅**加载命名空间匹配 `enabled` 中模式的源：

```yaml
mode: allowlist
enabled:
  - calculator
  - api
```

命名空间匹配是层级式的：模式 `"web"` 匹配 `"web/brave_search"`。

### 按源启用/禁用

可以通过 `enabled: false` 临时禁用单个源，不受过滤模式影响：

```yaml
tools:
  - type: python
    class: toolregistry_hub.calculator.Calculator
    namespace: calculator

  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    namespace: remote_mcp
    enabled: false  # 临时禁用

  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: external_api
    enabled: false  # 等 API 密钥配置好再启用
```

## 解析类型

`load_config()` 返回 `ToolConfig` 冻结 dataclass：

```python
@dataclass(frozen=True)
class ToolConfig:
    mode: Literal["denylist", "allowlist"]
    disabled: tuple[str, ...]
    enabled: tuple[str, ...]
    tools: tuple[ToolSource, ...]  # PythonSource | MCPSource | OpenAPISource
    source: str  # 配置文件路径
```

所有配置对象在解析后不可变。

## 错误处理

- **`FileNotFoundError`** — 配置文件不存在
- **`ConfigError`** — 语义验证错误（无效的模式、缺少必填字段、未知类型、未设置的环境变量）
- 解析器原生错误（`JSONCDecodeError`、`YAMLError`）用于语法问题
