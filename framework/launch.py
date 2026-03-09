#!/usr/bin/env python3
"""
project framework Launcher
=========================

Simple launcher for running any phase of the project framework.

Usage:
    python launch.py A        # Run Phase A (LFA Analysis)
    python launch.py B        # Run Phase B (Work Packages)
    python launch.py C        # Run Phase C (Full Project Plan)
    python launch.py --help   # Show this help
"""

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.call_context import ensure_call_dir, load_env_for_call, resolve_call_dir


def show_help():
    """Show help information"""
    print("🚀 project framework Launcher")
    print("=" * 35)
    print()
    print("Usage:")
    print("  python launch.py A --call my-call     # Phase A: LFA Analysis")
    print("  python launch.py B --call my-call     # Phase B: Work Packages Analysis")
    print("  python launch.py C --call my-call     # Phase C: Full Project Plan Analysis")
    print("  python launch.py --help      # Show this help")
    print()
    print("Phase Details:")
    print("  Phase A: Analyzes Logic Framework against call requirements")
    print("  Phase B: Analyzes individual work packages and alignment")
    print("  Phase C: Comprehensive analysis of complete proposal")
    print()
    print("Advanced Usage:")
    print("  python3 run_phase_a.py --call my-call --verbose")
    print("  python3 run_phase_b.py --call my-call --funding-type skattefunn")
    print("  python3 run_phase_c.py --call my-call --mode python")


def main():
    """Main launcher"""
    if len(sys.argv) < 2 or sys.argv[1] in ["--help", "-h", "help"]:
        show_help()
        return

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("phase", nargs="?")
    parser.add_argument("--call")
    args, passthrough = parser.parse_known_args()

    if not args.phase:
        show_help()
        return

    if not args.call:
        print("❌ Missing required argument: --call <call-name>")
        print("   Example: python launch.py A --call seabridge")
        sys.exit(1)

    phase = args.phase.upper()
    framework_root = Path(__file__).parent
    call_dir = resolve_call_dir(framework_root, args.call)
    ensure_call_dir(call_dir)
    load_env_for_call(call_dir, framework_root)

    # Map phases to their runner scripts
    phase_scripts = {
        "A": framework_root / "run_phase_a.py",
        "B": framework_root / "run_phase_b.py",
        "C": framework_root / "run_phase_c.py",
    }

    if phase not in phase_scripts:
        print(f"❌ Unknown phase: {phase}")
        print("   Valid phases: A, B, C")
        print("   Use 'python launch.py --help' for more information")
        sys.exit(1)

    script_path = phase_scripts[phase]

    if not script_path.exists():
        print(f"❌ Phase script not found: {script_path}")
        sys.exit(1)

    # Pass through any additional arguments
    cmd = [sys.executable, str(script_path), "--call", args.call] + passthrough

    print(f"🚀 Launching Phase {phase}...")
    print(f"   Command: {' '.join(cmd)}")
    print()

    try:
        # Run the phase script
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n⚠️  Phase execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to launch Phase {phase}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
