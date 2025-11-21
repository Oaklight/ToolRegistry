# Core Classes

This section documents the core classes and base components that form the foundation of the ToolRegistry library.

## Overview

The core classes provide the fundamental abstractions for tool management, execution, and integration within the ToolRegistry ecosystem. These classes define the core patterns and interfaces used throughout the library.

## Available Classes

### ToolRegistry

The central registry class that manages tool registration, execution, and metadata across all integration types.

- **Overview**: [ToolRegistry](core/toolregistry.md)
- **Purpose**: Central orchestrator for tool management
- **Key Features**: Unified interface, namespace support, multi-source integration
- **Usage**: Primary entry point for all ToolRegistry operations

### Tool

Represents an individual tool with metadata and execution logic.

- **Overview**: [Tool](core/tool.md)
- **Purpose**: Fundamental abstraction for all tools
- **Key Features**: Metadata management, parameter validation, execution abstraction
- **Usage**: Base class for all tool implementations

### Executor

Handles the execution of tool calls with support for different concurrency modes and parallel execution strategies.

- **Overview**: [Executor](core/executor.md)
- **Purpose**: Core execution engine for parallel tool execution
- **Key Features**: Thread/process pool execution, async/sync bridge, error handling
- **Usage**: Powers concurrent tool execution across all tool types

### BaseToolWrapper

Base class for tool wrappers providing support for synchronous and asynchronous calls.

- **Overview**: [Wrappers/BasetoolWrapper](wrappers/basetoolwrapper.md)
- **Purpose**: Standardized interface for tool execution
- **Key Features**: Dual execution modes, automatic mode detection, parameter processing
- **Usage**: Foundation for all integration-specific wrappers

## Architecture Overview

```
ToolRegistry (Orchestrator)
    ├── Tool (Abstraction)
    ├── Executor (Execution Engine)
    │   └── BaseToolWrapper (Execution Interface)
    │       ├── MCPToolWrapper
    │       ├── OpenAPIToolWrapper
    │       └── LangChainToolWrapper
    └── Integration Modules
        ├── MCP Integration
        ├── OpenAPI Integration
        ├── LangChain Integration
        └── Native Integration
```

## Design Patterns

### Core Patterns

1. **Registry Pattern**: ToolRegistry serves as central registry
2. **Strategy Pattern**: Executor provides different execution strategies
3. **Template Method**: BaseToolWrapper defines execution template
4. **Adapter Pattern**: Tool wrappers adapt external interfaces
5. **Data Transfer Object**: Tool encapsulates data and behavior

### Integration Flow

```
External Source → Tool Wrapper → Tool → ToolRegistry → Executor → LLM Application
```

This flow ensures:

- **Consistency**: Unified interface across all tool types
- **Flexibility**: Support for diverse tool sources and execution strategies
- **Performance**: Optimized execution through parallel processing
- **Extensibility**: Easy addition of new integration types
- **Maintainability**: Clear separation of concerns

## Usage Patterns

### Basic Registration and Execution

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
# Tools are registered and executed through registry
# Executor handles parallel execution automatically
```

### Direct Tool Usage

```python
from toolregistry import Tool

tool = Tool(name="my_tool", ...)
# Use tool directly or through registry
# Executor provides concurrent execution when needed
```

### Custom Wrapper Implementation

```python
from toolregistry.tool_wrapper import BaseToolWrapper

class CustomWrapper(BaseToolWrapper):
    # Implement call_sync() and call_async()
    # Automatic integration with Executor
```

### Execution Configuration

```python
from toolregistry.executor import Executor

executor = Executor()
executor.set_execution_mode("process")  # or "thread"
# Executor manages parallel execution strategies
```

## Helper Classes

For supporting functionality like parameter validation and utilities, see:

- [**Helper Classes**](../helpers.md): Parameter validation and utility functions
- [Parameter Models](../helpers/parameter_models.md): Schema validation
- [Utilities](../helpers/utils.md): Common utility functions

The core classes provide the foundation that enables the rich integration ecosystem and efficient execution capabilities of the ToolRegistry library, ensuring consistent behavior and high-performance tool execution across all tool types and execution contexts.
