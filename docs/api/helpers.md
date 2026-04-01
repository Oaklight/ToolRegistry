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

Common utility functions used across the library, including tool name normalization and HTTP client configuration for OpenAPI integrations.

::: toolregistry.utils
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false
