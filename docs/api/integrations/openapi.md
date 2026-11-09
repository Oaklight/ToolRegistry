# OpenAPI Integration

This section documents the OpenAPI/Swagger integration capabilities of the ToolRegistry library.

## Architecture Overview

The OpenAPI integration is designed to automatically discover and register REST API endpoints as tools based on OpenAPI specifications. The architecture follows a three-layer design:

### Core Components

1. **OpenAPIToolWrapper**: A wrapper class that provides both synchronous and asynchronous HTTP client methods for API calls

   - Handles GET, POST, PUT, DELETE requests
   - Supports parameter processing and validation
   - Integrates with a built-in HTTP client for HTTP communication

2. **OpenAPITool**: A tool class that preserves function metadata extracted from OpenAPI specifications

   - Automatically generates parameter schemas from OpenAPI specs
   - Normalizes tool names and descriptions
   - Maintains namespace support

3. **OpenAPIIntegration**: The main integration class that orchestrates the registration process
   - Parses OpenAPI specifications
   - Creates tool instances for each endpoint
   - Supports both synchronous and asynchronous registration

### Design Patterns

- **Factory Pattern**: `OpenAPITool.from_openapi_spec()` creates tool instances from specifications
- **Wrapper Pattern**: `OpenAPIToolWrapper` provides a unified interface for HTTP operations
- **Template Method**: Both sync and async versions follow similar patterns with async/await support

### Key Features

- Automatic parameter extraction from OpenAPI schemas
- Support for query parameters, path parameters, and request bodies
- Namespace support for organizing tools
- Full async/await compatibility
- Automatic HTTP status error handling

## API Reference

### OpenAPIToolWrapper

Wrapper class that provides both synchronous and asynchronous methods for OpenAPI tool calls.

::: toolregistry.integrations.openapi.integration.OpenAPIToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### OpenAPITool

Wrapper class for OpenAPI tools preserving function metadata.

::: toolregistry.integrations.openapi.integration.OpenAPITool
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### OpenAPIIntegration

Handles integration with OpenAPI services for tool registration.

::: toolregistry.integrations.openapi.integration.OpenAPIIntegration
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## Refreshing a document

`OpenAPIIntegration.refresh()` re-reads the document the source was
registered from, using the stored ETag. A `304` returns `skipped` and changes
nothing: no route rebuild, no `last_refreshed_at` bump. A changed document is
diffed against the live tools, so a name the operator disabled by hand stays
disabled, a path that disappeared is unregistered, and a tool whose
definition did not change keeps its registry state.

The base URL follows the document, within a limit. The URL the registration
document named at `servers[0]` is remembered, and a refresh adopts a moved
`servers[0]` only while the client config still points at that remembered
value — a base URL the caller supplied explicitly is never replaced. Only the
entry a refresh would adopt is checked against the outbound address policy;
entries that are never dialed are neither validated nor resolved, and an
explicit override makes the document's `servers` irrelevant to the refresh. A
templated entry such as `https://{region}.example.com` cannot be resolved
before substitution, so it is never adopted or checked: the current base URL
stays and the rest of the document still applies. Adoption rebuilds every
tool's wrapper, including operations whose definition did not change; that
replacement is not counted in `updated`, and `RefreshResult.base_url_changed`
reports it instead. A candidate that is refused raises `UnsafeAddressError`
and leaves the tools, the config and the stored document untouched.

`forget_tracked_tools(names)` is the hook for a caller that removes a tool
between refreshes — for example a validation step that drops a tool whose
schema it cannot accept. Without it the next refresh treats the name as
tracked but absent and never registers it again; with it the name comes back
when the document is fixed. It only changes the tracked set: the caller has
already handled the registry and the events.

`ToolRegistry.openapi_integrations` returns those integrations in creation
order, so a caller that needs the one it just registered can take the last
element instead of reading a private list.

## Module Utilities

### OpenAPI Utils

Utility functions for OpenAPI processing.

::: toolregistry.integrations.openapi.utils
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
