# Deployment

## Server Setup (SSH / Headless)

Tested on Ubuntu 22.04 (linux 6.8.0) via Cursor Remote SSH.

### 1. Clone monorepo to ~/projects/

```bash
git clone <callio-repo-url> ~/projects/callio
cd ~/projects/callio/framework
```

### 2. Create virtual environment

Use `virtualenv`, not `python3 -m venv`. The system package `python3.12-venv` is often missing on minimal Ubuntu installs and requires `sudo apt install` to fix. `virtualenv` is pre-installed via pip and works without root.

```bash
virtualenv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

The `openai` package is not listed in `requirements.txt` but is required. Install separately:

```bash
python3 -m pip install openai
```

### 3. Create call workspace

Create a call-specific workspace with the generator:

```bash
python3 scripts/create_call.py my-call
```

Edit call config:

```bash
nano calls/my-call/call.yaml
```

### 4. Create .env

Create call-level `.env` (recommended):

```bash
nano calls/my-call/.env
```

Contents:
```
OPENAI_API_KEY=sk-proj-...
```

Lock permissions:
```bash
chmod 600 calls/my-call/.env
```

Environment loading order is automatic:
1. `calls/<call>/.env`
2. repo root `.env` (fallback)

No manual `export` is needed.

### 5. Add input files

```bash
cp my-call.pdf calls/my-call/input/call_documents/
cp my-strategy.pdf calls/my-call/input/strategy_documents/
cp my-lfa.docx calls/my-call/input/lfa_documents/
```

Document ownership model:

- **Static context** (`call_documents/`, `strategy_documents/`): processed by pre-phase once, do not change between iterations
- **Consortium iteration inputs** (`lfa_documents/`): processed by Phase A with versioned output each iteration
- **Consortium iteration inputs** (`work_packages/`): processed by Phase B with versioned output each iteration
- Reusable template files belong only in `templates/input_templates/`
- Phase A maps call-specific LFA content onto the global template structure

### 6. Create output directories (optional)

Most scripts expect these to exist:

```bash
mkdir -p calls/my-call/output/phase_a/processing_logs calls/my-call/output/phase_a/review_results
mkdir -p calls/my-call/output/phase_b/processing_logs calls/my-call/output/phase_b/review_results
mkdir -p calls/my-call/output/phase_c/processing_logs calls/my-call/output/phase_c/review_results
mkdir -p calls/my-call/output/logs calls/my-call/output/reports calls/my-call/snapshots
```

Note: Phase A now creates `output/phase_a/processing_logs` and `output/phase_a/review_results` automatically if missing.

### 7. Cursor interpreter

Create `.vscode/settings.json` in the project root (git-ignored):

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python3"
}
```

Or set manually: Ctrl+Shift+P → "Python: Select Interpreter" → `.venv/bin/python3`

## Verify Setup

```bash
source .venv/bin/activate
python3 run_phase_a.py --call my-call --help
```

Should print usage without errors (pydub ffmpeg warning is harmless).

## Full Test Run

```bash
python3 run_pre_phase.py --call my-call
python3 run_phase_a.py --call my-call --verbose
```

Expected: Phase A completes in ~30-60 seconds with 3 OpenAI API calls (CA, LC, CQ blocks).  
Outputs are written to `calls/my-call/output/phase_a/review_results/`.

Phase A processing logs include `template_mapping` diagnostics for call-specific LFA files (matched/unmatched template sections). Pre-phase only converts static context documents and does not touch LFA or WP files.

## Warnings

| Warning | Cause | Impact |
|---------|-------|--------|
| `Couldn't find ffmpeg or avconv` | pydub (via markitdown) wants ffmpeg for audio | None — audio processing not used |
