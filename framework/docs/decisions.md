# Decision Log

Lightweight record of key architectural and operational decisions.

---

### 2026-03-09 — Introduce LFA iteration loop and Slack integration

**Context:** The existing iteration cycle required manually editing the LFA `.docx`, converting it, and re-running Phase A. There was no structured mechanism for the moderator to edit the LFA between runs without overwriting Phase A outputs, and no team-facing interface for discussion or feedback collection.

**Decision:** Introduce two new concepts:

1. **LFA iteration loop** — a single editable file `input/lfa_documents/lfa_iteration_input.md` that the moderator edits in Cursor between Phase A runs. Phase A's review step already prefers `output/phase_a/lfa_restructured/lfa_structured.md` when it exists; `sync_lfa_draft.py` archives the old version, copies the draft there, and re-runs Phase A. No `.docx` round-trip needed after the first run.

2. **Slack integration** — dedicated `#callio-{call-slug}` channels. Nina (AI assistant, `groupPolicy: open`) responds to all messages. `sync` posts `sync_lfa_draft.py` output back to the channel. `start discussion` loads the full call context and opens an interactive LLM-assisted session (backed by `run_discussion.py`).

**Key design principles:**
- `lfa_iteration_input.md` is always input; Phase A outputs are always regenerated. No file serves both roles.
- The Slack file is a read-only team view; source of truth is the filesystem.
- `sync_lfa_draft.py` archives before overwriting, so every version of `lfa_structured.md` is recoverable from `output/discussions/lfa_structured_archive_*.md`.
- Phase B and C are only run once the LFA is solid (Phase A scores acceptable). The iteration loop is Phase A only.

**Files added:** `init_lfa_draft.py`, `sync_lfa_draft.py`, `templates/discussion/system_prompt.md`, `scripts/discussion_engine.py`, `run_discussion.py`

**Files updated:** `README.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/deployment.md`

---

### 2026-03-09 — Add smart context sync for pipeline phases

**Context:** Teams add new call/strategy context throughout iterative proposal work, but had to manually decide whether to run pre-phase before Phase A/B/C. Re-running pre-phase also reprocessed unchanged files and repeated LLM synthesis work.

**Decision:** Add hash-based context synchronization with a manifest at `output/pre_phase/.context_manifest.json`. Pipeline runs that include `phase_a`, `phase_b`, or `phase_c` now run context sync automatically before step execution. Only new/changed/removed static context inputs are reprocessed.

**Implementation details:**
- Added `orchestrator/context_sync.py` with scan/diff/sync logic for `input/call_documents/` and `input/strategy_documents/`.
- Updated `orchestrator/runner.py` to trigger sync automatically before non-pre steps.
- Updated `run_pre_phase.py` to read/write context manifest and skip conversion for unchanged files.
- Expanded compiled context synthesis to include both call and strategy documents, with clear separation in synthesis prompt.

**Files:** `orchestrator/context_sync.py`, `orchestrator/runner.py`, `run_pre_phase.py`, `AGENTS.md`

---

### 2026-03-08 — Enforce source-nested call directory convention

**Context:** Watch handoff was run twice against ESA/RVO/Forskningsradet sources. The first run placed 145 call scaffolds flat under `calls/<call-slug>/` (no source nesting). A later run correctly nested them under `calls/<source-slug>/<call-slug>/`. This created duplicates and a chaotic mix of sources at the root level.

**Decision:** Enforce the canonical path `calls/<source-slug>/<call-slug>/` for all calls. Flat root-level call directories are not permitted. Manual calls use the funding body as source slug (e.g. `horizon-eu/seabridge`). The existing `call_context.py` glob fallback resolves short names (`--call responsible-fishing`) when unambiguous.

**Implementation:**
- Moved `esa-responsible-fishing/` to `esa/responsible-fishing/` (preserved all Phase A outputs).
- Moved `seabridge/` to `horizon-eu/seabridge/`.
- Removed 145 empty flat Watch scaffolds and `test-responsible-fishing-pilot/`.
- Removed 12 non-call entries from nested source folders (news articles, events, job vacancies, navigation pages).
- Fixed `framework_handoff.py` to quote `project_name` in generated `call.yaml` (colons in titles broke YAML parsing).
- Added `scripts/list_calls.py` for call workspace management.
- Updated `AGENTS.md` and `docs/architecture.md`.

**Files:** `calls/`, `watch/backend/app/services/framework_handoff.py`, `scripts/list_calls.py`, `AGENTS.md`, `docs/architecture.md`

---

### 2026-03-04 — Separate static context (pre-phase) from consortium iteration inputs (Phase A/B)

