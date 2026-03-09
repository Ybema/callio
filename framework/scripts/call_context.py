#!/usr/bin/env python3
"""Utilities for resolving per-call workspace paths and config."""

from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


def resolve_call_dir(framework_root: Path, call_name: str) -> Path:
    """Return the absolute path for a named call workspace.

    Supports both:
    - flat names: "esa-responsible-fishing"
    - grouped names: "esa/responsible-fishing"
    """
    calls_root = framework_root / "calls"
    rel = Path(call_name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Invalid call name: {call_name}")

    direct = calls_root / rel
    if direct.exists():
        return direct

    # Backward compatibility: if only nested source/call exists, resolve it.
    if len(rel.parts) == 1:
        nested_matches = [p for p in calls_root.glob(f"*/{call_name}") if p.is_dir()]
        if len(nested_matches) == 1:
            return nested_matches[0]

    return direct


def ensure_call_dir(call_dir: Path) -> None:
    """Validate a call workspace exists."""
    if not call_dir.exists():
        raise FileNotFoundError(f"Call directory not found: {call_dir}")


def load_env_for_call(call_dir: Path, framework_root: Path) -> None:
    """
    Load environment variables with call precedence.

    Order:
    1) call-level .env
    2) framework-level .env (fills missing only)
    """
    call_env = call_dir / ".env"
    framework_env = framework_root / ".env"
    monorepo_env = framework_root.parent / ".env"

    if call_env.exists():
        load_dotenv(call_env, override=False)
    if framework_env.exists():
        load_dotenv(framework_env, override=False)
    if monorepo_env.exists():
        load_dotenv(monorepo_env, override=False)


def load_call_config(call_dir: Path) -> Dict[str, Any]:
    """Load and validate call.yaml from the call workspace."""
    config_path = call_dir / "call.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing call config: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return {
        "project_name": config.get("project_name", "Project"),
        "call_id": config.get("call_id", "CALL-ID-PLACEHOLDER"),
        "funding_type": config.get("funding_type", "generic"),
        "model": config.get("model", "gpt-4o-mini"),
        "phases": config.get("phases", ["pre", "A"]),
    }
