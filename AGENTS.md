# AGENTS.md — ToolRegistry

> Context file for AI coding assistants. Symlinked as `CLAUDE.md`.

## What this project is

ToolRegistry is a **protocol-agnostic tool management library** for
function-calling LLMs. It unifies tool registration, schema generation, and
execution across multiple LLM providers (OpenAI, Anthropic, Gemini) and
external ecosystems (MCP, OpenAPI, LangChain).

This is the **core** package in a three-package ecosystem:

| Package | Role | Depends on |
|---------|------|------------|
| `toolregistry` (this) | Core library: `Tool` model, `ToolRegistry`, client integrations | — |
| `toolregistry-server` | Server infrastructure: `RouteTable`, OpenAPI/MCP adapters, auth, CLI | `toolregistry` |
| `toolregistry-hub` | Tool implementations + default server configuration | `toolregistry-server` |

Downstream packages are notified on release via `notify-downstream.yml`.

## Architecture

ToolRegistry is organized around a central `ToolRegistry` class composed of
7 orthogonal mixins:

| Mixin | File | Responsibility |
|-------|------|----------------|
| RegistrationMixin | `_mixins/registration.py` | Register/unregister tools from functions, classes, MCP, OpenAPI |
| EnableDisableMixin | `_mixins/enable_disable.py` | Enable/disable tools, track reasons, metadata updates |
| NamespaceMixin | `_mixins/namespace.py` | Namespace prefixing, merge, spinoff sub-registries |
| PermissionsMixin | `_mixins/permissions.py` | Tag-based permission policies, sync/async handlers |
| ExecutionLoggingMixin | `_mixins/logging.py` | In-memory call history (name, args, result, duration) |
| AdminMixin | `_mixins/admin.py` | Web admin panel lifecycle |
| ChangeCallbackMixin | `_mixins/callbacks.py` | Event subscriptions (register, enable, error, etc.) |

Key standalone modules:

| Module | Purpose |
|--------|---------|
| `tool.py` | `Tool`, `ToolMetadata`, `ToolTag`, `TOOLCALL_REASON_PROPERTY` |
| `tool_registry.py` | `ToolRegistry` (composes the 7 mixins) |
| `tool_wrapper.py` | Tool wrapper base classes |
| `parameter_models.py` | JSON Schema generation from Python signatures |
| `schema_diff.py` | Compatible/breaking classification of schema changes |
| `events.py` | ChangeEvent types |
| `errors.py` | Validation and schema error types |
| `netpolicy.py` | Public outbound address policy (`_netpolicy.py` implements it) |
| `_names.py` | Tool-name normalization, namespace rules, registration filter |
| `_http.py` | Base-URL HTTP clients and `HttpClientConfig` |
| `_serialisation.py` | Tool-result JSON encoding |
| `_validation.py` | Shared metadata field validation |
| `_async_runtime.py` | Persistent event loop for sync→async bridging |
| `_warnings.py` | Warning attribution to the caller's frame |
| `llm/` | Tool discovery, result truncation, provider tool calls, Rosetta bridge |
| `runtimes/` | PTC (Programmatic Tool Calling) bridge |
| `admin/` | HTTP server, REST handlers, extension contract, source hook, UI |
| `executor/` | Thread/process pool execution backends |
| `permissions/` | Policy engine, handler protocol, built-in rules |
| `config/` | Declarative JSONC/YAML config loader |
| `integrations/` | Native, MCP, OpenAPI, LangChain integration packages |

## Repository layout

```
src/toolregistry/
├── __init__.py              # Exports, __version__
├── tool.py                  # Tool, ToolMetadata, ToolTag
├── tool_registry.py         # ToolRegistry (composes 7 mixins)
├── tool_wrapper.py          # Tool wrapper base classes
├── parameter_models.py      # JSON Schema from signatures
├── schema_diff.py           # Schema compatibility classification
├── events.py                # ChangeEvent types
├── errors.py                # Validation and schema errors
├── netpolicy.py             # Public outbound address policy
├── utils.py                 # Compatibility surface (re-exports the helpers below)
├── _names.py                # Tool-name rules + registration filter
├── _http.py                 # Base-URL HTTP clients and config
├── _serialisation.py        # Tool-result JSON encoding
├── _validation.py           # Shared metadata field validation
├── _async_runtime.py        # Sync→async bridge event loop
├── _warnings.py             # Caller-attributed warnings
├── _netpolicy.py            # Outbound address policy implementation
├── _mixins/                 # 7 mixin classes (see Architecture)
├── llm/                     # Discovery, truncation, tool calls, Rosetta bridge
├── runtimes/                # PTC (Programmatic Tool Calling) bridge
├── admin/                   # Web admin panel (server, handlers, extensions, UI)
│   ├── server.py            # Async HTTP server
│   ├── handlers.py          # REST API endpoints
│   ├── extensions.py        # Admin extension contract
│   ├── source_hook.py       # Source persistence and status hook
│   ├── admin.html           # Single-file SPA (i18n: EN/ZH)
│   ├── execution_log.py     # Call history
│   ├── auth.py              # Token auth and failure limiter
│   └── static.py            # Asset serving
├── executor/                # Pluggable execution backends
├── permissions/             # Policy engine + built-in rules
├── config/                  # JSONC/YAML config loader
├── integrations/            # MCP, OpenAPI, LangChain, native
└── _vendor/                 # Vendored zero-dep modules (DO NOT EDIT)

tests/                       # pytest suite
examples/                    # Usage examples
docs_en/, docs_zh/           # Documentation (git worktrees, orphan branches)
```

