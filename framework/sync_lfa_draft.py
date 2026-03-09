#!/usr/bin/env python3
"""
sync_lfa_draft.py — Push lfa_draft.md edits through Phase A reviews.

Triggered when the moderator posts 'sync' in the Slack channel.

Flow:
  1. Verify input/lfa_documents/lfa_draft.md exists
  2. Archive the current lfa_structured.md with a timestamp
  3. Copy lfa_draft.md → output/phase_a/lfa_restructured/lfa_structured.md
  4. Run Phase A (skips doc processing since no new .docx; reviews run on the draft)
  5. Print the score summary from the new improvement_guide.md

Usage:
  python3 scripts/sync_lfa_draft.py --call esa/responsible-fishing
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from scripts.call_context import ensure_call_dir, load_env_for_call, resolve_call_dir


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync lfa_draft.md into Phase A and run reviews."
    )
    parser.add_argument("--call", required=True, help="Call workspace slug under calls/")
    return parser.parse_args(argv)


def _print_score_summary(guide_path: Path) -> None:
    """Print the score summary from the top of the improvement guide."""
    if not guide_path.exists():
        print("(improvement_guide.md not found)")
        return
    lines = guide_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    print("\n--- Score Summary (from new improvement_guide.md) ---")
    for line in lines[:25]:
        print(line)
    print("-----------------------------------------------------")


def main(argv=None) -> int:
    args = parse_args(argv)
    framework_root = Path(__file__).parent.resolve()
    call_dir = resolve_call_dir(framework_root, args.call)
    ensure_call_dir(call_dir)
    load_env_for_call(call_dir, framework_root)

    draft_path      = call_dir / "input" / "lfa_documents" / "lfa_iteration_input.md"
    structured_path = call_dir / "output" / "phase_a" / "lfa_restructured" / "lfa_structured.md"
    archive_dir     = call_dir / "output" / "discussions"
    guide_path      = call_dir / "output" / "phase_a" / "improvement_guide.md"

    # 1. Verify draft exists
    if not draft_path.exists():
        print("ERROR: lfa_draft.md not found.")
        print(f"  Expected: {draft_path}")
        print("  Run init first:  python3 init_lfa_draft.py --call " + args.call)
        return 1

    draft_size = draft_path.stat().st_size
    print(f"Draft: {draft_path.name}  ({draft_size:,} bytes)")

    # 2. Archive existing lfa_structured.md
    if structured_path.exists():
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"lfa_structured_archive_{stamp}.md"
        shutil.copy2(structured_path, archive_path)
        print(f"Archived: {archive_path.name}")

    # 3. Copy draft → lfa_structured.md
    structured_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(draft_path, structured_path)
    print(f"Copied lfa_draft.md → lfa_structured.md")

    # 4. Run Phase A
    print(f"\nRunning Phase A reviews for: {args.call}")
    print("=" * 56)
    result = subprocess.run(
        [sys.executable, "run_phase_a.py", "--call", args.call],
        cwd=str(framework_root),
    )

    if result.returncode != 0:
        print(f"\nERROR: Phase A exited with code {result.returncode}")
        return 1

    # 5. Print score summary
    _print_score_summary(guide_path)

    print(f"\nDone. New improvement_guide.md is ready:")
    print(f"  {guide_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
