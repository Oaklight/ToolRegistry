import asyncio
import json
from typing import Any
from urllib.parse import urlparse

from ..._vendor.jsonschema import resolve_refs
from ..._vendor.yaml import YAMLError
from ..._vendor.yaml import load as yaml_load

from ..._vendor.httpclient import (
    AsyncClient,
    Client,
    HttpClientError,
    HTTPError,
    Response,
)
from ...utils import redact_url_userinfo


def _parse_spec_content(content: str) -> Any:
    """Parse an OpenAPI document, preferring JSON over YAML.

    JSON is a subset of YAML, but the vendored YAML reader does not join a
    flow mapping that continues past the first line (issue #369), so a
    pretty-printed JSON document would load as ``{None: None}``.  Decode JSON
    first and fall back to YAML only when the text is not valid JSON.

    A leading UTF-8 BOM is stripped here too.  Production callers decode with
    ``utf-8-sig``, but the helper must stay correct when called directly: the
    JSON decoder rejects a BOM and the YAML fallback would return a string.

    Args:
        content: Decoded OpenAPI document text.

    Returns:
        The parsed document.

    Raises:
        ValueError: If the text is empty or whitespace only.
        YAMLError: If the text is neither valid JSON nor valid YAML.
    """
    content = content.lstrip(chr(0xFEFF))
    if not content.strip():
        raise ValueError("OpenAPI document is empty")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return yaml_load(content)


def extract_base_url_from_specs(openapi_spec: dict[str, Any]) -> str | None:
    """
    Extract and validate the base URL from the 'servers' field of the OpenAPI specification.

    Args:
        openapi_spec (Dict[str, Any]): The parsed OpenAPI specification.

    Returns:
        Optional[str]: The validated base API URL extracted from the 'servers' field, or None if not valid.
    """
    servers = openapi_spec.get("servers", [])
    if servers:
        server_url = (
            servers[0].get("url", "").strip()
        )  # Get the first server URL and strip whitespace
        parsed_url = urlparse(server_url)

        # Validate the extracted URL
        if parsed_url.scheme in ["http", "https"] and parsed_url.netloc:
            return server_url.rstrip("/")

    return None


#: The only schemes an HTTP fetch path accepts.  ``load_openapi_spec`` treats
#: every other scheme — and a URI with no scheme — as a local file path.
_SPEC_URL_SCHEMES = frozenset({"http", "https"})


#: Added to a redacted ``$ref`` when redaction would leave a local pointer.
#: Only a ``#/`` pointer reaches the vendored resolver's lookup, so this
#: prefix keeps the value unresolvable, as the original pointer was.
_REDACTED_REF_PREFIX = "redacted:"


def _redact_dropped_refs(node: Any) -> None:
    """Strip userinfo from every ``$ref`` the resolver will drop, in place.

    ``_vendor.jsonschema`` warns with the raw ``$ref`` text when it drops a
    pointer.  A pointer that is not a local ``#/`` reference is always
    dropped, so rewriting it before resolution changes only that warning;
    the pointer itself never reaches the returned document.

    A local ``#/`` pointer is left byte for byte intact, because its exact
    text decides what resolves.

    Redaction can turn an external pointer into a local one: the bare form
    ``user:pass@#/definitions/X`` loses ``user:pass@`` and becomes
    ``#/definitions/X``, which the resolver would look up and could resolve.
    Such a value gets :data:`_REDACTED_REF_PREFIX`, so it stays unresolvable.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#/"):
            redacted = redact_url_userinfo(ref)
            if redacted.startswith("#/"):
                redacted = _REDACTED_REF_PREFIX + redacted
            node["$ref"] = redacted
        for value in node.values():
            _redact_dropped_refs(value)
    elif isinstance(node, list):
        for item in node:
            _redact_dropped_refs(item)


def resolve_refs_redacted(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local ``$ref`` pointers without leaking userinfo in warnings.

    The vendored resolver reports a dropped ``$ref`` by quoting it verbatim.
    An external ``$ref`` is always dropped, and its text comes from the
    document, which may be attacker controlled and may carry URL userinfo.
    ``_vendor/`` must not be edited in place, so every pointer that is going
    to be dropped is rewritten with :func:`redact_url_userinfo` applied
    before resolution starts.  Only the warning text changes: dropped
    pointers never appear in the result.

    This deliberately does not use ``warnings.catch_warnings``: that context
    manager changes process-wide state and would capture warnings raised by
    other threads.  Rewriting the input needs no global state.

    ``schema`` is modified in place.  Both spec loaders pass a document they
    just parsed, so no caller observes the rewritten pointers.

    Args:
        schema: A parsed OpenAPI or JSON Schema document.

    Returns:
        The resolved document, exactly as
        :func:`toolregistry._vendor.jsonschema.resolve_refs` returns it.
    """
    _redact_dropped_refs(schema)
    return resolve_refs(schema)


