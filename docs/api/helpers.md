# Helper Classes

Utility classes and helper functions that support the core functionality of the ToolRegistry library.

## Parameter Models

Parameter validation and schema generation for tool functions. `ArgModelBase` dynamically creates Pydantic models from function signatures for runtime argument validation.

::: toolregistry.parameter_models
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false

## Utilities

`toolregistry.utils` is the compatibility surface: it re-exports every helper
that downstream packages import, so existing imports keep working. The
implementations live next to their concern: tool-name normalization and the
registration filter in `toolregistry._names`, base-URL HTTP clients and
`HttpClientConfig` in `toolregistry._http`, and tool-result encoding in
`toolregistry._serialisation`.

The admin panel's Python-source preview lists only functions defined in the
module. Because `toolregistry.utils` is now a compatibility surface,
previewing it no longer lists the moved functions; register those from
`toolregistry._names`, `toolregistry._http` or `toolregistry._serialisation`.

::: toolregistry.utils
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false
