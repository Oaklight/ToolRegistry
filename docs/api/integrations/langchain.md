# LangChain Integration

This section documents the LangChain integration capabilities of the ToolRegistry library.

## Architecture Overview

The LangChain integration enables seamless interoperability between LangChain tools and the ToolRegistry ecosystem. This integration allows LangChain's extensive tool ecosystem to be used within the ToolRegistry framework:

### Core Components

1. **LangChainToolWrapper**: A wrapper class that bridges LangChain tools with ToolRegistry's unified interface

   - Provides both synchronous (`_run`) and asynchronous (`_arun`) execution methods
   - Manages parameter mapping between LangChain and ToolRegistry formats
   - Handles error propagation and logging

2. **LangChainTool**: A tool class that wraps LangChain BaseTool instances

   - Preserves original tool metadata and descriptions
   - Converts LangChain input schemas to ToolRegistry format
   - Maintains namespace support for tool organization

3. **LangChainIntegration**: The main integration class that orchestrates the bridging process
   - Manages the conversion from LangChain tools to ToolRegistry tools
   - Supports both individual tool and batch registration patterns
   - Handles schema transformation and normalization

### Design Philosophy

- **Non-invasive Integration**: Preserves original LangChain tool behavior
- **Schema Compatibility**: Automatic conversion between LangChain and ToolRegistry schemas
- **Error Transparency**: Original LangChain exceptions are preserved and enhanced with context
- **Async Support**: Full compatibility with LangChain's async execution model

### Key Features

- Direct integration with LangChain's `BaseTool` instances
- Automatic schema transformation from LangChain to ToolRegistry format
- Support for both synchronous and asynchronous execution modes
- Namespace support for organizing LangChain tools
- Preserved error handling and logging from original LangChain tools
- Minimal overhead - no additional dependencies or transformations

### Usage Patterns

- **Single Tool Integration**: Register individual LangChain tools
- **Tool Collections**: Integrate multiple LangChain tools from collections
- **Namespace Organization**: Group LangChain tools under common namespaces
- **Error Handling**: Maintain LangChain's original exception behavior with enhanced context

## API Reference

### LangChainToolWrapper

Wrapper class providing both async and sync versions of LangChain tool calls.

::: toolregistry.langchain.integration.LangChainToolWrapper
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### LangChainTool

Wrapper class for LangChain tools that preserves original function metadata.

::: toolregistry.langchain.integration.LangChainTool
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### LangChainIntegration

Handles integration with LangChain tools for registration.

::: toolregistry.langchain.integration.LangChainIntegration
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Module Overview

### LangChain Module

The main LangChain integration module.

::: toolregistry.langchain
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true