def validate_spec_url(uri: str) -> str:
    """Return *uri* unchanged when it is an HTTP(S) URL that names a host.

    ``load_openapi_spec`` reads a URI with no scheme, or with ``file``, as a
    local path only when the caller opts in with ``allow_local_files=True``,
    while ``load_openapi_spec_conditional_async`` can only fetch over HTTP(S).
    Callers that accept a URL from an untrusted source use this to refuse
    anything else before any I/O starts.

    Args:
        uri: A candidate specification URL.

    Returns:
        *uri*, unchanged.

    Raises:
        ValueError: If the URL cannot be parsed, its scheme is not
            ``http``/``https``, or it names no host.
    """
    try:
        parsed = urlparse(uri)
        host = parsed.hostname
        # Accessing ``port`` validates it: urlparse raises ValueError for a
        # non-numeric or out-of-range value.
        _ = parsed.port
    except ValueError as exc:  # malformed IPv6, invalid port, ...
        detail = redact_url_userinfo(str(exc))
        raise ValueError(f"'spec_url' is not a valid URL: {detail}") from exc
    scheme = parsed.scheme.lower()
    if scheme not in _SPEC_URL_SCHEMES:
        raise ValueError(
            f"Unsupported 'spec_url' scheme '{scheme or '(none)'}': "
            "only http and https URLs are allowed"
        )
    if not host:
        raise ValueError(
            "'spec_url' must include a host, for example "
            "https://example.com/openapi.json"
        )
    return uri


def determine_urls(url: str) -> dict[str, Any]:
    """
    Determine whether the given URL or its common endpoints contain an OpenAPI schema.

    Args:
        url (str): Base URL or schema URL.

    Returns:
        Dict[str, Any]: Contains "found" (bool), "schema_url" (str) if valid or None, and "base_api_url" (str).
    """
    common_endpoints = [
        "/openapi.json",
        "/swagger.json",
        "/api-docs",
        "/v3/api-docs",
        "/swagger.yaml",
        "/openapi.yaml",
    ]
    base_url = url.rstrip("/")

    # Direct schema check for common endpoints
    for endpoint in common_endpoints:
        if base_url.endswith(endpoint):
            base_api_url = base_url.rstrip(endpoint)
            return {"found": True, "schema_url": base_url, "base_api_url": base_api_url}

    # Test appending endpoints to base URL
    with Client(timeout=5.0) as client:
        for endpoint in common_endpoints:
            full_url = f"{base_url}{endpoint}"
            try:
                response = client.get(full_url)
                if response.status_code == 200:
                    content_type = (response.headers.get("content-type") or "").lower()
                    if "json" in content_type or "yaml" in content_type:
                        return {
                            "found": True,
                            "schema_url": full_url,
                            "base_api_url": base_url,
                        }
            except HttpClientError:
                continue

    return {"found": False, "base_api_url": base_url}


