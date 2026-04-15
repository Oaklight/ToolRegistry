"""Config file loading, parsing, and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, cast

from ._types import (
    AuthConfig,
    ConfigError,
    MCPSource,
    OpenAPISource,
    PythonSource,
    ToolConfig,
    ToolSource,
)

__all__ = ["load_config"]

_TRANSPORT_ALIASES: dict[str, str] = {
    "http": "streamable-http",
}


def load_config(path: str | Path) -> ToolConfig:
    """Load and parse a tool configuration file.

    Supports JSONC (``.json``, ``.jsonc``) and YAML (``.yaml``, ``.yml``)
    formats.  The file format is auto-detected from the extension.

    Args:
        path: Path to the configuration file.

    Returns:
        Parsed and validated ``ToolConfig``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ConfigError: If the content is semantically invalid.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Config file not found: {p}")
    fmt = _detect_format(p)
    data = _parse_file(p, fmt)
    return _build_config(data, source=str(p))


# --- format detection -------------------------------------------------------


def _detect_format(path: Path) -> Literal["jsonc", "yaml"]:
    suffix = path.suffix.lower()
    if suffix in (".json", ".jsonc"):
        return "jsonc"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    raise ConfigError(
        f"Unsupported config file extension '{suffix}'. "
        "Expected .json, .jsonc, .yaml, or .yml."
    )


# --- raw parsing -------------------------------------------------------------


def _parse_file(path: Path, fmt: Literal["jsonc", "yaml"]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if fmt == "jsonc":
        from .._vendor.jsonc import loads as jsonc_loads

        data = jsonc_loads(text)
    else:
        from .._vendor.yaml import load as yaml_load

        data = yaml_load(text)

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file must contain a mapping at the top level, "
            f"got {type(data).__name__}."
        )
    return data


# --- config building ---------------------------------------------------------


def _build_config(data: dict[str, Any], source: str) -> ToolConfig:
    mode = data.get("mode", "denylist")
    if mode not in ("denylist", "allowlist"):
        raise ConfigError(f"Invalid mode '{mode}'. Must be 'denylist' or 'allowlist'.")

    disabled = _validate_string_list(data, "disabled")
    enabled_list = _validate_string_list(data, "enabled")

    raw_tools = data.get("tools", [])
    if not isinstance(raw_tools, list):
        raise ConfigError(f"'tools' must be a list, got {type(raw_tools).__name__}.")

    tools: list[ToolSource] = []
    for i, entry in enumerate(raw_tools):
        if not isinstance(entry, dict):
            raise ConfigError(
                f"Tool entry at index {i} must be a mapping, "
                f"got {type(entry).__name__}."
            )
        tools.append(_build_tool_source(cast(dict[str, Any], entry), i))

    return ToolConfig(
        mode=mode,
        disabled=tuple(disabled),
        enabled=tuple(enabled_list),
        tools=tuple(tools),
        source=source,
    )


def _validate_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ConfigError(f"'{key}' must be a list, got {type(value).__name__}.")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise ConfigError(
                f"'{key}[{i}]' must be a string, got {type(item).__name__}."
            )
    return value


# --- tool source dispatch ----------------------------------------------------


def _build_tool_source(entry: dict[str, Any], index: int) -> ToolSource:
    tool_type = _infer_type(entry, index)
    namespace = entry.get("namespace")
    enabled = entry.get("enabled", True)

    if tool_type == "python":
        return _build_python_source(entry, index, namespace, enabled)
    if tool_type == "mcp":
        return _build_mcp_source(entry, index, namespace, enabled)
    if tool_type == "openapi":
        return _build_openapi_source(entry, index, namespace, enabled)
    raise ConfigError(f"Tool entry at index {index}: unknown type '{tool_type}'.")


def _infer_type(entry: dict[str, Any], index: int) -> str:
    if "type" in entry:
        return entry["type"]
    # Backward compat: class/module keys imply "python"
    if "class" in entry or "module" in entry:
        return "python"
    raise ConfigError(
        f"Tool entry at index {index}: missing 'type' field "
        "and cannot infer type from keys."
    )


