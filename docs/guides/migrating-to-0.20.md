# Migrating to 0.20

This release changes what an outbound request may reach, how the OpenAPI
loaders fetch and size a document, and how much of a tool response is buffered.
Each change has an opt-in that restores the old behaviour where it is still safe
to do so.

## Outbound address policy

Every outbound request now resolves the host before a connection is opened and
refuses loopback, link-local, private, multicast and reserved addresses. A name
that does not resolve is refused too. A successful answer is cached for 60
seconds; a failure is never cached.

This covers `validate_spec_url()`, `load_openapi_spec()`,
`load_openapi_spec_async()`, `extract_base_url_from_specs()`,
`HttpClientConfig`, both base-URL clients, `OpenAPISource`, `MCPClient`,
`register_mcp_tools*()`, `register(..., source="mcp")`, `MCPSource` and
`registry.enable_admin()`.

A local or internal API opts in explicitly:

```python
# before — the host was used as given
config = HttpClientConfig(base_url="http://localhost:11434")

# after — UnsafeAddressError unless the host is public
config = HttpClientConfig(base_url="http://localhost:11434", allow_private_hosts=True)
```

The same flag on the other entry points:

```python
spec = load_openapi_spec(
    "http://127.0.0.1:8000/openapi.json",
    allow_private_hosts=True,
)

registry.register(..., source="openapi", allow_private_hosts=True)
registry.register(..., source="mcp", allow_private_hosts=True)
```

The admin panel has its own switch. Start it with
`registry.enable_admin(allow_private_hosts=True)` so preview and registration can
reach a local API. `GET /api/info` reports the value as `allow_private_hosts`, and
the OpenAPI form shows a hint when the server refuses private addresses.

## Redirects

`load_openapi_spec()`, `load_openapi_spec_async()` and `determine_urls()` no
longer follow redirects by default. The next hop cannot be checked against the
outbound policy, so a 3xx is refused with an error that names the final URL.

```python
# before — a 302 was followed to an address nobody validated
spec = load_openapi_spec("https://api.example.com/openapi.json")

# after — pass the final URL ...
spec = load_openapi_spec("https://api.example.com/v2/openapi.json")

# ... or opt in when the target is trusted
spec = load_openapi_spec("https://api.example.com/openapi.json", follow_redirects=True)
```

A tool call still follows redirects, because the vendored HTTP client cannot
expose each hop for validation. Redirect revalidation on the call path is tracked
in #399.

## Spec size and depth

A downloaded document is buffered up to 10 MiB (`DEFAULT_MAX_SPEC_BYTES`) and
nested up to 100 containers (`DEFAULT_MAX_SPEC_DEPTH`). A declared
`Content-Length` over the budget is refused before the body is read, and an
unbounded stream is cut off at the limit. A parser recursion overflow raises
`SpecTooDeepError` instead of a generic `ValueError`.

```python
# before — any size, any depth
spec = load_openapi_spec(url)

# after — raise the budgets when the document is legitimately larger
spec = load_openapi_spec(url, max_bytes=32 * 1024 * 1024, max_depth=200)
```

## Tool response size

An OpenAPI tool call buffers its response, so it is capped at 10 MiB
(`DEFAULT_MAX_TOOL_RESPONSE_BYTES`, importable from `toolregistry.utils`).
Exceeding the cap raises `ResponseTooLargeError`, re-exported from
`toolregistry.errors`.

```python
# before — the whole body was buffered, whatever its size
config = HttpClientConfig(base_url=BASE)

# after — raise the cap ...
config = HttpClientConfig(base_url=BASE, max_response_size=64 * 1024 * 1024)

# ... or turn it off for a tool that really needs an unbounded read
config = HttpClientConfig(base_url=BASE, max_response_size=None)
```

## Local spec files

`load_openapi_spec()` and `load_openapi_spec_async()` used to read any URI with no
scheme, or with the `file` scheme, from the local file system. A caller that
passed a location supplied by someone else could therefore be made to read an
arbitrary file. Both loaders now raise `ValueError` for a local path or a
`file://` URI before any I/O.

```python
# before
spec = load_openapi_spec("./openapi.json")

# after
spec = load_openapi_spec("./openapi.json", allow_local_files=True)
```

The admin panel is unaffected: it already restricts `spec_url` to http(s).
