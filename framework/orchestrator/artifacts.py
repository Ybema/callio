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


def init_artifacts(context: PipelineContext) -> Dict[str, Any]:
    context.ensure_dirs()
    payload = {
        "run_id": context.run_id,
        "call_slug": context.call_slug,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "steps": {
            "pre": [],
            "phase_a": [],
            "phase_b": [],
            "phase_c": [],
        },
    }
    _write_json(context.artifacts_path, payload)
    return payload


def load_artifacts(context: PipelineContext) -> Dict[str, Any]:
    return _read_json(context.artifacts_path)


def save_artifacts(context: PipelineContext, payload: Dict[str, Any]) -> None:
    payload["updated_at"] = _utc_now()
    _write_json(context.artifacts_path, payload)


def add_step_artifact(
    context: PipelineContext,
    payload: Dict[str, Any],
    step: str,
    artifact_type: str,
    path: str,
    metadata: Dict[str, Any] | None = None,
) -> None:
    payload["steps"].setdefault(step, [])
    payload["steps"][step].append(
        {
            "type": artifact_type,
            "path": path,
            "created_at": _utc_now(),
            "metadata": metadata or {},
        }
    )
    save_artifacts(context, payload)

