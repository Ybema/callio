from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable
from urllib.parse import urlparse
import json
import re


def _slugify(value: str, fallback: str = "call") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or fallback


def _safe_filename(value: str, fallback: str = "source") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return name or fallback


def _repo_paths() -> tuple[Path, Path]:
    monorepo_root = Path(__file__).resolve().parents[4]
    framework_root = monorepo_root / "framework"
    return monorepo_root, framework_root


def derive_source_slug(source_label: str | None, source_url: str | None) -> str:
    parsed = urlparse(source_url or "")
    host = (parsed.netloc or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        host_parts = [p for p in host.split(".") if p]
        if len(host_parts) >= 2:
            return _slugify(host_parts[-2], "source")
        return _slugify(host_parts[0], "source")
    return _slugify(source_label or "", "source")


def derive_call_slug(title: str | None, url: str | None, explicit_slug: str | None = None) -> str:
    if explicit_slug:
        return _slugify(explicit_slug, "call")[:80]
    parsed = urlparse(url or "")
    host_slug = _slugify(parsed.netloc or "call")
    return _slugify(title or "", host_slug)[:80]


def get_call_workspace_dir(
    framework_root: Path,
    source_slug: str,
    call_slug: str,
) -> Path:
    return framework_root / "calls" / source_slug / call_slug


def _ensure_call_workspace(call_dir: Path, title: str) -> None:
    if call_dir.exists():
        return

    (call_dir / "input" / "call_documents").mkdir(parents=True, exist_ok=True)
    (call_dir / "input" / "lfa_documents").mkdir(parents=True, exist_ok=True)
    (call_dir / "input" / "strategy_documents").mkdir(parents=True, exist_ok=True)
    (call_dir / "input" / "work_packages").mkdir(parents=True, exist_ok=True)
    (call_dir / "output").mkdir(parents=True, exist_ok=True)

    call_slug = call_dir.name
    call_id = _slugify(call_slug, "call").upper().replace("-", "_")
    safe_title = (title or call_slug).replace('"', '\\"')
    call_yaml = (
        f'project_name: "{safe_title}"\n'
        f"call_id: {call_id}\n"
        "funding_type: generic\n"
        "model: gpt-4o-mini\n"
        "phases:\n"
        "- pre\n"
        "- A\n"
    )
    (call_dir / "call.yaml").write_text(call_yaml, encoding="utf-8")


def _load_index(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"call_hashes": {}, "updated_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"call_hashes": {}, "updated_at": None}


def _save_index(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def handoff_calls_to_framework(source: Any, calls: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """
    Write metadata-only handoff manifests into framework call workspaces.
    """
    _, framework_root = _repo_paths()
    created = 0
    skipped = 0
    errors = 0

    source_label = getattr(source, "label", None) or getattr(source, "url", "source")
    source_url = getattr(source, "url", "")
    source_id = str(getattr(source, "id", ""))
    source_tag = _safe_filename(_slugify(source_label, "source"))
    source_slug = derive_source_slug(source_label=source_label, source_url=source_url)

    for call in calls:
        try:
            title = (call.get("title") or "").strip()
            url = call.get("url") or source_url
            deadline = call.get("deadline")
            summary = call.get("summary")
            call_hash = call.get("call_hash")
            seen_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

            call_slug = derive_call_slug(
                title=title,
                url=url,
                explicit_slug=call.get("call_slug"),
            )

            call_dir = get_call_workspace_dir(
                framework_root=framework_root,
                source_slug=source_slug,
                call_slug=call_slug,
            )
            _ensure_call_workspace(call_dir, title=title or call_slug)

            index_path = call_dir / "output" / "watch_handoff" / "index.json"
            idx = _load_index(index_path)
            call_hashes = idx.setdefault("call_hashes", {})
            dedupe_key = call_hash or _slugify(f"{title}-{url}", "unknown")
            if dedupe_key in call_hashes:
                skipped += 1
                continue

            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            manifest_name = f"{source_tag}_{ts}_watch_manifest.json"
            manifest_path = call_dir / "input" / "call_documents" / manifest_name
            payload = {
                "call_slug": call_slug,
                "source_slug": source_slug,
                "source_url": source_url,
                "title": title,
                "url": url,
                "deadline": deadline,
                "summary": summary,
                "call_hash": call_hash,
                "source_id": source_id,
                "source_label": source_label,
                "seen_at": seen_at,
            }
            manifest_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            call_hashes[dedupe_key] = {
                "manifest_path": str(manifest_path),
                "seen_at": seen_at,
            }
            _save_index(index_path, idx)
            created += 1
        except Exception:
            errors += 1

    return {"created": created, "skipped": skipped, "errors": errors}

