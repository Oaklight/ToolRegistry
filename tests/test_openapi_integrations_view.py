"""Public view of the registered OpenAPI integrations (#458)."""

import pytest

from toolregistry import ToolRegistry
from toolregistry.utils import HttpClientConfig

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "ViewAPI", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {"operationId": "listItems", "summary": "List items"},
        },
    },
}

SPEC_ADDED = {
    **SPEC,
    "paths": {
        **SPEC["paths"],
        "/items": {
            **SPEC["paths"]["/items"],
            "post": {"operationId": "createItem", "summary": "Create item"},
        },
    },
}


def _config() -> HttpClientConfig:
    return HttpClientConfig(base_url="http://test.example.com")


class TestOpenAPIIntegrationsView:
    def test_registrations_are_listed_in_creation_order(self):
        registry = ToolRegistry()
        registry.register_from_openapi(
            _config(), SPEC, spec_url="http://first.test/spec.json"
        )
        registry.register_from_openapi(
            _config(), SPEC, spec_url="http://second.test/spec.json"
        )

        integrations = registry.openapi_integrations

        assert isinstance(integrations, tuple)
        assert len(integrations) == 2
        assert [item._spec_url for item in integrations] == [
            "http://first.test/spec.json",
            "http://second.test/spec.json",
        ]
        assert integrations[-1] is registry._openapi_integrations[-1]

    def test_the_tuple_is_an_immutable_snapshot(self):
        registry = ToolRegistry()
        registry.register_from_openapi(
            _config(), SPEC, spec_url="http://first.test/spec.json"
        )
        view = registry.openapi_integrations

        with pytest.raises(TypeError):
            view[0] = None  # type: ignore[index]

        registry.register_from_openapi(
            _config(), SPEC, spec_url="http://second.test/spec.json"
        )
        # A tuple returned earlier does not grow when another source registers.
        assert len(view) == 1
        assert len(registry.openapi_integrations) == 2

    @pytest.mark.asyncio
    async def test_the_newest_entry_owns_the_second_spec_url_and_etag(
        self, monkeypatch
    ):
        import toolregistry.integrations.openapi.utils as openapi_utils

        async def fake_conditional(url, etag=None, headers=None, **kwargs):
            return SPEC_ADDED, '"second-etag"'

        async def fake_validate(url, **kwargs):
            return url

        monkeypatch.setattr(
            openapi_utils, "load_openapi_spec_conditional_async", fake_conditional
        )
        monkeypatch.setattr(openapi_utils, "validate_spec_url_async", fake_validate)

        registry = ToolRegistry()
        registry.register_from_openapi(
            _config(), SPEC, spec_url="http://first.test/spec.json"
        )
        registry.register_from_openapi(
            _config(), SPEC, spec_url="http://second.test/spec.json"
        )

        await registry.refresh_from_openapi_async(index=1)

        first, second = registry.openapi_integrations
        assert first._etag is None
        assert second._spec_url == "http://second.test/spec.json"
        assert second._etag == '"second-etag"'