async def load_openapi_spec_async(
    uri: str, *, allow_local_files: bool = False
) -> dict[str, Any]:
    """Async version of load_openapi_spec using AsyncClient.

    A URI with no scheme, or with the ``file`` scheme, names a local file.
    Such a URI is refused by default so that a spec location supplied by
    someone else cannot be turned into a read of the local file system.  A
    caller that really means to read a local file passes
    ``allow_local_files=True``.

    Args:
        uri (str): URL or file path pointing to an OpenAPI specification.
        allow_local_files: Read *uri* from the local file system when it names
            a path or a ``file://`` URI.  Defaults to ``False``.

    Returns:
        Dict[str, Any]: A dictionary containing the parsed OpenAPI specification.

    Raises:
        ValueError: If URI retrieval, parsing, or decoding fails, or if *uri*
            names a local file while *allow_local_files* is false.
    """
    try:
        parsed_uri = urlparse(uri)
    except Exception as exc:  # noqa: BLE001 - same wrapping as the request path
        # A malformed authority (an unterminated IPv6 literal, for example)
        # keeps the loader's error wrapping and redaction.
        raise ValueError(f"Unexpected error: {redact_url_userinfo(str(exc))}") from exc
    is_local = parsed_uri.scheme in ("", "file")
    if is_local and not allow_local_files:
        raise ValueError(
            "Reading an OpenAPI specification from the local file system is "
            "disabled; pass allow_local_files=True to allow it"
        )

    try:
        if is_local:  # Handle file paths
            file_path = parsed_uri.path if parsed_uri.scheme == "file" else uri
            with open(file_path, "rb") as file:
                openapi_spec_content = file.read()
        else:  # Handle URLs
            # First attempt to determine schema URL and fallback base URL
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, determine_urls, uri)
            uri = results["schema_url"] if results["found"] else uri

            # timeout for network requests (e.g., 10 seconds)
            async with AsyncClient(timeout=10) as client:
                response = await client.get(uri)
                assert isinstance(response, Response)
                response.raise_for_status()
                openapi_spec_content = response.content

        # Load and parse OpenAPI spec (CPU-bound operation)
        loop = asyncio.get_event_loop()
        openapi_spec_dict = await loop.run_in_executor(
            None,
            lambda: resolve_refs_redacted(
                _parse_spec_content(openapi_spec_content.decode("utf-8-sig"))
            ),
        )

        # Ensure return type matches Dict[str, Any]
        if not isinstance(openapi_spec_dict, dict):
            raise ValueError("OpenAPI spec must be a dictionary")
        return dict(openapi_spec_dict)  # Explicit type conversion

    except YAMLError as e:
        raise ValueError(f"Failed to parse OpenAPI content: {e}")
    except HTTPError as e:
        raise ValueError(
            f"HTTP error: {e.status_code} for {redact_url_userinfo(str(e.url))}"
        )
    except HttpClientError as e:
        raise ValueError(
            f"Network error when fetching URI: {redact_url_userinfo(str(e))}"
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Invalid file path: {e}")
    except Exception as e:
        raise ValueError(f"Unexpected error: {redact_url_userinfo(str(e))}")


def load_openapi_spec(uri: str, *, allow_local_files: bool = False) -> dict[str, Any]:
    """Sync version that calls the async implementation.

    Args:
        uri (str): URL or file path pointing to an OpenAPI specification.
        allow_local_files: Read *uri* from the local file system when it names
            a path or a ``file://`` URI.  Defaults to ``False``.

    Returns:
        Dict[str, Any]: A dictionary containing the parsed OpenAPI specification.

    Raises:
        ValueError: If URI retrieval, parsing, or decoding fails, or if *uri*
            names a local file while *allow_local_files* is false.
    """
    return asyncio.run(
        load_openapi_spec_async(uri, allow_local_files=allow_local_files)
    )


async def load_openapi_spec_conditional_async(
    uri: str,
    etag: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch an OpenAPI spec with ETag-based conditional request support.

    When *etag* is provided, an ``If-None-Match`` header is sent.  If the
    server responds with ``304 Not Modified`` the spec is unchanged and
    ``(None, etag)`` is returned, avoiding re-parsing.

    Args:
        uri: URL pointing to an OpenAPI specification.
        etag: ETag value from a previous fetch.  ``None`` for the first request.
        headers: Extra HTTP headers to include in the request.

    Returns:
        A ``(spec_dict, new_etag)`` tuple.  ``spec_dict`` is ``None`` when the
        server returned 304.
    """
    try:
        req_headers: dict[str, str] = dict(headers or {})
        if etag is not None:
            req_headers["If-None-Match"] = etag

        async with AsyncClient(timeout=10) as client:
            response = await client.get(uri, headers=req_headers)
            assert isinstance(response, Response)

            if response.status_code == 304:
                return None, etag

            response.raise_for_status()

            new_etag = response.headers.get("ETag") or response.headers.get("etag")
            openapi_spec_content = response.content

        loop = asyncio.get_running_loop()
        openapi_spec_dict = await loop.run_in_executor(
            None,
            lambda: resolve_refs_redacted(
                _parse_spec_content(openapi_spec_content.decode("utf-8-sig"))
            ),
        )

        if not isinstance(openapi_spec_dict, dict):
            raise ValueError("OpenAPI spec must be a dictionary")
        return dict(openapi_spec_dict), new_etag

    except YAMLError as e:
        raise ValueError(f"Failed to parse OpenAPI content: {e}")
    except HTTPError as e:
        raise ValueError(
            f"HTTP error: {e.status_code} for {redact_url_userinfo(str(e.url))}"
        )
    except HttpClientError as e:
        raise ValueError(
            f"Network error when fetching URI: {redact_url_userinfo(str(e))}"
        )
    except Exception as e:
        raise ValueError(f"Unexpected error: {redact_url_userinfo(str(e))}")


def load_openapi_spec_conditional(
    uri: str,
    etag: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Sync version of :func:`load_openapi_spec_conditional_async`."""
    return asyncio.run(load_openapi_spec_conditional_async(uri, etag, headers))
