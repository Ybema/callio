#!/usr/bin/env python3
"""List call workspaces with status summary.

Usage:
    python3 scripts/list_calls.py                # all calls
    python3 scripts/list_calls.py --source esa   # one source
    python3 scripts/list_calls.py --active        # only calls with real work
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def _latest_mtime(directory: Path) -> Optional[float]:
    """Return the most recent file mtime under a directory, or None."""
    latest = None
    for f in directory.rglob("*"):
        if f.is_file() and not f.name.startswith("."):
            mt = f.stat().st_mtime
            if latest is None or mt > latest:
                latest = mt
    return latest


def _count_phase_runs(output_dir: Path, phase: str) -> int:
    phase_dir = output_dir / phase
    if not phase_dir.exists():
        return 0
    return len(list(phase_dir.rglob("*.json"))) + len(list(phase_dir.rglob("*.md")))


def discover_calls(calls_root: Path, source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    results = []
    for source_dir in sorted(calls_root.iterdir()):
        if not source_dir.is_dir() or source_dir.name.startswith((".", "_")):
            continue
        if source_filter and source_dir.name != source_filter:
            continue

        for call_dir in sorted(source_dir.iterdir()):
            if not call_dir.is_dir() or call_dir.name.startswith("."):
                continue

            source = source_dir.name
            call = call_dir.name
            ref = f"{source}/{call}"

            config_path = call_dir / "call.yaml"
            config = _load_yaml(config_path) if config_path.exists() else {}

            output_dir = call_dir / "output"
            has_output = output_dir.exists() and any(output_dir.rglob("*.json"))

            has_lfa = any((call_dir / "input" / "lfa_documents").glob("*.md"))
            has_call_docs = any(
                f for f in (call_dir / "input" / "call_documents").glob("*")
                if f.suffix in (".md", ".pdf", ".docx") and "_watch_manifest" not in f.name
            )
            has_handoff = (call_dir / "output" / "watch_handoff" / "index.json").exists()

            phase_a_runs = _count_phase_runs(output_dir, "phase_a")
            phase_b_runs = _count_phase_runs(output_dir, "phase_b")
            phase_c_runs = _count_phase_runs(output_dir, "phase_c")

            if phase_a_runs > 0:
                status = "active"
            elif has_lfa or has_call_docs:
                status = "prepared"
            elif has_handoff:
                status = "discovered"
            else:
                status = "empty"

            last_activity = _latest_mtime(output_dir) if has_output else None
            last_str = datetime.fromtimestamp(last_activity).strftime("%Y-%m-%d") if last_activity else "-"

            results.append({
                "ref": ref,
                "source": source,
                "call": call,
                "project_name": config.get("project_name", "-"),
                "funding_type": config.get("funding_type", "-"),
                "status": status,
                "phase_a": phase_a_runs,
                "phase_b": phase_b_runs,
                "phase_c": phase_c_runs,
                "last_activity": last_str,
            })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="List call workspaces")
    parser.add_argument("--source", help="Filter by source slug")
    parser.add_argument("--active", action="store_true", help="Only show calls with phase runs")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    framework_root = Path(__file__).resolve().parent.parent
    calls_root = framework_root / "calls"

    calls = discover_calls(calls_root, source_filter=args.source)

    if args.active:
        calls = [c for c in calls if c["status"] == "active"]

    if args.as_json:
        print(json.dumps(calls, indent=2))
        return

    # Summary header
    sources = sorted(set(c["source"] for c in calls))
    status_counts = {}
    for c in calls:
        status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1

    print(f"Sources: {', '.join(sources)}")
    print(f"Total: {len(calls)} calls  ({', '.join(f'{v} {k}' for k, v in sorted(status_counts.items()))})")
    print()

    # Table
    header = f"{'Call Reference':<65} {'Status':<12} {'A':>3} {'B':>3} {'C':>3} {'Last Activity':>14}"
    print(header)
    print("-" * len(header))

    for c in calls:
        ref = c["ref"]
        if len(ref) > 63:
            ref = ref[:60] + "..."
        a = str(c["phase_a"]) if c["phase_a"] else "."
        b = str(c["phase_b"]) if c["phase_b"] else "."
        c_val = str(c["phase_c"]) if c["phase_c"] else "."
        print(f"{ref:<65} {c['status']:<12} {a:>3} {b:>3} {c_val:>3} {c['last_activity']:>14}")


if __name__ == "__main__":
    main()
