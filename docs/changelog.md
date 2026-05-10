---
title: Changelog
summary: Version history and change records for the ToolRegistry project
description: Detailed documentation of all feature updates, fixes, and improvements in ToolRegistry since version 0.1.0
keywords: changelog, version history, release notes, changes
author: Oaklight
---

# Changelog

This page documents all notable changes to the ToolRegistry project since the first release.

## Unreleased

### New Features

- **Admin Panel Enrichment** ([#133](../../pull/133))
    - Enrich tool API responses with full metadata: `ToolTag` badges, `ToolMetadata` fields (`is_async`, `timeout`, `locality`, `think_augment`, `defer`, etc.), and permission evaluation results
    - Add `GET /api/tools/{name}/permissions` endpoint for per-tool permission policy evaluation
    - Add tool detail modal in Web UI with tabbed view (Schema, Metadata, Permissions)
    - Add system `ToolTag` badges (color-coded) and custom tag pills in tool rows
    - Replace single-letter meta icons (`T`, `D`) with full-word badges (`think`, `defer`, `async`, `local`/`remote`)
    - Add search and tag-based filtering in the tools panel
    - Improve mobile responsive layout with horizontal scroll and hidden reason column on small viewports
    - Add 7 new tests covering enriched API and permissions endpoint

- **Runtime Control for think_augment and defer** ([#134](../../issues/134), [#135](../../pull/135))
    - Add `update_tool_metadata(tool_name, **kwargs)` and `update_namespace_metadata(namespace, **kwargs)` methods to `ToolRegistry` for runtime mutation of `think_augment` and `defer` fields
    - Whitelist approach: only `think_augment` and `defer` are allowed for runtime modification (prevents unsafe mutations of execution-critical fields)
    - Add `PATCH /api/tools/{name}/metadata` and `PATCH /api/namespaces/{ns}/metadata` REST API endpoints
    - Add interactive checkboxes in Web UI for `think_augment` and `defer` in dedicated columns at both tool and namespace levels
    - Gray out Think checkbox for tools with native `thought` parameter; expose `has_native_thought` in `get_tools_status()` API
    - Namespace-level checkboxes apply to all tools within the namespace
    - Add `METADATA_UPDATE` event type to `ChangeEventType` enum
    - Add 7 new tests for metadata update endpoints

- **Admin Panel i18n** ([#137](../../pull/137))
    - Add bilingual support (English / Chinese) to the admin Web UI
    - Language switcher dropdown in the header with `localStorage` persistence
    - All static text uses `data-i18n` attributes; dynamic text uses `t(key, params)` translation function
    - Covers all tabs, table headers, buttons, filters, toast messages, modal dialogs, and empty states
    - Instant language switching with automatic re-rendering of the active tab
    - Simplify connection status to dot-only indicator with hover tooltip

### Refactoring

- **Remove PyYAML and jsonref Dependencies from OpenAPI** ([#140](../../pull/140))
    - Replace `PyYAML` with zerodep vendored YAML parser in OpenAPI integration
    - Replace `jsonref` with zerodep vendored `jsonschema.resolve_refs()` for `$ref` resolution
    - Remove all external dependencies from the `openapi` optional extra
    - Vendor `zerodep/jsonschema` v0.2.0 with full JSON Pointer (RFC 6901) support

- **Remove httpx Core Dependency** ([#139](../../pull/139))
    - Replace `httpx` with zero-dependency vendored HTTP client for core OpenAPI functionality
    - Rename `HttpxClientConfig` → `HttpClientConfig` (old name preserved as deprecated alias with `DeprecationWarning`)
    - Move `httpx` from core `dependencies` to `[mcp]` optional extras (MCP integration still requires it)
    - No changes to public API behavior — `HttpClientConfig` accepts the same constructor arguments

- **Admin Panel Async Migration** ([#136](../../pull/136))
    - Migrate admin panel from stdlib `http.server` to zerodep's async `httpserver` module (vendored via `zerodep add httpserver`)
    - Replace `BaseHTTPRequestHandler` with decorator-based routing (`@app.get`, `@app.post`, `@app.patch`, `@app.delete`)
    - Unify authentication and CORS handling via `before_request`/`after_request` middleware
    - Run `asyncio.new_event_loop()` in background thread instead of `HTTPServer.serve_forever()`
    - Remove `AdminRequestHandler` class (internal implementation detail replaced by `setup_routes()`)
    - Simplify `TokenAuth` to pure token management — HTTP enforcement moved to middleware
    - Exclude `_vendor/` from ruff, ty, and complexipy checks in `pyproject.toml`

## [0.8.0] - 2026-05-02

### New Features

- **Declarative Tool Config Loader** ([#120](../../issues/120), [#122](../../pull/122))
    - Add `toolregistry.config` module for parsing JSONC/YAML config files into typed frozen dataclasses
    - Support three tool source types: `python` (class/module), `mcp` (stdio/sse/streamable-http), `openapi` (with auth)
    - Vendor `zerodep/jsonc` and `zerodep/yaml` into `_vendor/` package for zero external dependencies
    - `transport: "http"` accepted as alias for `"streamable-http"`
    - Backward-compatible with legacy `{"module": "x", "class": "Y"}` config format
    - Denylist/allowlist mode with per-source enable/disable and `token_env` environment variable resolution

### Refactoring

- **Integration Package Restructuring**
    - Moved `mcp/`, `openapi/`, `langchain/`, `native/` integration packages under a new `integrations/` parent package
    - New canonical import paths: `toolregistry.integrations.mcp`, `toolregistry.integrations.openapi`, `toolregistry.integrations.langchain`, `toolregistry.integrations.native`
    - Old import paths (`toolregistry.mcp`, `toolregistry.openapi`, etc.) preserved as deprecation shims that emit `DeprecationWarning`; these shims will be removed in a future release
    - Public `ToolRegistry` API methods (`register_from_mcp()`, `register_from_openapi()`, etc.) are unchanged

- **Consolidate Internal Modules**
    - Consolidate mixin modules into `_mixins/` package
    - Consolidate zero-dependency vendored modules into `_vendor/` package
    - Use subpackage-level imports for llm-rosetta ToolOps

### Bug Fixes

- **Improve error message for classes with required constructor args** ([#127](../../issues/127))
    - Provide a clearer error message when `register_from_class()` is called with a class whose constructor requires arguments

### Maintenance

- Bump `llm-rosetta` minimum to `>=0.5.1,<0.6.0`

## [0.7.0] - 2026-04-06

### New Features

- **Anthropic & Gemini Schema Format Support** ([#55](../../issues/55), [#88](../../pull/88))
    - Add `"anthropic"` and `"gemini"` as valid `api_format` values for `get_schemas()` and `get_json_schema()`
    - All schema conversion is powered by [llm-rosetta](https://pypi.org/project/llm-rosetta/), which also sanitizes JSON Schema keywords unsupported by each format
    - Add `llm-rosetta>=0.2.6` as a core dependency
    - Support parsing Anthropic `tool_use` blocks and Gemini `functionCall` parts in `ToolCall.from_tool_call()`
    - Add `build_assistant_message()` and `build_tool_response()` support for `"anthropic"` and `"gemini"` formats

- **Permission System** ([#79](../../issues/79), [#80](../../issues/80), [#81](../../issues/81), [#82](../../issues/82))
    - **ToolTag & ToolMetadata** ([#80](../../issues/80), [#84](../../pull/84)): Add `ToolTag` enum (READ_ONLY, DESTRUCTIVE, NETWORK, FILE_SYSTEM, SLOW, PRIVILEGED) and `ToolMetadata` model with execution hints (`is_async`, `is_concurrency_safe`, `timeout`) and classification tags
    - **Permission Handler Protocol** ([#81](../../issues/81), [#85](../../pull/85)): Add `PermissionHandler` and `AsyncPermissionHandler` runtime-checkable protocols for tool authorization; add `PermissionRequest` and `PermissionResult` types; add `set_permission_handler()`, `get_permission_handler()`, `remove_permission_handler()` methods on ToolRegistry
    - **Permission Rule Engine** ([#82](../../issues/82), [#86](../../pull/86)): Add `PermissionRule` and `PermissionPolicy` models with first-match-wins evaluation; add `set_permission_policy()`, `get_permission_policy()`, `remove_permission_policy()` methods; add five built-in rules (`ALLOW_READONLY`, `ASK_DESTRUCTIVE`, `DENY_PRIVILEGED`, `ASK_NETWORK`, `ASK_FILE_SYSTEM`); permission checks integrated into `execute_tool_calls()`
    - Add `PERMISSION_DENIED` and `PERMISSION_ASKED` event types to the callback mechanism

- **ToolMetadata Locality** ([#89](../../issues/89))
    - Add `locality` field to `ToolMetadata` with values `"local"`, `"remote"`, or `"any"` (default)
    - Enables classification of tools by execution location for filtering and scheduling

- **Tag-Based Filtering and Stable Sorting** ([#83](../../issues/83))
    - Add `tags`, `exclude_tags`, and `sort` parameters to `get_schemas()`
    - Enables prompt-level tool filtering and deterministic ordering, reducing token waste and improving prompt cache hit rates with large tool pools

- **Persistent Connections for MCP and OpenAPI** ([#90](../../issues/90))
    - MCP integrations now maintain persistent connections across tool calls via `MCPConnectionManager`
    - OpenAPI integrations reuse `httpx` client sessions for connection pooling
    - Add `ToolRegistry.close()` / `close_async()` for explicit resource cleanup
    - Add context manager support: `with ToolRegistry() as reg:` and `async with ToolRegistry() as reg:`

- **ToolDiscoveryTool for Progressive Tool Disclosure** ([#108](../../pull/108), [#114](../../pull/114), [#118](../../pull/118))
    - Add `ToolDiscoveryTool` class with dual-mode discovery: exact name match (returns full schema) and BM25F fuzzy search
    - Vendor zerodep `SparseIndex` as `_sparse_search.py` (zero external dependencies)
    - Add `ToolMetadata.defer` field to mark tools for deferred loading (excluded from initial prompt)
    - Add `ToolMetadata.search_hint` field for free-form search keywords and synonyms
    - Index tool name, description, tags, parameter names, and search_hint with configurable field weights
    - Add `enable_tool_discovery()` / `disable_tool_discovery()` to register `discover_tools` as a first-class callable tool in the registry
    - Add `get_deferred_summaries()` to get lightweight name + first-sentence description for deferred tools (for system prompt injection)
    - Add `include_deferred` parameter to `get_schemas()` — set to `False` to exclude deferred tools from initial schemas
    - Discovery results for deferred tools include the full tool `schema` so LLMs can call them immediately after discovery
    - Auto-rebuild discovery index via ChangeCallback when tools are registered or unregistered
    - Add `ToolRegistry(tool_discovery=True)` constructor parameter for convenience

- **Think-Augmented Function Calling** ([#49](../../pull/49))
    - Inject a `thought` string property into tool parameter schemas so LLMs can include chain-of-thought reasoning when calling tools
    - **Off by default** — enable globally via `ToolRegistry(think_augment=True)` or at runtime with `enable_think_augment()` / `disable_think_augment()`
    - Per-tool override via `ToolMetadata.think_augment` (`None`=follow registry, `True`=force on, `False`=force off)
    - The property is automatically stripped before execution
    - Native `thought` parameters on functions are preserved (not overridden)
    - Covers all integration paths (MCP, OpenAPI, LangChain, native)
    - Reference: [arXiv:2601.18282](https://arxiv.org/abs/2601.18282)

- **Result Size Management**
    - Add `ToolMetadata.max_result_size` and `ToolRegistry(default_max_result_size=...)` for automatic result truncation
    - Two strategies: `HEAD` (keep first N chars) and `HEAD_TAIL` (keep first and last portions, default)
    - Full results automatically persisted to temporary files before truncation
    - Add `truncate_result()` function and `TruncatedResult` dataclass for programmatic use

### Bug Fixes

- **Gemini Tool Call ID and Name Resolution**
    - Fix `build_tool_call_messages` to align tool call IDs by position: IDs from `tool_responses` (produced by `execute_tool_calls`) are remapped onto the converted `ToolCall` objects so assistant and tool messages reference the same IDs
    - Pass `tool_calls` to `build_tool_response` for Gemini `functionResponse.name` resolution
    - Previously, Gemini `functionResponse.name` showed a random UUID instead of the function name because `convert_tool_calls()` was called twice independently, generating different IDs each time

### Refactoring

- **Pluggable Executor Backend Architecture** ([#78](../../issues/78))
    - Replace monolithic `Executor` class with a pluggable `executor/` package
    - New `ExecutionBackend` Protocol and `ExecutionHandle` ABC for backend extensibility
    - `ThreadBackend`: thread-pool executor with cooperative cancellation via `ExecutionContext`
    - `ProcessPoolBackend`: process-pool executor with cloudpickle serialization
    - `ToolMetadata.timeout` enforcement at the backend level
    - `ToolMetadata.is_concurrency_safe` controls sequential vs parallel batching
    - Tool functions can accept `_ctx: ExecutionContext` for cooperative cancellation and progress reporting

- **Mixin-Based ToolRegistry Architecture** ([#94](../../issues/94))
    - Split `tool_registry.py` (1459 lines) into 7 focused mixin classes (454 lines remaining)
    - Mixins: `ChangeCallbackMixin`, `NamespaceMixin`, `EnableDisableMixin`, `RegistrationMixin`, `PermissionsMixin`, `ExecutionLoggingMixin`, `AdminMixin`
    - Public API unchanged; cooperative `__init__` via MRO chain

- **Public API Rename** ([#107](../../issues/107))
    - `get_tools_json()` → `get_schemas()` on `ToolRegistry`
    - `recover_tool_call_assistant_message()` → `build_tool_call_messages()` on `ToolRegistry`
    - `recover_assistant_message()` → `build_assistant_message()` (module-level)
    - `recover_tool_message()` → `build_tool_response()` (module-level)
    - `with_namespace` parameter renamed to `namespace` in all `register_from_*` methods (old name still accepted with deprecation warning)
    - `set_execution_mode()` renamed to `set_default_execution_mode()` (old name deprecated)
    - `list_all_tools()` merged into `list_tools(include_disabled=True)` (old name deprecated)
    - Add `"openai-chat"` as canonical API format name; deprecate `"openai"` and `"openai-chatcompletion"`
    - All old names remain as deprecated aliases with `DeprecationWarning`

## [0.6.1] - 2026-03-22

### Bug Fixes

- **Fix `**kwargs` leaking into tool JSON Schema**: `_generate_parameters_model()` now skips `VAR_POSITIONAL` (`*args`) and `VAR_KEYWORD` (`**kwargs`) parameters, preventing them from appearing as required fields in the generated schema. This fixes MCP tool calls failing with validation errors when tool functions use `**kwargs`.

### Maintenance

- Switch `pyproject.toml` to dynamic versioning (read from `toolregistry.__version__`), consistent with toolregistry-server and toolregistry-hub.

## [0.6.0] - 2026-03-18

### ⚠️ Breaking Changes

- **Upgrade Minimum Python Version to 3.10** ([#74](../../issues/74))
	- Update `requires-python` from `>=3.8` to `>=3.10`
	- Python 3.8 and 3.9 are no longer supported
	- This aligns with Python 3.9 EOL and MCP SDK requirements

### New Features

- **Admin Panel** (Phase 7)
	- Built-in web-based administration interface for ToolRegistry
	- Execution logging with ring buffer storage
	- REST API for tool and namespace management (12 endpoints)
	- Web UI with Anthropic-style minimalist design
	- Token-based authentication for remote access
	- State export/import functionality
	- New methods: `enable_admin()`, `disable_admin()`, `get_admin_info()`
	- New methods: `enable_logging()`, `disable_logging()`, `get_execution_log()`
	- New classes: `AdminServer`, `AdminInfo`, `TokenAuth`
	- New classes: `ExecutionLog`, `ExecutionLogEntry`, `ExecutionStatus`

- **Callback Mechanism** ([#68](../../issues/68))
	- Added `on_change()` and `remove_on_change()` methods for monitoring registry changes
	- Supports callbacks for tool registration, removal, enable/disable events

- **Observability API**
	- Added `get_tools_status()` method for inspecting tool states at runtime

### Refactoring

- **Replace `dill` with `cloudpickle`** ([#76](../../issues/76))
	- Swap `dill.dumps`/`dill.loads` with `cloudpickle.dumps`/`pickle.loads` in executor
	- Deserialization now uses stdlib `pickle`, so future remote executor targets only need Python stdlib
	- Replace `dill>=0.4.0` dependency with `cloudpickle>=3.0.0` in pyproject.toml

- **Modernize Type Annotations for Python 3.10+**
	- Replaced `Union[X, Y]` with `X | Y` syntax
	- Replaced `Optional[X]` with `X | None`
	- Replaced `List`, `Dict`, `Tuple` with lowercase `list`, `dict`, `tuple`

### Maintenance

- Remove `fake-useragent` dependency (no longer used after toolregistry-hub split)
- Remove legacy `./docs` directory (migrated to `docs_en`/`docs_zh` worktrees)
- Add Python 3.10/3.11/3.12/3.13 classifiers to pyproject.toml

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
	- Add `list_tools(include_disabled=True)` for admin panel use (returns all tools including disabled)
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
