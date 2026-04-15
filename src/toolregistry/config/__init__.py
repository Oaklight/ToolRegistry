"""Declarative tool configuration loader.

Parse JSONC or YAML config files into typed Python objects describing
tool sources (Python classes/modules, OpenAPI endpoints, MCP servers)
and filtering rules (denylist/allowlist by namespace).

Example::

    from toolregistry.config import load_config

    config = load_config("tools.yaml")
    for source in config.tools:
        print(source)
"""

from ._loader import load_config
from ._types import (
    AuthConfig,
    ConfigError,
    MCPSource,
    OpenAPISource,
    PythonSource,
    ToolConfig,
    ToolSource,
)

__all__ = [
    "load_config",
    "AuthConfig",
    "ConfigError",
    "MCPSource",
    "OpenAPISource",
    "PythonSource",
    "ToolConfig",
    "ToolSource",
]