**Context:** An earlier change added LFA document discovery to `run_pre_phase.py`, but LFA documents are consortium iteration inputs (they change each review cycle). Pre-phase should only prepare static context that doesn't change between iterations.

**Decision:** Revert LFA handling from pre-phase. Pre-phase converts only static context documents (`call_documents`, `strategy_documents`). Phase A owns the complete LFA lifecycle: `.docx` conversion, timestamped versioning, template mapping, hash-based dedup, and LLM evaluation. Phase B owns the WP lifecycle. Phase B/C read raw `.docx` from `lfa_documents` as reference context only.

**Implementation details:**
- Removed `lfa_documents` discovery, template-mapping code, and related helpers from `run_pre_phase.py`.
- Phase A retains full LFA processing: versioned `*_processed_<timestamp>.md`, template mapping onto global `templates/input_templates/lfa_template_processed.md`, content hash dedup, and `template_mapping` diagnostics.
- Phase A auto-creates missing output directories (`processing_logs`, `review_results`).

**Files:** `run_pre_phase.py`, `run_phase_a.py`, `docs/architecture.md`, `docs/deployment.md`, `docs/decisions.md`

---

### 2026-03-04 — Keep LFA template global; map call LFA into template structure

**Context:** LFA template files were drifting into call workspaces. That blurred the line between reusable framework templates and call-specific source documents, and made it harder to guarantee a consistent single source of truth for downstream phases.

**Decision:** Keep reusable LFA template ownership at framework level (`templates/input_templates/lfa_template_processed.md`). Treat call-level LFA files in `calls/<call>/input/lfa_documents/` as source content only. During Phase A processing, map call-specific LFA content onto the global template structure before writing call-local versioned markdown outputs.

**Implementation details:**
- `run_phase_a.py` maps `lfa_document` content to the global template and stores `template_mapping` diagnostics in processing logs.
- Phase A auto-creates missing `output/phase_a/processing_logs` and `output/phase_a/review_results` directories.

**Files:** `run_phase_a.py`, `docs/architecture.md`, `docs/deployment.md`

---

### 2026-03-03 — Switch LLM provider default from Cursor to OpenAI

**Context:** On the SSH deployment server, the Cursor CLI availability check (`cursor status`) passes, but `cursor agent --print` hangs for 180 seconds per call. With 3 evaluation blocks, Phase A took ~10 minutes instead of ~45 seconds.

**Decision:** Changed `preferred_provider` from `"cursor"` to `"openai"` in both `llm_provider.py` (class default) and `review_engine.py` (call site). Cursor CLI remains as fallback.

**Files:** `scripts/review_engine/llm_provider.py`, `scripts/review_engine/review_engine.py`

---

### 2026-03-03 — Add load_dotenv() to all entry points

**Context:** The `.env` file was never loaded into the environment. `OPENAI_API_KEY` was not available to the OpenAI client unless manually exported in the shell.

**Decision:** Added `from dotenv import load_dotenv` and `load_dotenv()` at the start of `main()` in all runner scripts. The `python-dotenv` package was already installed as a transitive dependency.

**Files:** `launch.py`, `run_pre_phase.py`, `run_phase_a.py`, `run_phase_b.py`, `run_phase_c.py`

---

### Pre-existing — All criteria routed to LLM

**Context:** The review engine has a `criteria.json` routing table that can send individual criteria to either `"llm"` or `"python"` evaluators. Python evaluators exist for eligibility (CA5), temporal completeness (LC4), duplication (LC7), and readability (CQ1).

**Decision:** All 13 criteria (CA1–CA6, LC1–LC4, CQ1–CQ3) are set to `"llm"`. The Python evaluators are kept in the codebase but unused. This prioritizes evaluation quality over cost — each criterion gets full LLM context.

**File:** `scripts/review_engine/criteria.json`

---

### Pre-existing — Phase A self-contained, Phase B/C via ProposalFramework

**Context:** Phase A grew organically with its own processor classes (`PhaseAProcessor`, `LFAAnalysisProcessor`) defined inline in `run_phase_a.py`. Phases B and C were later built on top of `scripts/framework.py` (`ProposalFramework` class).

**Decision:** Two parallel execution paths coexist. Phase A is self-contained (~1160 lines). Phases B/C delegate to `ProposalFramework` which manages config loading, document processing, and output generation.

**Implication:** Changes to Phase A's processing logic don't propagate to B/C and vice versa.

---

### Pre-existing — MarkItDown as primary document converter

**Context:** Document conversion needed to handle PDF, Word, Excel, and PowerPoint with Markdown output suitable for LLM consumption.

**Decision:** Microsoft's MarkItDown (`markitdown[all]`) is the primary converter. `python-docx` is kept as fallback for Word documents. Documented in `reference/markitdown_guide.md`.
