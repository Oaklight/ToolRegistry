"""Typed dataclasses for declarative tool configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

__all__ = [
    "ConfigError",
    "AuthConfig",
    "ProfileConfig",
    "PythonSource",
    "MCPSource",
    "OpenAPISource",
    "ToolMetadataOverride",
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict.

        Omits fields with default values for cleaner output.
        The ``token`` field is excluded to avoid leaking secrets;
        only ``token_env`` is preserved.
        """
        d: dict[str, Any] = {}
        if self.type != "bearer":
            d["type"] = self.type
        if self.token_env:
            d["token_env"] = self.token_env
        if self.type == "header" and self.header_name != "Authorization":
            d["header_name"] = self.header_name
        return d


@dataclass(frozen=True)
class ProfileConfig:
    """Per-profile filter overrides declared in the config file.

    When a profile name is found in ``ToolConfig.profiles``, these
    settings take precedence over the built-in tag-based defaults.

    Attributes:
        disable_tags: Tag names whose tools should be disabled.
            Replaces the built-in default tag set for this profile.
            When absent, the built-in default is used.
        enable: Namespace patterns to force-enable after tag filtering
            (highest priority — overrides tag-based disable).
        disable: Namespace patterns to force-disable after tag filtering
            (applied after ``enable``).
    """

    disable_tags: tuple[str, ...] = ()
    enable: tuple[str, ...] = ()
    disable: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict."""
        d: dict[str, Any] = {}
        if self.disable_tags:
            d["disable_tags"] = list(self.disable_tags)
        if self.enable:
            d["enable"] = list(self.enable)
        if self.disable:
            d["disable"] = list(self.disable)
        return d


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
        kwargs: Keyword arguments forwarded to the class constructor when
            *class_path* is used.  Allows passing configuration (e.g. API
            keys, base URLs) directly from the config file instead of
            requiring a pre-constructed instance.
    """

    class_path: str | None = None
    module_path: str | None = None
    namespace: str | None = None
    enabled: bool = True
    kwargs: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.class_path and not self.module_path:
            raise ConfigError(
                "PythonSource requires at least one of 'class_path' or 'module_path'."
            )
        if self.class_path and self.module_path:
            raise ConfigError(
                "PythonSource accepts only one of 'class_path' or 'module_path', not both."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict.

        Maps ``class_path`` back to the ``"class"`` key and
        ``module_path`` to ``"module"`` for config-file compatibility.
        Omits ``kwargs`` when empty.
        """
        d: dict[str, Any] = {"type": "python"}
        if self.class_path:
            d["class"] = self.class_path
        if self.module_path:
            d["module"] = self.module_path
        if self.namespace:
            d["namespace"] = self.namespace
        if not self.enabled:
            d["enabled"] = False
        if self.kwargs:
            d["kwargs"] = dict(self.kwargs)
        if self.tags:
            d["tags"] = list(self.tags)
        return d


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
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict.

        Omits fields with default values for cleaner output.
        """
        d: dict[str, Any] = {"type": "mcp", "transport": self.transport}
        if self.namespace:
            d["namespace"] = self.namespace
        if not self.enabled:
            d["enabled"] = False
        if self.command:
            d["command"] = list(self.command)
        if self.env:
            d["env"] = dict(self.env)
        if self.url:
            d["url"] = self.url
        if self.headers:
            d["headers"] = dict(self.headers)
        if not self.persistent:
            d["persistent"] = False
        if self.tags:
            d["tags"] = list(self.tags)
        return d


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
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict.

        Omits fields with default values for cleaner output.
        """
        d: dict[str, Any] = {"type": "openapi", "url": self.url}
        if self.namespace:
            d["namespace"] = self.namespace
        if not self.enabled:
            d["enabled"] = False
        if self.auth:
            d["auth"] = self.auth.to_dict()
        if self.base_url:
            d["base_url"] = self.base_url
        if self.tags:
            d["tags"] = list(self.tags)
        return d


ToolSource = PythonSource | MCPSource | OpenAPISource
"""Discriminated union of all supported tool source types."""


@dataclass(frozen=True)
class ToolMetadataOverride:
    """Per-tool metadata overrides declared in the config file.

    Maps to entries under the ``tool_metadata`` top-level key, keyed
    by exact tool name (e.g. ``"calculator-evaluate"``).

    Attributes:
        search_hint: Free-form keywords to boost BM25 discoverability
            and shorten the bullet description in ``discover_tools``.
        defer: Override whether this tool is deferred from the initial
            prompt.  ``None`` means no override (use the registered value).
    """

    search_hint: str = ""
    defer: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict.

        Omits fields with default/None values for cleaner output.
        """
        d: dict[str, Any] = {}
        if self.search_hint:
            d["search_hint"] = self.search_hint
        if self.defer is not None:
            d["defer"] = self.defer
        return d


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
        tool_metadata: Per-tool metadata overrides keyed by exact tool name.
            Applied after registration; supports ``search_hint`` and ``defer``.
    """

    mode: Literal["denylist", "allowlist"] = "denylist"
    disabled: tuple[str, ...] = ()
    enabled: tuple[str, ...] = ()
    tools: tuple[ToolSource, ...] = ()
    source: str = ""
    profiles: dict[str, ProfileConfig] = field(default_factory=dict)
    tool_metadata: dict[str, ToolMetadataOverride] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a config-file-compatible dict.

        Omits fields with default values for cleaner output.
        The ``source`` (file path) field is excluded as it is
        diagnostic metadata, not part of the config schema.
        """
        d: dict[str, Any] = {"mode": self.mode}
        if self.disabled:
            d["disabled"] = list(self.disabled)
        if self.enabled:
            d["enabled"] = list(self.enabled)
        if self.tools:
            d["tools"] = [t.to_dict() for t in self.tools]
        if self.profiles:
            d["profiles"] = {name: pc.to_dict() for name, pc in self.profiles.items()}
        if self.tool_metadata:
            d["tool_metadata"] = {
                name: override.to_dict()
                for name, override in self.tool_metadata.items()
                if override.to_dict()  # skip empty overrides
            }
        return d
