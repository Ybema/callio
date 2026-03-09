# Known Issues

## Phase B/C — ReviewEngine not wired

`scripts/framework.py` comments out the `ReviewEngine` import and instantiation:

```python
# from .review_engine import ReviewEngine  # Commented out - class doesn't exist
# self.review_engine = ReviewEngine(self.config)
```

Phase B (`run_phase_b.py`) and Phase C (`run_phase_c.py`) route through `ProposalFramework`, which calls `self.review_engine` in `run_phase()`. Since `review_engine` is never set, **Phase B and C will fail at the review step**.

Phase A works because it bypasses `ProposalFramework` entirely and calls `scripts/review_engine/review_engine.py` directly.

**Workaround:** None currently. Phase A is the only fully functional review phase.

---

## Step 4 / Part B scripts missing

`config/wp_to_partb_mapping.yaml` references scripts that don't exist in the repo:

- `analyze_partb_content.py`
- `detect_wp_files.py`
- `verify_context.py`

These appear to be planned for a future Step 4 (Part B table extraction) workflow.

---

## Config path mismatches

`scripts/framework.py` looks for review criteria at:
```
config/review_criteria/{funding_type}_phase_{phase}.md
```

Actual location is:
```
config/review_criteria_scoring/{funding_type}_phase_{phase}.md
```

This mismatch would cause a `FileNotFoundError` if `ProposalFramework` tried to load criteria. Not triggered currently because Phase A loads criteria independently.

---

## horizon_eu.yaml lists providers not used at runtime

`config/funding_types/horizon_eu.yaml` lists Anthropic Claude and OpenAI GPT-4 as review providers. The actual runtime uses `llm_provider.py` which only supports OpenAI API and Cursor CLI. The Anthropic provider in the config has no effect.

---

## openai package not in requirements.txt

The `openai` Python package is required by `llm_provider.py` but not listed in `requirements.txt`. Must be installed separately: `pip install openai`.

---

## pydub ffmpeg warning

Every run prints:
```
RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
```

This comes from `pydub` (pulled in by `markitdown[all]`). Harmless — audio conversion is not used. Can be suppressed by installing ffmpeg (`sudo apt install ffmpeg`) or ignored.

---

## Cursor CLI availability check too optimistic

`LLMProvider._check_cursor_availability()` runs `cursor status` with a 5-second timeout. This succeeds on SSH servers where the Cursor remote extension is installed, even though `cursor agent` (the actual LLM endpoint) hangs indefinitely without an interactive IDE session.

Mitigated by setting `preferred_provider="openai"` (see [decisions.md](decisions.md)), but the check itself still returns a false positive.
