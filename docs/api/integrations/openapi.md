# OpenAPI Integration

This section documents the OpenAPI/Swagger integration capabilities of the ToolRegistry library.

## Architecture Overview

The OpenAPI integration is designed to automatically discover and register REST API endpoints as tools based on OpenAPI specifications. The architecture follows a three-layer design:

### Core Components

1. **OpenAPIToolWrapper**: A wrapper class that provides both synchronous and asynchronous HTTP client methods for API calls

   - Handles GET, POST, PUT, DELETE requests
   - Supports parameter processing and validation
   - Integrates with httpx for HTTP communication

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

::: toolregistry.openapi.integration.OpenAPIToolWrapper
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### OpenAPITool

Wrapper class for OpenAPI tools preserving function metadata.

::: toolregistry.openapi.integration.OpenAPITool
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### OpenAPIIntegration

Handles integration with OpenAPI services for tool registration.

::: toolregistry.openapi.integration.OpenAPIIntegration
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Module Utilities

### OpenAPI Utils

Utility functions for OpenAPI processing.

::: toolregistry.openapi.utils
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true
