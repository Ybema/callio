#!/usr/bin/env python3
"""Run moderator-led discussion sessions between Phase A iterations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from scripts.call_context import ensure_call_dir, load_env_for_call, resolve_call_dir
from scripts.discussion_engine import DiscussionSession


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive discussion session to improve LFA between Phase A runs."
    )
    parser.add_argument("--call", required=True, help="Call workspace slug under calls/")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Anthropic model to use for discussion (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--resume",
        default=None,
        help="Optional path to an existing session directory in output/discussions/session_*",
    )
    return parser.parse_args(argv)


def _print_chunk(chunk: str) -> None:
    print(chunk, end="", flush=True)


def _history_path(framework_root: Path) -> Path:
    cache_dir = framework_root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "discussion_history.txt"


def _handle_command(session: DiscussionSession, raw: str) -> bool:
    cmd, _, rest = raw.partition(" ")
    cmd = cmd.strip().lower()
    arg = rest.strip()

    if cmd == "/help":
        print(session.command_help())
        return False

    if cmd == "/show":
        if not arg:
            print("Usage: /show <lfa|derivation|guide|structural|alignment|call|team>")
            return False
        print(session.show_section(arg))
        return False

    if cmd == "/guide":
        print(session.show_section("guide"))
        return False

    if cmd == "/team":
        print(session.show_section("team"))
        return False

    if cmd == "/draft":
        print("Generating draft...\n")
        session.draft(on_chunk=_print_chunk)
        print("\n")
        print("Draft saved to session checkpoint.")
        return False

    if cmd == "/diff":
        print(session.diff())
        return False

    if cmd == "/save":
        print(session.save())
        return False

    if cmd == "/finalize":
        print("Finalizing outputs...\n")
        outputs = session.finalize(on_chunk=_print_chunk)
        print("\n")
        print("Session finalized. Outputs:")
        for k, v in outputs.items():
            print(f"- {k}: {v}")
        return True

    print(f"Unknown command: {cmd}. Use /help")
    return False


def main(argv=None) -> int:
    args = parse_args(argv)
    framework_root = Path(__file__).parent.resolve()
    call_dir = resolve_call_dir(framework_root, args.call)
    ensure_call_dir(call_dir)
    load_env_for_call(call_dir, framework_root)

    resume_path: Optional[Path] = Path(args.resume).expanduser().resolve() if args.resume else None
    if resume_path and not resume_path.exists():
        print(f"Resume path does not exist: {resume_path}")
        return 1

    session = DiscussionSession(
        framework_root=framework_root,
        call_dir=call_dir,
        call_slug=args.call,
        model=args.model,
        resume=resume_path,
    )
    print(session.context_summary())
    print()
    print("Interactive session started.")
    print("Type /help for commands. Use /finalize to produce .md + .docx outputs for the next Phase A iteration.")
    print()

    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
    except ModuleNotFoundError:
        print("Missing dependency: prompt_toolkit")
        print("Install with: python3 -m pip install -r requirements.txt")
        return 1

    prompt_session: Any = PromptSession(history=FileHistory(str(_history_path(framework_root))))

    while True:
        try:
            user_input = prompt_session.prompt("moderator> ", multiline=True)
        except (EOFError, KeyboardInterrupt):
            print("\nStopping session. Saving checkpoint...")
            print(session.save())
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            should_exit = _handle_command(session, user_input)
            if should_exit:
                break
            continue

        print("assistant> ", end="", flush=True)
        session.handle_message(user_input, on_chunk=_print_chunk)
        print("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
