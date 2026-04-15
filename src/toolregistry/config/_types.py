"""Typed dataclasses for declarative tool configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "ConfigError",
    "AuthConfig",
    "PythonSource",
    "MCPSource",
    "OpenAPISource",
    "ToolSource",
    "ToolConfig",
]


class ConfigError(ValueError):
    """Raised when a tool configuration file is semantically invalid.

    Syntax errors from the underlying parser (JSONCDecodeError, YAMLError)
    propagate unchanged.  ConfigError covers schema-level issues: unknown
    tool type, missing required fields, unresolvable env vars, etc.
    """


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration for an OpenAPI tool source.

    Attributes:
        type: Auth mechanism.  ``"bearer"`` adds an
            ``Authorization: Bearer <token>`` header.  ``"header"`` sends
            a custom header whose name is given by *header_name*.
        token: Resolved token value (from *token_env* or a literal).
        token_env: Name of the environment variable the token was
            resolved from.  Retained for diagnostics.
        header_name: Custom header name (used when *type* is ``"header"``).
    """

    type: Literal["bearer", "header"] = "bearer"
    token: str | None = None
    token_env: str | None = None
    header_name: str = "Authorization"


@dataclass(frozen=True)
class PythonSource:
    """A tool source backed by a Python class or module.

    Exactly one of *class_path* or *module_path* must be set.

    * *class_path*: consumer imports the module, gets the class, and calls
      ``registry.register_from_class()``.
    * *module_path*: consumer imports the module and registers every
      public callable it finds.

    Attributes:
        class_path: Fully-qualified dotted class path
            (e.g. ``"toolregistry_hub.calculator.Calculator"``).
        module_path: Fully-qualified dotted module path
            (e.g. ``"my_package.tools"``).
        namespace: Optional namespace passed to the registration call.
        enabled: Per-source enabled flag.
    """

    class_path: str | None = None
    module_path: str | None = None
    namespace: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.class_path and not self.module_path:
            raise ConfigError(
                "PythonSource requires at least one of 'class_path' or 'module_path'."
            )
        if self.class_path and self.module_path:
            raise ConfigError(
                "PythonSource accepts only one of 'class_path' or 'module_path', not both."
            )


@dataclass(frozen=True)
class MCPSource:
    """A tool source backed by an MCP server.

    For *stdio* transport, *command* is required and *env* is optional.
    For *sse* or *streamable-http* transport, *url* is required.

    The config file may use ``"http"`` as a shorthand for
    ``"streamable-http"``; the loader normalises it before constructing
    this object.

    Attributes:
        transport: MCP transport mechanism.
        namespace: Optional namespace passed to ``register_from_mcp()``.
        enabled: Per-source enabled flag.
        command: Command + args for stdio
            (e.g. ``["python", "-m", "server"]``).
        env: Extra environment variables for the stdio subprocess.
        url: Server URL for *sse* or *streamable-http* transport.
        headers: Extra HTTP headers for network transports.
        persistent: Whether to keep the MCP connection alive.
    """

    transport: Literal["stdio", "sse", "streamable-http"]
    namespace: str | None = None
    enabled: bool = True
    command: tuple[str, ...] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    persistent: bool = True


@dataclass(frozen=True)
class OpenAPISource:
    """A tool source backed by an OpenAPI endpoint.

    Attributes:
        url: URL to the OpenAPI spec (JSON or YAML).
        namespace: Optional namespace passed to
            ``register_from_openapi()``.
        enabled: Per-source enabled flag.
        auth: Optional authentication configuration.
        base_url: Override the ``servers[0].url`` from the spec.
    """

    url: str
    namespace: str | None = None
    enabled: bool = True
    auth: AuthConfig | None = None
    base_url: str | None = None


ToolSource = PythonSource | MCPSource | OpenAPISource
"""Discriminated union of all supported tool source types."""


@dataclass(frozen=True)
class ToolConfig:
    """Top-level configuration parsed from a JSONC or YAML file.

    Attributes:
        mode: Filtering strategy.  ``"denylist"`` enables everything
            except namespaces listed in *disabled*.  ``"allowlist"``
            enables only namespaces listed in *enabled*.
        disabled: Namespace patterns to disable (denylist mode).
        enabled: Namespace patterns to enable (allowlist mode).
        tools: Ordered sequence of tool source declarations.
        source: Filesystem path of the config file (for diagnostics).
    """

    mode: Literal["denylist", "allowlist"] = "denylist"
    disabled: tuple[str, ...] = ()
    enabled: tuple[str, ...] = ()
    tools: tuple[ToolSource, ...] = ()
    source: str = ""
