from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json

from .context import PipelineContext


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def init_state(context: PipelineContext, selected_steps: List[str]) -> Dict[str, Any]:
    context.ensure_dirs()
    state = {
        "run_id": context.run_id,
        "call_slug": context.call_slug,
        "framework_root": str(context.framework_root),
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "continue_on_error": context.continue_on_error,
        "selected_steps": selected_steps,
        "status": "running",
        "steps": {
            step: {
                "status": ("pending" if step in selected_steps else "skipped"),
                "started_at": None,
                "finished_at": None,
                "command": None,
                "exit_code": None,
                "error": None,
            }
            for step in ["pre", "phase_a", "phase_b", "phase_c"]
        },
    }
    _write_json(context.state_path, state)
    return state


def load_state(context: PipelineContext) -> Dict[str, Any]:
    return _read_json(context.state_path)


def save_state(context: PipelineContext, state: Dict[str, Any]) -> None:
    state["updated_at"] = _utc_now()
    _write_json(context.state_path, state)


def start_step(
    context: PipelineContext, state: Dict[str, Any], step: str, command: List[str]
) -> None:
    entry = state["steps"][step]
    entry["status"] = "running"
    entry["started_at"] = _utc_now()
    entry["command"] = command
    entry["error"] = None
    save_state(context, state)


def finish_step(
    context: PipelineContext,
    state: Dict[str, Any],
    step: str,
    exit_code: int,
    error: str | None = None,
) -> None:
    entry = state["steps"][step]
    entry["finished_at"] = _utc_now()
    entry["exit_code"] = exit_code
    entry["status"] = "success" if exit_code == 0 else "failed"
    entry["error"] = error
    save_state(context, state)


def finalize_run(context: PipelineContext, state: Dict[str, Any]) -> None:
    any_failed = any(v["status"] == "failed" for v in state["steps"].values())
    any_running = any(v["status"] == "running" for v in state["steps"].values())
    if any_running:
        state["status"] = "running"
    else:
        state["status"] = "failed" if any_failed else "success"
    state["finished_at"] = _utc_now()
    save_state(context, state)

