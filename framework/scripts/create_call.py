#!/usr/bin/env python3
"""Create a new call workspace from calls/_template."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a new proposal call workspace from template."
    )
    parser.add_argument(
        "call_name",
        help="Folder name under calls/ (for example: my-new-call)",
    )
    parser.add_argument(
        "--source",
        help="Optional source slug for grouped path (for example: esa)",
    )
    parser.add_argument(
        "--project-name",
        help="Value for project_name in call.yaml (defaults to call_name)",
    )
    parser.add_argument(
        "--call-id",
        default="CALL-ID-PLACEHOLDER",
        help="Value for call_id in call.yaml",
    )
    parser.add_argument(
        "--funding-type",
        default="generic",
        help="Funding type key (for example: generic, horizon_eu)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Default model name to write into call.yaml",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite destination if it already exists",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    template_dir = repo_root / "calls" / "_template"
    calls_dir = repo_root / "calls"
    if args.source:
        source_path = Path(args.source)
        if source_path.is_absolute() or ".." in source_path.parts or len(source_path.parts) != 1:
            print(f"Error: invalid source slug: {args.source}")
            return 1
        call_dir = calls_dir / args.source / args.call_name
        call_ref = f"{args.source}/{args.call_name}"
    else:
        call_dir = calls_dir / args.call_name
        call_ref = args.call_name

    if not template_dir.exists():
        print(f"Error: template folder not found: {template_dir}")
        return 1

    if call_dir.exists():
        if not args.force:
            print(f"Error: destination already exists: {call_dir}")
            print("Use --force to overwrite.")
            return 1
        shutil.rmtree(call_dir)

    shutil.copytree(template_dir, call_dir)

    call_yaml_path = call_dir / "call.yaml"
    config = load_yaml(call_yaml_path)
    config["project_name"] = args.project_name or args.call_name
    config["call_id"] = args.call_id
    config["funding_type"] = args.funding_type
    config["model"] = args.model
    save_yaml(call_yaml_path, config)

    print(f"Created call workspace: {call_dir}")
    print("Next steps:")
    print(f"  1) Edit config: nano {call_yaml_path}")
    print(f"  2) Add call docs: {call_dir / 'input' / 'call_documents'}")
    print(f"  3) Add LFA docs:  {call_dir / 'input' / 'lfa_documents'}")
    print(f"  4) Run pre-phase: python3 run_pre_phase.py --call {call_ref}")
    print(f"  5) Run phase A:   python3 run_phase_a.py --call {call_ref} --verbose")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
