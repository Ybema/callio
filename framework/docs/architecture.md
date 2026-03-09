# Architecture

## Overview

The proposal framework separates framework logic from per-call data.  
Framework code lives at repo root; each proposal call has its own workspace under `calls/<call-name>/`.

```
Pre-Phase               Phase A              Phase B              Phase C
Static context docs     LFA -> scored        WPs -> scored        Full proposal -> scored
PDF/Word -> MD          review report        review reports       final assessment
(call docs, strategy)   (consortium .docx)   (consortium .docx)   (all inputs)
```

## Data Separation

```
framework/
├── calls/
│   ├── _template/
│   └── <source-slug>/
│       └── <call-slug>/
│           ├── call.yaml
│           ├── .env (optional)
│           ├── input/
│           │   ├── call_documents/
│           │   ├── lfa_documents/
│           │   ├── work_packages/
│           │   └── strategy_documents/
│           ├── output/
│           └── snapshots/
├── config/                     # framework-level funding definitions and criteria
├── scripts/                    # framework logic
└── run_*.py                    # CLI entry points
```

`call.yaml` stores per-call settings (`project_name`, `call_id`, `funding_type`, `model`, `phases`).

Call reference format for CLI: `--call <source>/<call>` (e.g. `--call esa/responsible-fishing`).  
Short form `--call <call>` also works when the call name is unique across sources.

## Phase Structure

### Pre-Phase (run_pre_phase.py)

Prepares **static context documents** that do not change between consortium iterations:

- Converts `input/call_documents/` and `input/strategy_documents/` to `*_processed.md`
- Uses MarkItDown (with python-docx fallback). No LLM calls.
- Does **not** touch `input/lfa_documents/` or `input/work_packages/` — those are consortium iteration inputs owned by Phase A and Phase B respectively.

### Phase A (run_phase_a.py)

Owns the **LFA lifecycle** — consortium submits `.docx`, Phase A converts, versions, maps to template, evaluates, and produces feedback. Self-contained (does not use `ProposalFramework`). Two sections:

1. **Document processing**: discovers `.docx` in `calls/<call>/input/lfa_documents/`, converts to versioned Markdown (`*_processed_<timestamp>.md`), maps content onto global template (`templates/input_templates/lfa_template_processed.md`), tracks content hashes to detect changes vs identical resubmissions.
2. **LFA evaluation**: runs `scripts/review_engine/review_engine.py` with 3 LLM calls (one per block). Discovers the latest `*_processed_<timestamp>.md` for review.

Processing logs include `template_mapping` diagnostics per LFA file (matched/unmatched template sections).

Uses `LFAAnalysisProcessor` and `PhaseAProcessor` classes defined inline in `run_phase_a.py`.

### Phase B & C (run_phase_b.py, run_phase_c.py)

Phase B owns the **WP lifecycle** — consortium submits WP `.docx` files in `input/work_packages/`.  
Phase C performs full proposal assessment using all inputs.  
Both read the LFA `.docx` from `input/lfa_documents/` as reference context (not for conversion).  
Route through `scripts/framework.py` -> `ProposalFramework` class.  
Document discovery is call-scoped (`calls/<call>/input/...`).  
See [known-issues.md](known-issues.md) for current integration gaps in B/C.

## Review Engine (Phase A)

Located in `scripts/review_engine/`. Three evaluation blocks, each a single LLM call:

| Block | Weight | Criteria | Evaluates |
|-------|--------|----------|-----------|
| **CA** (Call Alignment) | 30% | CA1–CA6 | Objectives, scope, outcomes, evaluation coverage, completeness, terminology |
| **LC** (Logic Consistency) | 50% | LC1–LC4 | Logical flow, measurable outcomes, activity-outcome linkage, feasibility |
| **CQ** (Content Quality) | 20% | CQ1–CQ3 | Clarity, actionability, professional presentation |

All 13 criteria are routed to LLM evaluation via `criteria.json`. Python evaluators exist (`eval_eligibility`, `eval_temporal`, `eval_duplication`, `eval_readability`) but are not wired into the main flow.

### Scoring

Each criterion scores 0–5. Block subtotals are averaged, then weighted:

```
total = 0.30 × CA_avg + 0.50 × LC_avg + 0.20 × CQ_avg
```

Bands: Outstanding (≥4.5), Strong (≥4.0), Adequate (≥3.5), Needs Work (<3.5).

### Output Artifacts

Each Phase A run produces:
- JSON results with scores, findings, evidence, and cost tracking
- Markdown report
- Word document (.docx)
- Processing log
- Version control snapshot (input hashes + session ID)

Phase A processing logs include `template_mapping` diagnostics per LFA file, so section-level mapping coverage is traceable for each run.

## Key Files

| File | Role |
|------|------|
| `launch.py` | CLI dispatcher for phases A/B/C |
| `run_phase_a.py` | Phase A orchestration (self-contained) |
| `scripts/call_context.py` | Resolves call directories, loads call `.env`, loads `call.yaml` |
| `scripts/framework.py` | `ProposalFramework` controller (Phase B/C) |
| `scripts/review_engine/review_engine.py` | Core evaluation engine |
| `scripts/review_engine/llm_provider.py` | LLM provider with fallback chain |
| `scripts/review_engine/criteria.json` | Criteria → evaluator routing |
| `scripts/review_engine/prompts/` | System prompts for CA, LC, CQ blocks |
| `calls/<call>/call.yaml` | Per-call project metadata and model selection |
| `config/funding_types/horizon_eu.yaml` | Funding type configuration |
