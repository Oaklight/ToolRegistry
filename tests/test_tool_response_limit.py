"""Tests for the tool-response size cap (#391).

The OpenAPI integration reads a tool response through the vendored HTTP
client.  A buffered response is capped by default so one call cannot buffer
an arbitrarily large body, and the wrapper raises a size error whose message
does not echo credentials embedded in the base URL.
"""

import contextlib
import http.server
import json
import pickle
import threading
import traceback

import pytest

from toolregistry._vendor.httpclient import (
    ResponseTooLargeError as VendorResponseTooLargeError,
)
from toolregistry.errors import ResponseTooLargeError
from toolregistry.integrations.openapi.integration import OpenAPIToolWrapper
from toolregistry.utils import (
    DEFAULT_MAX_TOOL_RESPONSE_BYTES,
    HttpClientConfig,
)

#: A valid JSON body well above the small caps used in these tests.
_BODY = json.dumps({"data": "x" * 4096}).encode()


@contextlib.contextmanager
def _serve():
    """Serve ``_BODY`` over HTTP on an ephemeral loopback port."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(_BODY)))
            self.end_headers()
            try:
                self.wfile.write(_BODY)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client refused the response and closed

        def log_message(self, format: str, *args: object) -> None:
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


class TestDefaultCap:
    """The cap is on by default and matches the spec-download budget."""

    def test_default_is_ten_mib(self):
        config = HttpClientConfig(base_url="https://example.com")
        assert config.max_response_size == DEFAULT_MAX_TOOL_RESPONSE_BYTES
        assert DEFAULT_MAX_TOOL_RESPONSE_BYTES == 10 * 1024 * 1024

    def test_default_reaches_the_client(self):
        config = HttpClientConfig(base_url="https://example.com")
        assert (
            config._client_kwargs()["max_response_size"]
            == DEFAULT_MAX_TOOL_RESPONSE_BYTES
        )
        client = config.to_client()
        assert client._client._max_response_size == DEFAULT_MAX_TOOL_RESPONSE_BYTES

    def test_over_limit_raises(self):
        with _serve() as base:
            config = HttpClientConfig(
                base_url=base, max_response_size=1024, allow_private_hosts=True
            )
            with config.to_client() as client:
                with pytest.raises(ResponseTooLargeError):
                    client.get("/data")

    def test_explicit_none_disables_the_cap(self):
        with _serve() as base:
            config = HttpClientConfig(
                base_url=base, max_response_size=None, allow_private_hosts=True
            )
            with config.to_client() as client:
                response = client.get("/data")
            assert response.content == _BODY

    def test_streaming_is_not_limited(self):
        with _serve() as base:
            config = HttpClientConfig(
                base_url=base, max_response_size=64, allow_private_hosts=True
            )
            with config.to_client() as client:
                response = client.get("/data", stream=True)
                try:
                    body = b"".join(response.iter_bytes())
                finally:
                    response.close()
            assert body == _BODY

    def test_error_is_the_public_type(self):
        assert ResponseTooLargeError is VendorResponseTooLargeError

    def test_pickle_round_trip_preserves_the_cap(self):
        """The process-pool backend restores the config in another process."""
        for value in (DEFAULT_MAX_TOOL_RESPONSE_BYTES, 2048, None):
            config = HttpClientConfig(
                base_url="https://example.com", max_response_size=value
            )
            restored = pickle.loads(pickle.dumps(config))
            assert restored.max_response_size == value


class TestOpenAPIToolWrapper:
    """The wrapper applies the cap and redacts base-URL userinfo."""

    def test_sync_error_redacts_userinfo(self):
        with _serve() as base:
            host = base.removeprefix("http://")
            config = HttpClientConfig(
                base_url=f"http://user:secret@{host}",
                max_response_size=1024,
                allow_private_hosts=True,
            )
            wrapper = OpenAPIToolWrapper(
                client_config=config,
                name="big",
                method="get",
                path="/data",
                params=None,
                persistent=False,
            )
            with pytest.raises(ResponseTooLargeError) as excinfo:
                wrapper.call_sync()
        error = excinfo.value
        assert "user:secret" not in str(error)
        assert "user:secret" not in error.url
        # ``from None`` keeps the unredacted original out of the traceback.
        assert error.__cause__ is None
        rendered = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        assert "user:secret" not in rendered

    @pytest.mark.asyncio
    async def test_async_error_redacts_userinfo(self):
        with _serve() as base:
            host = base.removeprefix("http://")
            config = HttpClientConfig(
                base_url=f"http://user:secret@{host}",
                max_response_size=1024,
                allow_private_hosts=True,
            )
            wrapper = OpenAPIToolWrapper(
                client_config=config,
                name="big",
                method="get",
                path="/data",
                params=None,
                persistent=False,
            )
            with pytest.raises(ResponseTooLargeError) as excinfo:
                await wrapper.call_async()
        error = excinfo.value
        assert "user:secret" not in str(error)
        assert error.__cause__ is None
        rendered = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        assert "user:secret" not in rendered

    def test_request_under_the_cap_succeeds(self):
        with _serve() as base:
            config = HttpClientConfig(
                base_url=base, max_response_size=8192, allow_private_hosts=True
            )
            wrapper = OpenAPIToolWrapper(
                client_config=config,
                name="ok",
                method="get",
                path="/data",
                params=None,
                persistent=False,
            )
            assert wrapper.call_sync() == json.loads(_BODY)
