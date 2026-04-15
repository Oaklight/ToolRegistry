"""Tests for toolregistry.config — declarative tool configuration loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from toolregistry.config import (
    ConfigError,
    MCPSource,
    OpenAPISource,
    PythonSource,
    ToolConfig,
    load_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestFormatDetection:
    def test_json_extension(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.json", "{}")
        cfg = load_config(p)
        assert isinstance(cfg, ToolConfig)

    def test_jsonc_extension(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.jsonc", "{}")
        cfg = load_config(p)
        assert isinstance(cfg, ToolConfig)

    def test_yaml_extension(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "mode: denylist")
        cfg = load_config(p)
        assert cfg.mode == "denylist"

    def test_yml_extension(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yml", "mode: allowlist")
        cfg = load_config(p)
        assert cfg.mode == "allowlist"

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.toml", "")
        with pytest.raises(ConfigError, match="Unsupported config file extension"):
            load_config(p)

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# JSONC parsing
# ---------------------------------------------------------------------------


class TestJSONCParsing:
    def test_line_comments(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.jsonc",
            """\
{
  // This is a comment
  "mode": "denylist",
  "tools": []
}
""",
        )
        cfg = load_config(p)
        assert cfg.mode == "denylist"
        assert cfg.tools == ()

    def test_block_comments(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.jsonc",
            """\
{
  /* block comment */
  "mode": "allowlist",
  "enabled": ["math"]
}
""",
        )
        cfg = load_config(p)
        assert cfg.mode == "allowlist"
        assert cfg.enabled == ("math",)

    def test_trailing_commas(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.jsonc",
            """\
{
  "disabled": ["web", "fs",],
  "tools": [],
}
""",
        )
        cfg = load_config(p)
        assert cfg.disabled == ("web", "fs")


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------


class TestYAMLParsing:
    def test_basic_yaml(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
mode: denylist
disabled:
  - web
  - fs
tools: []
""",
        )
        cfg = load_config(p)
        assert cfg.mode == "denylist"
        assert cfg.disabled == ("web", "fs")
        assert cfg.tools == ()

    def test_yaml_with_comments(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
# Top-level comment
mode: allowlist
enabled:
  - math  # inline comment
""",
        )
        cfg = load_config(p)
        assert cfg.mode == "allowlist"
        assert cfg.enabled == ("math",)


# ---------------------------------------------------------------------------
# PythonSource
# ---------------------------------------------------------------------------


class TestPythonSource:
    def test_class_path_new_format(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: python
    class: toolregistry_hub.calculator.Calculator
    namespace: calc
""",
        )
        cfg = load_config(p)
        assert len(cfg.tools) == 1
        src = cfg.tools[0]
        assert isinstance(src, PythonSource)
        assert src.class_path == "toolregistry_hub.calculator.Calculator"
        assert src.module_path is None
        assert src.namespace == "calc"

    def test_module_path(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: python
    module: my_package.tools
    namespace: custom
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, PythonSource)
        assert src.module_path == "my_package.tools"
        assert src.class_path is None

    def test_legacy_module_class(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.jsonc",
            """\
{
  "tools": [
    {"module": "my_module", "class": "MyTool", "namespace": "ns"}
  ]
}
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, PythonSource)
        assert src.class_path == "my_module.MyTool"

    def test_legacy_module_only(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.jsonc",
            '{"tools": [{"module": "examples.tools", "namespace": "ex"}]}',
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, PythonSource)
        assert src.module_path == "examples.tools"
        assert src.class_path is None

    def test_missing_class_and_module(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: python
    namespace: oops
""",
        )
        with pytest.raises(ConfigError, match="requires 'class' or 'module'"):
            load_config(p)


# ---------------------------------------------------------------------------
# MCPSource
# ---------------------------------------------------------------------------