## Setup and commands

```bash
conda activate toolregistry
pip install -e ".[dev,test,mcp]"
pre-commit install
```

Run `make help` for all targets. Key ones:

```bash
make lint          # ruff check + ty check + complexipy
make fmt           # ruff check --fix + ruff format
make test          # pytest tests/ -v
make build         # python -m build
make push          # twine upload
```

Tooling config (ruff, ty, complexipy) lives in `pyproject.toml`.

## Definition of done

1. `pre-commit run --all-files` passes (ruff, ruff-format, ty, complexipy)
2. `pytest tests/ -v` passes — run from the repo root, not `pytest` bare
3. New code has tests in `tests/`
4. Google-style docstrings on public APIs; comments in English
5. No manual edits to `_vendor/` — update upstream in zerodep, re-vendor via CLI
6. `ruff format` covers both `src/` **and** `tests/`

## Workflow

- **Branch from master**, open a PR, require CI green before merge.
- **Merge strategy: rebase** — keep commits atomic and well-messaged.
- Branch naming: `feature/...`, `fix/...`, `refactor/...`, `test/...`, `docs/...`
- Never force-push to `master` unless the user explicitly requests it.
- **No AI co-author tags in commits.** Do not add `Co-authored-by` lines for AI
  tools in git commit messages. Disclose AI usage in PR descriptions instead.

## Documentation

User-facing docs live on **orphan branches** (`docs_en`, `docs_zh`), mounted
as git worktrees at `./docs_en/` and `./docs_zh/`. Built with zensical.

```bash
# Edit docs in-place (worktrees already mounted)
cd docs_en/docs/
# Commit and push inside the worktree
```

### When to update docs worktrees

Update `docs_en/` and `docs_zh/` whenever any of the following happens:

- **New public API added or signature changed**: update the relevant API
  reference pages in both languages.
- **Behavior change or bug fix affecting documented functionality**: update
  affected guide/reference pages.
- **Changelog-worthy change merged to main branch**: update
  `docs_en/docs/changelog.md` and `docs_zh/docs/changelog.md` under the
  `[Unreleased]` section. Follow the [Keep a Changelog](https://keepachangelog.com/)
  format. Entries should cover: features, enhancements, bug fixes,
  breaking changes, and infrastructure.
- **Release published**: move `[Unreleased]` entries into a new versioned
  section in both changelogs, then create a GitHub Release:
  ```bash
  gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
  ```
  Release notes should mirror the versioned changelog section (in English).
  Include an installation snippet and a "Full Changelog" compare link.

### Cross-language consistency (enforced)

**Both language versions must be updated in the same task/agent run.** Never
update only one language and leave the other for later. The workflow is:

1. Make changes to `docs_en/` first (English is the source of truth).
2. In the same task, apply equivalent changes to `docs_zh/` before committing.
3. Commit and push both worktrees before the task is considered done.

Splitting the two languages across separate agents or separate sessions is not
allowed — it leads to drift and missed pages.

### Cross-language consistency (enforced)

**Both language versions must be updated in the same task/agent run.** Never
update only one language and leave the other for later. The workflow is:

1. Make changes to `docs_en/` first (English is the source of truth).
2. In the same task, apply equivalent changes to `docs_zh/` before committing.
3. Commit and push both worktrees before the task is considered done.

Splitting the two languages across separate agents or separate sessions is not
allowed — it leads to drift and missed pages.

Commits in doc worktrees use `PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit` since
those branches have no `.pre-commit-config.yaml`.

## Escalation

- Schema generation mismatch → check `llm/_rosetta.py` and `llm-rosetta` version
- Rosetta compat failure → see `rosetta-compat.yml` CI, check upstream release
- `_vendor/` issues → never fix in-place; update in zerodep repo, re-vendor
- Pre-existing CI failure (complexipy on `_update_config`) → known, not blocking
- Test failure after 3 attempts → stop, report full output
- Never: delete files to fix errors, skip tests, modify `_vendor/` directly

## Files to never edit

- `src/toolregistry/_vendor/**` — vendored from zerodep, managed via `zerodep` CLI
- `docs_en/`, `docs_zh/` — separate git branches, edit inside the worktree only
