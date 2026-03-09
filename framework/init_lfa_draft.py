#!/usr/bin/env python3
"""
init_lfa_draft.py — Initialise lfa_draft.md for a call.

Seeds input/lfa_documents/lfa_draft.md from the latest Phase A output
(output/phase_a/lfa_restructured/lfa_structured.md). This is the file
Mark edits in Cursor between Phase A runs. Once seeded, use sync_lfa_draft.py
to push edits back through Phase A.

Current state of input/lfa_documents/ for esa/responsible-fishing:
  - fish_mapping_lfa.docx                        (original source docx)
  - fish_mapping_lfa_processed_20260309_093631.md (Phase A processed)
  - fish_mapping_lfa_raw.md                       (raw converted markdown)
  - lfa_template_processed_20260304_202644.md     (template placeholder)

Usage:
  python3 scripts/init_lfa_draft.py --call esa/responsible-fishing
  python3 scripts/init_lfa_draft.py --call esa/responsible-fishing --force
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from scripts.call_context import ensure_call_dir, load_env_for_call, resolve_call_dir


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed input/lfa_documents/lfa_draft.md from the latest Phase A structured LFA."
    )
    parser.add_argument("--call", required=True, help="Call workspace slug under calls/")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing lfa_draft.md without prompting",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    framework_root = Path(__file__).parent.resolve()
    call_dir = resolve_call_dir(framework_root, args.call)
    ensure_call_dir(call_dir)
    load_env_for_call(call_dir, framework_root)

    source = call_dir / "output" / "phase_a" / "lfa_restructured" / "lfa_structured.md"
    dest   = call_dir / "input" / "lfa_documents" / "lfa_iteration_input.md"

    if not source.exists():
        print(f"ERROR: Structured LFA not found at:\n  {source}")
        print("Run Phase A first to generate lfa_structured.md.")
        return 1

    if dest.exists() and not args.force:
        answer = input(f"lfa_draft.md already exists ({dest.stat().st_size:,} bytes). Overwrite? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)

    size_kb = dest.stat().st_size / 1024
    print(f"Initialised lfa_draft.md")
    print(f"  Source : {source}")
    print(f"  Dest   : {dest}")
    print(f"  Size   : {size_kb:.1f} KB")
    print()
    print("Edit lfa_iteration_input.md in Cursor, then post 'sync' in the Slack channel")
    print("to run Phase A reviews on your changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