# --- python source -----------------------------------------------------------


def _build_python_source(
    entry: dict[str, Any],
    index: int,
    namespace: str | None,
    enabled: bool,
) -> PythonSource:
    class_val = entry.get("class", "")
    module_val = entry.get("module", "")

    class_path: str | None = None
    module_path: str | None = None

    if class_val and module_val:
        # Legacy: {"module": "pkg", "class": "Cls"} → class_path = "pkg.Cls"
        if "." not in class_val:
            class_path = f"{module_val}.{class_val}"
        else:
            class_path = class_val
    elif class_val:
        class_path = class_val
    elif module_val:
        module_path = module_val
    else:
        raise ConfigError(
            f"Tool entry at index {index} (type=python): requires 'class' or 'module'."
        )

    return PythonSource(
        class_path=class_path,
        module_path=module_path,
        namespace=namespace,
        enabled=enabled,
    )


# --- mcp source --------------------------------------------------------------


def _build_mcp_source(
    entry: dict[str, Any],
    index: int,
    namespace: str | None,
    enabled: bool,
) -> MCPSource:
    raw_transport = entry.get("transport", "")
    transport = _TRANSPORT_ALIASES.get(raw_transport, raw_transport)

    if transport not in ("stdio", "sse", "streamable-http"):
        raise ConfigError(
            f"Tool entry at index {index} (type=mcp): "
            f"transport must be 'stdio', 'sse', 'streamable-http', or 'http', "
            f"got '{raw_transport}'."
        )

    if transport == "stdio":
        command = entry.get("command")
        if not command:
            raise ConfigError(
                f"Tool entry at index {index} (type=mcp, transport=stdio): "
                "'command' is required."
            )
        if isinstance(command, str):
            command = [command]
        return MCPSource(
            transport=transport,
            namespace=namespace,
            enabled=enabled,
            command=tuple(command),
            env=entry.get("env"),
            persistent=entry.get("persistent", True),
        )

    # sse or streamable-http
    url = entry.get("url")
    if not url:
        raise ConfigError(
            f"Tool entry at index {index} (type=mcp, transport={raw_transport}): "
            "'url' is required."
        )
    return MCPSource(
        transport=transport,
        namespace=namespace,
        enabled=enabled,
        url=url,
        headers=entry.get("headers"),
        persistent=entry.get("persistent", True),
    )


# --- openapi source ----------------------------------------------------------


def _build_openapi_source(
    entry: dict[str, Any],
    index: int,
    namespace: str | None,
    enabled: bool,
) -> OpenAPISource:
    url = entry.get("url")
    if not url:
        raise ConfigError(
            f"Tool entry at index {index} (type=openapi): 'url' is required."
        )

    auth = None
    auth_data = entry.get("auth")
    if auth_data is not None:
        if not isinstance(auth_data, dict):
            raise ConfigError(
                f"Tool entry at index {index} (type=openapi): 'auth' must be a mapping."
            )
        auth = _build_auth(auth_data, index)

    return OpenAPISource(
        url=url,
        namespace=namespace,
        enabled=enabled,
        auth=auth,
        base_url=entry.get("base_url"),
    )


# --- auth ---------------------------------------------------------------------


def _build_auth(data: dict[str, Any], tool_index: int) -> AuthConfig:
    auth_type = data.get("type", "bearer")
    token: str | None = None
    token_env = data.get("token_env")

    if token_env:
        token = _resolve_env(token_env, tool_index)
    elif "token" in data:
        token = data["token"]

    return AuthConfig(
        type=auth_type,
        token=token,
        token_env=token_env,
        header_name=data.get("header_name", "Authorization"),
    )


def _resolve_env(var_name: str, tool_index: int) -> str:
    value = os.environ.get(var_name)
    if value is None:
        raise ConfigError(
            f"Tool entry at index {tool_index}: environment variable "
            f"'{var_name}' is not set (referenced by token_env)."
        )
    return value
