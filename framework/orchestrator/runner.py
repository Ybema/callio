from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import subprocess
import sys
import time

from .artifacts import add_step_artifact, init_artifacts
from .context import PipelineContext
from .context_sync import sync_context
from .state_store import finalize_run, finish_step, init_state, start_step


def _step_command(context: PipelineContext, step: str) -> List[str]:
    if step == "pre":
        return [sys.executable, "run_pre_phase.py", "--call", context.call_slug]
    if step == "phase_a":
        return [sys.executable, "launch.py", "A", "--call", context.call_slug]
    if step == "phase_b":
        return [sys.executable, "launch.py", "B", "--call", context.call_slug]
    if step == "phase_c":
        return [sys.executable, "launch.py", "C", "--call", context.call_slug]
    raise ValueError(f"Unknown step: {step}")


def _artifact_candidates(step: str) -> List[str]:
    if step == "pre":
        return [
            "output/logs/pre_phase_*.log",
            "output/pre_phase/**/*.json",
            "output/pre_phase/**/*.md",
        ]
    if step == "phase_a":
        return [
            "output/logs/phase_a_*.log",
            "output/phase_a/**/*.json",
            "output/phase_a/**/*.md",
            "output/phase_a/**/*.docx",
            "output/snapshots/*.json",
        ]
    if step == "phase_b":
        return [
            "output/logs/phase_b_*.log",
            "output/phase_b/**/*.json",
            "output/phase_b/**/*.md",
            "output/phase_b/**/*.docx",
            "output/snapshots/*.json",
        ]
    if step == "phase_c":
        return [
            "output/logs/phase_c_*.log",
            "output/phase_c/**/*.json",
            "output/phase_c/**/*.md",
            "output/phase_c/**/*.docx",
            "output/snapshots/*.json",
        ]
    return []


def _collect_step_artifacts(
    context: PipelineContext, step: str, started_epoch: float
) -> List[Path]:
    base = context.call_dir
    results: List[Path] = []
    seen = set()
    for pattern in _artifact_candidates(step):
        for candidate in base.glob(pattern):
            if not candidate.is_file():
                continue
            if candidate.stat().st_mtime < (started_epoch - 1):
                continue
            key = str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                results.append(candidate.resolve())
    return sorted(results, key=lambda p: p.stat().st_mtime)


def run_selected_steps(context: PipelineContext, steps: List[str]) -> int:
    state = init_state(context, steps)
    artifacts = init_artifacts(context)

    # Keep pre-phase context up to date for any run that executes phases A/B/C.
    if any(step != "pre" for step in steps):
        sync_result = sync_context(call_dir=context.call_dir, framework_root=context.framework_root)
        if sync_result.changed:
            print(f"Context updated ({sync_result.files_processed} changed inputs).")
        else:
            print("Context is up to date; no pre-phase sync needed.")

    exit_code = 0
    failed_step = None

    for step in steps:
        cmd = _step_command(context, step)
        start_step(context, state, step, cmd)
        started_epoch = time.time()
        result = subprocess.run(cmd, cwd=context.framework_root, check=False)
        error = None if result.returncode == 0 else f"Step {step} failed"
        finish_step(context, state, step, result.returncode, error=error)

        for path in _collect_step_artifacts(context, step, started_epoch):
            add_step_artifact(
                context=context,
                payload=artifacts,
                step=step,
                artifact_type=path.suffix.lstrip(".") or "file",
                path=str(path),
            )

        if result.returncode != 0:
            exit_code = result.returncode
            failed_step = step
            if not context.continue_on_error:
                break

    if failed_step and not context.continue_on_error:
        failed_idx = steps.index(failed_step)
        for step in steps[failed_idx + 1 :]:
            state["steps"][step]["status"] = "skipped"
            state["steps"][step]["error"] = "Skipped due to previous step failure"

    finalize_run(context, state)
    return exit_code

