# Helper Classes

This section documents the utility classes and helper functions that support the core functionality of the ToolRegistry library.

## Overview

Helper classes provide essential supporting functionality for parameter validation, utility operations, and common abstractions used throughout the ToolRegistry ecosystem.

## Available Helpers

### Parameter Models

Parameter validation and schema definitions for tool parameter processing.

- **Overview**: [Parameter Models](helpers/parameter_models.md)
- **Purpose**: Schema validation and parameter type checking
- **Key Features**: JSON Schema validation, type checking, required field validation
- **Usage**: Input validation for tool parameters

### Utilities

Utility functions and helper classes for common operations.

- **Overview**: [Utilities](helpers/utils.md)
- **Purpose**: Common utility functions and helper classes
- **Key Features**: Tool name normalization, HTTP client configuration, general utilities
- **Usage**: Shared functionality across different components

## Common Patterns

All helper classes follow these design principles:

### Validation Patterns

```python
# Parameter validation using JSON Schema
def validate_parameters(params: dict, schema: dict) -> bool:
    """Validate parameters against JSON Schema."""
    pass

# Type checking and conversion
def normalize_tool_name(name: str) -> str:
    """Normalize tool names for consistency."""
    pass
```

### Configuration Patterns

```python
# HTTP client configuration
client_config = HttpxClientConfig(
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer token"}
)
```

### Utility Patterns

```python
# Common utility functions
def normalize_tool_name(name: str) -> str:
    """Convert tool names to consistent format."""
    pass

def extract_namespace(tool_name: str) -> tuple[str, str]:
    """Extract namespace and tool name."""
    pass
```

## Architecture

Helper classes provide the foundation layer:

```
ToolRegistry Core
    ├── ToolRegistry (Orchestrator)
    ├── Tool (Abstraction)
    ├── Executor (Execution Engine)
    └── Helper Classes (Support Layer)
        ├── Parameter Validation
        ├── Utility Functions
        └── Common Abstractions
```

This support layer ensures:

- **Reusability**: Common functionality is shared across components
- **Consistency**: Unified approach to validation and utilities
- **Maintainability**: Centralized helper functionality
- **Extensibility**: Easy addition of new helper functions

## Integration Points

Helper classes integrate with:

- **Tool Classes**: Parameter validation for tool creation
- **Integration Modules**: Shared utility functions across integrations
- **ToolRegistry**: Core validation and utility operations
- **LLM Applications**: Input validation and result processing

These helper classes form the invisible foundation that enables consistent, reliable operation across all ToolRegistry components.
