---
title: Declarative Configuration
summary: Load tool sources from JSONC or YAML config files
description: Define Python classes, MCP servers, and OpenAPI endpoints in a config file and parse them into typed objects for tool registration.
---

# Declarative Configuration

The `toolregistry.config` module lets you define tool sources in a JSONC or YAML file and parse them into typed Python objects. This decouples **what** tools to load from **how** they are registered.

## Quick Start

```python
from toolregistry.config import load_config

config = load_config("tools.yaml")

for source in config.tools:
    print(source)
```

## Config File Format

Both JSONC (`.json`, `.jsonc`) and YAML (`.yaml`, `.yml`) are supported. The format is auto-detected from the file extension.

### YAML Example

```yaml
mode: denylist
disabled:
  - filesystem

tools:
  # Python class
  - type: python
    class: toolregistry_hub.calculator.Calculator
    namespace: calculator

  # Python module (all public functions)
  - type: python
    module: my_package.tools
    namespace: custom

  # OpenAPI endpoint
  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: external_api
    auth:
      type: bearer
      token_env: EXTERNAL_API_TOKEN

  # MCP server (stdio)
  - type: mcp
    transport: stdio
    command: ["python", "-m", "mcp_server"]
    namespace: mcp_tools
    env:
      DEBUG: "1"

  # MCP server (SSE)
  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    namespace: remote_mcp

  # MCP server (streamable-http, alias "http")
  - type: mcp
    transport: http
    url: http://localhost:8080/mcp
    namespace: remote_mcp2
```

### JSONC Example

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
      // MCP server via SSE
      "type": "mcp",
      "transport": "sse",
      "url": "http://localhost:8080/sse",
      "namespace": "remote_mcp"
    }
  ]
}
```

## Tool Source Types

### `python` — Python Class or Module

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"python"` | Yes | Source type identifier |
| `class` | string | One of `class`/`module` | Fully-qualified class path (e.g. `"pkg.Calculator"`) |
| `module` | string | One of `class`/`module` | Fully-qualified module path (e.g. `"pkg.tools"`) |
| `namespace` | string | No | Namespace for registered tools |
| `enabled` | bool | No | Per-source enable/disable (default: `true`) |

When `class` is specified, the consumer calls `register_from_class()`. When `module` is specified, the consumer registers all public callables from the module.

!!! note "Legacy Format"
    The legacy format `{"module": "pkg", "class": "Cls"}` (without `type` field) is still supported. The type is inferred as `"python"` and `class_path` is combined as `"pkg.Cls"`.

### `mcp` — MCP Server

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"mcp"` | Yes | Source type identifier |
| `transport` | string | Yes | `"stdio"`, `"sse"`, `"streamable-http"`, or `"http"` |
| `command` | string or list | stdio only | Command to start the server |
| `url` | string | sse/http only | Server URL |
| `env` | dict | No | Environment variables for stdio subprocess |
| `headers` | dict | No | HTTP headers for network transports |
| `namespace` | string | No | Namespace for registered tools |
| `persistent` | bool | No | Keep connection alive (default: `true`) |
| `enabled` | bool | No | Per-source enable/disable (default: `true`) |

!!! tip "`http` Alias"
    `transport: "http"` is a shorthand for `"streamable-http"` and is normalized internally.

### `openapi` — OpenAPI Endpoint

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"openapi"` | Yes | Source type identifier |
| `url` | string | Yes | URL to the OpenAPI spec |
| `namespace` | string | No | Namespace for registered tools |
| `auth` | object | No | Authentication configuration |
| `base_url` | string | No | Override `servers[0].url` from spec |
| `enabled` | bool | No | Per-source enable/disable (default: `true`) |

#### Auth Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `"bearer"` | `"bearer"` or `"header"` |
| `token` | string | — | Literal token value |
| `token_env` | string | — | Environment variable name (resolved at parse time) |
| `header_name` | string | `"Authorization"` | Custom header name (for `type: "header"`) |

If both `token_env` and `token` are specified, `token_env` takes precedence.

## Filtering Modes

### Denylist (Default)

All sources are loaded **except** those whose namespace matches a pattern in `disabled`:

```yaml
mode: denylist
disabled:
  - filesystem
  - web/dangerous
```

### Allowlist

**Only** sources whose namespace matches a pattern in `enabled` are loaded:

```yaml
mode: allowlist
enabled:
  - calculator
  - api
```

Namespace matching is hierarchical: pattern `"web"` matches `"web/brave_search"`.

### Per-Source Enable/Disable

Individual sources can be temporarily disabled with `enabled: false`, regardless of the filtering mode:

```yaml
tools:
  - type: python
    class: toolregistry_hub.calculator.Calculator
    namespace: calculator

  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    namespace: remote_mcp
    enabled: false  # temporarily disabled

  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: external_api
    enabled: false  # skip until API key is configured
```

## Parsed Types

`load_config()` returns a `ToolConfig` frozen dataclass:

```python
@dataclass(frozen=True)
class ToolConfig:
    mode: Literal["denylist", "allowlist"]
    disabled: tuple[str, ...]
    enabled: tuple[str, ...]
    tools: tuple[ToolSource, ...]  # PythonSource | MCPSource | OpenAPISource
    source: str  # config file path
```

All config objects are immutable after parsing.

## Error Handling

- **`FileNotFoundError`** — config file does not exist
- **`ConfigError`** — semantic validation errors (invalid mode, missing required fields, unknown type, unset env var)
- Parser-native errors (`JSONCDecodeError`, `YAMLError`) propagate for syntax issues
