from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import uuid


STEP_ORDER = ["pre", "phase_a", "phase_b", "phase_c"]


@dataclass
class PipelineContext:
    call_slug: str
    framework_root: Path
    run_id: str
    continue_on_error: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        call_slug: str,
        framework_root: Path,
        run_id: Optional[str] = None,
        continue_on_error: bool = False,
    ) -> "PipelineContext":
        if not run_id:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            run_id = f"pipe_{ts}_{uuid.uuid4().hex[:8]}"
        return cls(
            call_slug=call_slug,
            framework_root=framework_root.resolve(),
            run_id=run_id,
            continue_on_error=continue_on_error,
        )

    @property
    def call_dir(self) -> Path:
        return self.framework_root / "calls" / self.call_slug

    @property
    def output_dir(self) -> Path:
        return self.call_dir / "output"

    @property
    def pipeline_runs_dir(self) -> Path:
        return self.output_dir / "pipeline_runs"

    @property
    def run_dir(self) -> Path:
        return self.pipeline_runs_dir / self.run_id

    @property
    def state_path(self) -> Path:
        return self.run_dir / "state.json"

    @property
    def artifacts_path(self) -> Path:
        return self.run_dir / "artifacts.json"

    def ensure_dirs(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def resolve_steps(
        self,
        from_step: Optional[str] = None,
        to_step: Optional[str] = None,
        only_step: Optional[str] = None,
    ) -> List[str]:
        if only_step:
            if only_step not in STEP_ORDER:
                raise ValueError(f"Unknown step: {only_step}")
            return [only_step]

        start_idx = 0
        end_idx = len(STEP_ORDER) - 1
        if from_step:
            if from_step not in STEP_ORDER:
                raise ValueError(f"Unknown --from step: {from_step}")
            start_idx = STEP_ORDER.index(from_step)
        if to_step:
            if to_step not in STEP_ORDER:
                raise ValueError(f"Unknown --to step: {to_step}")
            end_idx = STEP_ORDER.index(to_step)
        if start_idx > end_idx:
            raise ValueError("--from step cannot be after --to step.")
        steps = STEP_ORDER[start_idx : end_idx + 1]
        if not steps:
            raise ValueError("No steps selected after applying --from/--to filters.")
        return steps