class TestMCPSource:
    def test_stdio(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: stdio
    command: ["python", "-m", "server"]
    env:
      KEY: value
    namespace: mcp_tools
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.transport == "stdio"
        assert src.command == ("python", "-m", "server")
        assert src.env == {"KEY": "value"}
        assert src.namespace == "mcp_tools"
        assert src.persistent is True

    def test_sse(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    namespace: remote
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.transport == "sse"
        assert src.url == "http://localhost:8080/sse"

    def test_http_alias(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: http
    url: http://localhost:8080/mcp
    namespace: remote2
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.transport == "streamable-http"
        assert src.url == "http://localhost:8080/mcp"

    def test_streamable_http(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: streamable-http
    url: http://localhost:8080/mcp
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.transport == "streamable-http"

    def test_stdio_string_command(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: stdio
    command: python
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.command == ("python",)

    def test_invalid_transport(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: grpc
    url: http://localhost:9090
""",
        )
        with pytest.raises(ConfigError, match="transport must be"):
            load_config(p)

    def test_stdio_missing_command(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: stdio
""",
        )
        with pytest.raises(ConfigError, match="'command' is required"):
            load_config(p)

    def test_sse_missing_url(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: sse
""",
        )
        with pytest.raises(ConfigError, match="'url' is required"):
            load_config(p)

    def test_persistent_false(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    persistent: false
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.persistent is False

    def test_headers(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    headers:
      X-Custom: value
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, MCPSource)
        assert src.headers == {"X-Custom": "value"}


# ---------------------------------------------------------------------------
# OpenAPISource
# ---------------------------------------------------------------------------


class TestOpenAPISource:
    def test_basic(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: api
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, OpenAPISource)
        assert src.url == "https://api.example.com/openapi.json"
        assert src.namespace == "api"
        assert src.auth is None

    def test_bearer_auth_with_token_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_API_TOKEN", "secret123")
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: api
    auth:
      type: bearer
      token_env: MY_API_TOKEN
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, OpenAPISource)
        assert src.auth is not None
        assert src.auth.type == "bearer"
        assert src.auth.token == "secret123"
        assert src.auth.token_env == "MY_API_TOKEN"

    def test_literal_token(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    url: https://api.example.com/openapi.json
    auth:
      type: bearer
      token: hardcoded-token
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, OpenAPISource)
        assert src.auth is not None
        assert src.auth.token == "hardcoded-token"
        assert src.auth.token_env is None

    def test_missing_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    url: https://api.example.com/openapi.json
    auth:
      type: bearer
      token_env: NONEXISTENT_VAR
""",
        )
        with pytest.raises(ConfigError, match="NONEXISTENT_VAR"):
            load_config(p)

    def test_missing_url(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    namespace: api
""",
        )
        with pytest.raises(ConfigError, match="'url' is required"):
            load_config(p)

    def test_base_url_override(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    url: https://api.example.com/openapi.json
    base_url: https://internal.example.com
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, OpenAPISource)
        assert src.base_url == "https://internal.example.com"

    def test_header_auth(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: openapi
    url: https://api.example.com/openapi.json
    auth:
      type: header
      header_name: X-API-Key
      token: my-key
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, OpenAPISource)
        assert src.auth is not None
        assert src.auth.type == "header"
        assert src.auth.header_name == "X-API-Key"
        assert src.auth.token == "my-key"


# ---------------------------------------------------------------------------
# Mode and filtering
# ---------------------------------------------------------------------------


class TestModeAndFiltering:
    def test_default_mode(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "tools: []")
        cfg = load_config(p)
        assert cfg.mode == "denylist"

    def test_allowlist_mode(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
mode: allowlist
enabled:
  - calc
  - web
""",
        )
        cfg = load_config(p)
        assert cfg.mode == "allowlist"
        assert cfg.enabled == ("calc", "web")

    def test_invalid_mode(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "mode: blocklist")
        with pytest.raises(ConfigError, match="Invalid mode"):
            load_config(p)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_config(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.json", "{}")
        cfg = load_config(p)
        assert cfg.mode == "denylist"
        assert cfg.disabled == ()
        assert cfg.enabled == ()
        assert cfg.tools == ()

    def test_empty_tools_list(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "tools: []")
        cfg = load_config(p)
        assert cfg.tools == ()

    def test_per_tool_enabled_false(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: python
    class: mod.Cls
    enabled: false
""",
        )
        cfg = load_config(p)
        src = cfg.tools[0]
        assert isinstance(src, PythonSource)
        assert src.enabled is False

    def test_top_level_not_mapping(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "- item1\n- item2")
        with pytest.raises(ConfigError, match="mapping at the top level"):
            load_config(p)

    def test_tool_entry_not_mapping(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "tools:\n  - just_a_string")
        with pytest.raises(ConfigError, match="must be a mapping"):
            load_config(p)

    def test_unknown_type(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
tools:
  - type: grpc
    url: http://localhost:9090
""",
        )
        with pytest.raises(ConfigError, match="unknown type"):
            load_config(p)

    def test_source_field(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "tools: []")
        cfg = load_config(p)
        assert cfg.source == str(p)

    def test_string_path(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "cfg.yaml", "tools: []")
        cfg = load_config(str(p))
        assert isinstance(cfg, ToolConfig)


# ---------------------------------------------------------------------------
# Round-trip: JSONC and YAML produce equal results
# ---------------------------------------------------------------------------


class TestRoundTrip:
    JSONC_CONTENT = """\
{
  "mode": "denylist",
  "disabled": ["web"],
  "tools": [
    {
      "type": "python",
      "class": "pkg.Calculator",
      "namespace": "calc"
    },
    {
      "type": "mcp",
      "transport": "sse",
      "url": "http://localhost:8080/sse",
      "namespace": "remote"
    },
    {
      "type": "openapi",
      "url": "https://api.example.com/openapi.json",
      "namespace": "api"
    }
  ]
}
"""

    YAML_CONTENT = """\
mode: denylist
disabled:
  - web
tools:
  - type: python
    class: pkg.Calculator
    namespace: calc
  - type: mcp
    transport: sse
    url: http://localhost:8080/sse
    namespace: remote
  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: api
"""

    def test_jsonc_yaml_equivalence(self, tmp_path: Path) -> None:
        jsonc_path = _write(tmp_path, "cfg.jsonc", self.JSONC_CONTENT)
        yaml_path = _write(tmp_path, "cfg.yaml", self.YAML_CONTENT)

        jsonc_cfg = load_config(jsonc_path)
        yaml_cfg = load_config(yaml_path)

        # source paths differ, compare everything else
        assert jsonc_cfg.mode == yaml_cfg.mode
        assert jsonc_cfg.disabled == yaml_cfg.disabled
        assert jsonc_cfg.enabled == yaml_cfg.enabled
        assert jsonc_cfg.tools == yaml_cfg.tools


# ---------------------------------------------------------------------------
# Multi-source config (integration)
# ---------------------------------------------------------------------------


class TestMultiSource:
    def test_mixed_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("API_TOKEN", "tok123")
        p = _write(
            tmp_path,
            "cfg.yaml",
            """\
mode: denylist
disabled:
  - filesystem

tools:
  - type: python
    class: toolregistry_hub.calculator.Calculator
    namespace: calculator

  - type: python
    module: my_package.tools
    namespace: custom

  - type: openapi
    url: https://api.example.com/openapi.json
    namespace: external_api
    auth:
      type: bearer
      token_env: API_TOKEN

  - type: mcp
    transport: stdio
    command: ["python", "-m", "mcp_server"]
    namespace: mcp_tools
    env:
      DEBUG: "1"

  - type: mcp
    transport: http
    url: http://localhost:8080/mcp
    namespace: remote_mcp
""",
        )

        cfg = load_config(p)

        assert cfg.mode == "denylist"
        assert cfg.disabled == ("filesystem",)
        assert len(cfg.tools) == 5

        # Python class
        s0 = cfg.tools[0]
        assert isinstance(s0, PythonSource)
        assert s0.class_path == "toolregistry_hub.calculator.Calculator"

        # Python module
        s1 = cfg.tools[1]
        assert isinstance(s1, PythonSource)
        assert s1.module_path == "my_package.tools"

        # OpenAPI with auth
        s2 = cfg.tools[2]
        assert isinstance(s2, OpenAPISource)
        assert s2.auth is not None
        assert s2.auth.token == "tok123"

        # MCP stdio
        s3 = cfg.tools[3]
        assert isinstance(s3, MCPSource)
        assert s3.transport == "stdio"
        assert s3.command == ("python", "-m", "mcp_server")
        assert s3.env == {"DEBUG": "1"}

        # MCP http alias
        s4 = cfg.tools[4]
        assert isinstance(s4, MCPSource)
        assert s4.transport == "streamable-http"
        assert s4.url == "http://localhost:8080/mcp"
