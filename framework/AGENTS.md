# Agent Instructions for Proposal Framework

Apply these rules to every session in this repository.

## New Project/Call Creation

When the user asks to create a new project or call workspace:

1. Use the generator script (do not create folders manually unless asked):
   - `python3 scripts/create_call.py <call-name> --source <source-slug>`
2. Populate optional values when provided by user:
   - `--project-name`
   - `--call-id`
   - `--funding-type`
   - `--model`
3. Confirm the resulting structure exists under:
   - `calls/<source-slug>/<call-name>/`
4. Keep framework logic in repo root and all project data inside `calls/<source-slug>/<call-name>/`.

## Call Listing

Use `python3 scripts/list_calls.py` to inspect call workspaces:
- `--active` shows only calls with phase run output
- `--source esa` filters by source
- `--json` for machine-readable output

## Run Commands

Always run phase commands with `--call` using `<source>/<call>` or just `<call>` (auto-resolved):

- `python3 run_pre_phase.py --call esa/responsible-fishing`
- `python3 run_phase_a.py --call esa/responsible-fishing --verbose`
- `python3 launch.py A --call esa/responsible-fishing`
- `python3 run_pipeline.py --call esa/responsible-fishing --only phase_a`

`run_pipeline.py` now auto-syncs pre-phase context before phases A/B/C.
You do not need to decide manually whether pre-phase must run first.

Short form also works when the call name is unique across sources:
- `python3 launch.py A --call responsible-fishing`

## Data Separation

- Do not place project-specific inputs in root `input/`.
- Do not write run outputs to root `output/` for new runs.
- Use `calls/<source>/<call>/input`, `calls/<source>/<call>/output`, and `calls/<source>/<call>/snapshots`.
- Canonical path pattern: `calls/<source-slug>/<call-slug>/`

## Phase Responsibilities

- **Pre-phase**: static context only (`call_documents/`, `strategy_documents/`). Does NOT process `lfa_documents/` or `work_packages/`.
- **Context sync**: before `phase_a`/`phase_b`/`phase_c` pipeline runs, the framework performs hash-based sync on static context files and only reprocesses changed inputs.
- **Phase A**: owns LFA lifecycle. Converts `.docx` from `input/lfa_documents/`, creates versioned `*_processed_<timestamp>.md`, maps to global template, evaluates with LLM.
- **Phase B**: owns WP lifecycle. Converts `.docx` from `input/work_packages/`, evaluates.
- **Phase C**: full proposal assessment using all inputs. Reads raw `.docx` from `lfa_documents/` and `work_packages/` as reference.
- Reusable LFA template lives at `templates/input_templates/lfa_template_processed.md` — never copy it into call workspaces.

## Call Directory Convention

All calls live under `calls/<source-slug>/<call-slug>/`:

```
calls/
├── _template/                          # scaffold for new calls
├── esa/                                # ESA Business Applications
│   ├── responsible-fishing/            # active proposal work
│   └── kick-start-open-calls/          # Watch-discovered
├── forskningsradet/                    # Norwegian Research Council
├── rvo/                                # Netherlands Enterprise Agency
├── rijksoverheid/                      # Dutch Government
└── horizon-eu/                         # Horizon Europe calls
    └── seabridge/
```

Source slugs are derived from the Watch source URL hostname. Manual calls should use the funding body as the source slug.
