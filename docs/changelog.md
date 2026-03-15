---
title: Changelog
summary: Version history and change records for the ToolRegistry project
description: Detailed documentation of all feature updates, fixes, and improvements in ToolRegistry since version 0.1.0
keywords: changelog, version history, release notes, changes
author: Oaklight
---

# Changelog

This page documents all notable changes to the ToolRegistry project since the first release.

## [0.5.1] - 2026-03-13

### ⚠️ Breaking Changes

- **Upgrade Minimum Python Version to 3.10** ([#74](../../issues/74))
	- Update `requires-python` from `>=3.8` to `>=3.10`
	- Python 3.8 and 3.9 are no longer supported
	- This aligns with Python 3.9 EOL and MCP SDK requirements

### Maintenance

- Remove `fake-useragent` dependency (no longer used after toolregistry-hub split)
- Remove legacy `./docs` directory (migrated to `docs_en`/`docs_zh` worktrees)
- Add Python 3.10/3.11/3.12/3.13 classifiers to pyproject.toml

### New Features

- **Callback Mechanism** ([#68](../../issues/68))
	- Added `on_change()` and `remove_on_change()` methods for monitoring registry changes
	- Supports callbacks for tool registration, removal, enable/disable events

### Refactoring

- **Modernize Type Annotations for Python 3.10+**
	- Replaced `Union[X, Y]` with `X | Y` syntax
	- Replaced `Optional[X]` with `X | None`
	- Replaced `List`, `Dict`, `Tuple` with lowercase `list`, `dict`, `tuple`

## [0.5.0] - 2026-03-10

### Refactoring

- **MCP Client Decoupled from fastmcp** ([#64](../../issues/64), [#65](../../pull/65))
	- Create `MCPClient` adapter in `mcp/client.py` using the official `mcp` SDK
	- Remove all `fastmcp` imports from `integration.py`, `utils.py`, and `tool_registry.py`
	- Change `[mcp]` extra dependency from `fastmcp` to `mcp>=1.0.0`
	- Add v1/v2 dual compatibility for camelCase/snake_case attributes
	- Support all four transports: stdio, SSE, streamable-http, websocket
	- Add `headers` parameter for HTTP authentication
	- Add 25 new tests covering `MCPClient` functionality

- **Remove `toolregistry[hub]` optional extra** ([#50](../../issues/50), [#56](../../pull/56))
	- Remove `hub = ['toolregistry-hub>=0.4.14']` from optional dependencies in `pyproject.toml`
	- Users should now install hub tools directly via `pip install toolregistry-hub`
	- The `from toolregistry.hub import ...` shim still works when both packages are installed
	- Update installation docs, hub integration docs, and README accordingly

### New Features

- **Enable/Disable with Reason Tracking** ([#53](../../issues/53), [#58](../../pull/58))
	- Add method-level and namespace-level disable with reason tracking
	- New methods: `disable(name, reason)`, `enable(name)`, `is_enabled(tool_name)`, `get_disable_reason(tool_name)`
	- `list_tools()` now only returns enabled tools
	- Add `list_all_tools()` for admin panel use (returns all tools including disabled)
	- `get_tools_json()` filters disabled tools when no specific tool_name given
	- `execute_tool_calls()` returns error message for disabled tools instead of executing
	- Add 28 new tests

- **Namespace & MRO Support** ([#51](../../issues/51), [#52](../../issues/52), [#57](../../pull/57))
	- Add `namespace`, `method_name` fields and `qualified_name` property to `Tool` model
	- `_update_sub_registries()` now uses `namespace` field for grouping, eliminating `-`/`_` ambiguity
	- Add `traverse_mro` parameter to `register_from_class()` and `register_from_class_async()`
	- Change `traverse_mro` default to `True` — child class methods take priority over parent class methods

### ⚠️ Breaking Changes

- `register_from_class()` now defaults to `traverse_mro=True`, meaning inherited public static and instance methods are registered automatically. Pass `traverse_mro=False` explicitly to get the previous behavior

### Maintenance

- Pin MCP SDK to `<2.0.0` to avoid v2 breaking changes while support for the official MCP SDK v2 is being developed
- Remove unused `beautifulsoup4` dependency

## [0.4.14] - 2025-08-11

### New Features

- **Type System Refactor**
	- Modularize and extend type definitions
	- Add custom tool call support
	- Add comprehensive error handling and validation for tool call conversion

- **Hub Module Spinoff**
	- Migrate hub module to external package (`toolregistry-hub`)
	- Add alternative import path for `toolregistry.hub`
	- Update installation documentation with hub tools instructions

### Documentation Improvements

- Reorganize hub documentation and add new hub tools docs
- Add note about package split in version 0.4.14

## [0.4.13] - 2025-06-20

### New Features

- **OpenAI Response API Support**
	- Add `ResponseFunctionToolCall` model
	- Add `api_mode` parameter to `get_tools_json` for JSON schema generation
	- Add `recover_tool_message` function
	- Add custom serializer for `result` field
	- Add `ChatCompletionMessage` model

- **Executor Improvements**
	- Add sync wrapper for async functions
	- Add executor for tool call management

- **OpenAPI Enhancements**
	- Add `HttpxClientConfig` to exports
	- Add overloads for httpx client creation

### Refactoring

- Restructure tool call handling for cleaner architecture
- Streamline tool parameter validation
- Simplify FastMCP import and usage
- Unify API mode to API format

### Bug Fixes

- Fix calculator: handle non-callable attributes correctly
- Fix integration: handle empty params gracefully
- Fix utils: resolve internal MCP server retrieval issue
- Fix executor: correct function type hint
- Fix toolregistry: handle event loop closure
- Fix parameter_models: correct field creation logic
- Fix toolregistry: correct typing for client configuration

### Maintenance

- Update type checker from mypy to pyright
- Update dependency versions
- Update mcp dependency version range (Closes #36)

### Documentation Improvements

- Add integration guides for OpenAI Chat Completion and Response API
- Add documentation for toolregistry modules
- Update MCP transport documentation

## [0.4.12] - 2025-06-04

### New Features

- **Calculator Refactor**
	- Spin off `BaseCalculator` from `Calculator` for cleaner architecture

- **OpenAPI Integration**
	- Refactor OpenAPI integration to modular structure
	- Add FastAPI as dev dependency

### Refactoring

- Restructure class tool integration implementation
- Reorganize MCP integration code
- Reorganize LangChain integration
- Move util function to native module

### Maintenance

- Deprecate labeled functions
- Update test cases for registry key format

### Documentation Improvements

- Update OpenAPI integration guide and examples
- Regenerate Sphinx documentation after reorganization

## [0.4.11] - 2025-06-03

### New Features

- **Web Search Enhancements**
	- Add fetch tool to websearch module
	- Add blocklist filtering for search results with GitHub raw proxy support
	- Add accept header to mobile user agent
	- Add real URL extraction from Bing redirects

- **Search Result Filtering** (Closes #29)
	- Improve search result filtering and blocklist caching mechanism

### Bug Fixes

- Fix websearch_bing: adjust pagination parameters
- Fix websearch: handle domain separator in blocklist parsing

### Documentation Improvements

- Add documentation for websearch and fetch tools
- Add documentation for websearch modules

## [0.4.10] - 2025-05-23

### New Features

- **Bing Search Integration**
	- Add Bing search functionality to websearch module

- **MCP Transport**
	- Add support for streamable-http transport mode
	- Fix transport type handling in MCP integration

- **ToolSpec Refactor**
	- Streamline tool creation with `ToolSpec`

### Bug Fixes

- Fix MCP tool name normalization raising error during execution (Closes #25)

### Refactoring

- Centralize lynx header generation
- Rename header variables for consistency

### Documentation Improvements

- Add Read the Docs configuration
- Restructure hub and examples documentation
- Add multilingual documentation support
- Add various example guides (consecutive tool calls, hub calculator, MCP, OpenAPI, LangChain)

## [0.4.9] - 2025-05-21

### New Features

- **LangChain Integration**
	- Add LangChain tool registration support
	- Add LangChain integration module with arxiv example

- **Async Support**
	- Add asyncio support for method registration
	- Refactor OpenAPI integration with async registration logic

- **Base Tool Wrapper**
	- Add `BaseToolWrapper` abstract base class
	- Standardize tool wrapper inheritance

### Refactoring

- Reorganize example files structure
- Replace print statements with logger.error
- Enhance base tool wrapper with ABC

### Documentation Improvements

- Add LangChain integration guide
- Update README with LangChain integration documentation

## [0.4.8.post1] - 2025-05-13

### New Features

- **Calculator Enhancements**
	- Add `function_help` and expand `evaluate` capabilities
	- Add utility to fetch static methods

- **Examples**
	- Add OpenAI calculator example

### Documentation Improvements

- Update calculator tool documentation
- Add PyPI version badge to index page

## [0.4.8] - 2025-05-11

### New Features

- **Calculator**
	- Add Python version check for certain functions

- **OpenAPI**
	- Replace heavy openapi dependencies with lightweight ones
	- Simplify spec parsing logic

### Refactoring

- Clean up imports and type annotations

## [0.4.7] - 2025-05-10

### New Features

- **Google Search Tool**
	- Add Google search functionality to websearch hub
	- Add enhanced content extraction methods
	- Add general web search abstraction (`WebSearchGeneral`)

- **MCP Transport**
	- Add support for multiple MCP transport modes (SSE, stdio, streamable-http)
	- Add fastmcp-based math server and client
	- Add diverse transport examples

- **Type Annotations**
	- Add type hinting support for toolregistry

### Refactoring

- Migrate from `mcp` library to `fastmcp`
- Streamline exception handling and tool registration
- Reorganize websearch module structure

### Documentation Improvements

- Update transport methods and tool registry documentation
- Add documentation for websearch modules
- Update MCP integration guide

## [0.4.6.post2] - 2025-04-28

### Bug Fixes

- Conditionally import `fake-useragent` when `python>=3.9` (fixes Python 3.8 compatibility)
- Resolve import compatibility issues in websearch module

## [0.4.6.post1] - 2025-04-28

### New Features

- Add Google-based websearch hub tool
- Unify websearch with `WebSearchGeneral` abstract class

> **Note**: Use 0.4.6.post2 instead — this version has a dependency issue on Python 3.8.

## [0.4.6] - 2025-04-28

### New Features

- **SearXNG Web Search**
	- Add SearXNG-backed websearch hub tool

- **Type System**
	- Replicate OpenAI types with Pydantic in utils

> **Note**: Use 0.4.6.post2 instead — this version has a dependency issue on Python 3.8.

## [0.4.5] - 2025-04-17

### New Features

- **Concurrent Tool Execution**
	- Add concurrent tool execution with `dill` serialization

- **Namespace Separator**
	- Refine namespace separator configuration

## [0.4.4] - 2025-04-16

### New Features

- **Class Registration Method Upgrade**
	- Enhanced class-based tool registration

## [0.4.3] - 2025-04-15

### New Features

- **Calculator Enhanced Features**
	- Add enhanced calculator capabilities

- **File Operations**
	- Add file operations hub tool
	- Refine FileSystem tool

## [0.4.2] - 2025-04-14

### Refactoring

- **Namespace Refactor and Hub of Tools**
	- Refactor namespace handling
	- Introduce hub of tools pattern

## [0.4.1] - 2025-04-12

### New Features

- **Name Normalization**
	- Add name normalization for consistent tool naming

### Refactoring

- Update README softlinks and testing examples for OpenAPI

## [0.4.0] - 2025-04-05

### New Features

- **OpenAPI Support**
	- Add OpenAPI integration for tool registration from OpenAPI specs

### Documentation Improvements

- Enhance docstrings for toolregistry
- Add comprehensive API documentation

## [0.3.1] - 2025-04-04

### New Features

- **Unified Sync & Async Interface**
	- Unify the callable interface for sync and async mode
	- Refine async calling mechanism for MCP

### Documentation Improvements

- Add documentation files and generation script

## [0.3.0] - 2025-04-01

### New Features

- **MCP Tools Support**
	- Add support for MCP SSE tools
	- Add async and sync modes for running tools
	- Add result post-processing for MCP tools
	- Enhance tool management capabilities

### Refactoring

- Improve tool lookup method
- Remove redundant execution methods
- Simplify tool run method result handling

### Documentation Improvements

- Add MCP integration guide and usage examples
- Update installation requirements with MCP details

## [0.2.0] - 2025-04-01

### New Features

- **Parallel Tool Execution**
	- Add parallel execution for tool calls

- **Project Setup**
	- Migrate from `setup.py` to `pyproject.toml`
	- Add version metadata

### Documentation Improvements

- Add Chinese README
- Update example file paths in documentation

## [0.1.0] - 2025-04-01

### Initial Release

- Initial spin-off from the cicada project
- Basic ToolRegistry implementation for managing and executing LLM tool calls
- Core tool registration and execution framework
- Support for Python function tools

---

## Version Notes

### Semantic Versioning

This project follows [Semantic Versioning](https://semver.org/) specification:

- **Major version**: Incompatible API changes
- **Minor version**: Backward-compatible functionality additions
- **Patch version**: Backward-compatible bug fixes

### Change Type Legend

- **New Features** - New functionality or features
- **Refactoring** - Code refactoring without functional changes
- **Bug Fixes** - Error corrections
- **Documentation** - Documentation updates
- **Maintenance** - Maintenance updates
- **Build** - Build system changes

### Getting Updates

To get the latest version, use:

```bash
pip install --upgrade toolregistry
```

### Feedback and Suggestions

If you find any issues or have improvement suggestions, please submit an Issue in our [GitHub repository](https://github.com/Oaklight/ToolRegistry).
