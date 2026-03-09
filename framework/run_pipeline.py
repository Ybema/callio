#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orchestrator.context import PipelineContext
from orchestrator.runner import run_selected_steps
from scripts.call_context import ensure_call_dir, load_env_for_call, resolve_call_dir


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run framework pipeline with step-level orchestration."
    )
    parser.add_argument("--call", required=True, help="Call workspace slug under calls/")
    parser.add_argument(
        "--from",
        dest="from_step",
        choices=["pre", "phase_a", "phase_b", "phase_c"],
        help="Run from this step onward.",
    )
    parser.add_argument(
        "--to",
        dest="to_step",
        choices=["pre", "phase_a", "phase_b", "phase_c"],
        help="Run until this step (inclusive).",
    )
    parser.add_argument(
        "--only",
        dest="only_step",
        choices=["pre", "phase_a", "phase_b", "phase_c"],
        help="Run only one step.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining selected steps even when one fails.",
    )
    parser.add_argument(
        "--run-id",
        help="Optional run identifier. Default is auto-generated.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    framework_root = Path(__file__).parent.resolve()
    call_dir = resolve_call_dir(framework_root, args.call)
    ensure_call_dir(call_dir)
    load_env_for_call(call_dir, framework_root)

    context = PipelineContext.create(
        call_slug=args.call,
        framework_root=framework_root,
        run_id=args.run_id,
        continue_on_error=args.continue_on_error,
    )
    steps = context.resolve_steps(
        from_step=args.from_step,
        to_step=args.to_step,
        only_step=args.only_step,
    )

    print(f"Pipeline run_id: {context.run_id}")
    print(f"Call: {context.call_slug}")
    print(f"Steps: {', '.join(steps)}")
    print()

    rc = run_selected_steps(context, steps)
    print()
    print(f"State file: {context.state_path}")
    print(f"Artifacts file: {context.artifacts_path}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

