# reference/

Architecture reference and decision records for `toolregistry`.

## Documents

| File | Description |
|------|-------------|
| [architecture.md](architecture.md) | Three-layer architecture overview and source tree |
| [adr-001-llm-subpackage.md](adr-001-llm-subpackage.md) | Why LLM orchestration was consolidated into `llm/` and deprecated shims removed |
| [adr-002-rosetta-delegation.md](adr-002-rosetta-delegation.md) | Delegating all format conversion to llm-rosetta; shim design; Gemini name resolution |
| [adr-003-result-ordering.md](adr-003-result-ordering.md) | Result ordering guarantee for Gemini; why disabled-tool interleaving is a non-issue |

## ADR Format

Each ADR records: **Context** (why the decision was needed), **Decision** (what was chosen),
**Consequences** (trade-offs accepted).
