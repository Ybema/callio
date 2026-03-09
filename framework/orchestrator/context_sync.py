from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import hashlib


@dataclass
class SyncResult:
    changed: bool
    files_processed: int
    context_path: Path | None
    diff: Dict[str, List[str]]


class ContextSync:
    """Hash-based context synchronization for pre-phase inputs."""

    def __init__(self, framework_root: Path, call_dir: Path):
        self.framework_root = framework_root
        self.call_dir = call_dir
        self.input_root = call_dir / "input"
        self.manifest_path = call_dir / "output" / "pre_phase" / ".context_manifest.json"

    def _sha256(self, path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def scan(self) -> Dict[str, Dict[str, str]]:
        scanned: Dict[str, Dict[str, str]] = {}
        categories = {
            "call_documents": "call_document",
            "strategy_documents": "strategy_document",
        }
        allowed = {".pdf", ".docx", ".doc", ".md", ".txt"}

        for folder_name, category in categories.items():
            folder = self.input_root / folder_name
            if not folder.exists():
                continue
            for path in sorted(folder.iterdir()):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed or path.name.endswith("_processed.md"):
                    continue
                rel_key = str(path.relative_to(self.call_dir))
                scanned[rel_key] = {
                    "hash": self._sha256(path),
                    "category": category,
                }
        return scanned

    def load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": 1, "files": {}}
        try:
            import json

            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"version": 1, "files": {}}
            data.setdefault("version", 1)
            data.setdefault("files", {})
            return data
        except Exception:
            return {"version": 1, "files": {}}

    def save_manifest(self, manifest: Dict[str, Any]) -> None:
        import json

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def diff(self, scanned: Dict[str, Dict[str, str]], manifest: Dict[str, Any]) -> Dict[str, List[str]]:
        files = manifest.get("files", {})
        new_files: List[str] = []
        changed_files: List[str] = []
        unchanged_files: List[str] = []

        for key, val in scanned.items():
            existing = files.get(key)
            if not existing:
                new_files.append(key)
            elif existing.get("hash") != val.get("hash"):
                changed_files.append(key)
            else:
                unchanged_files.append(key)

        removed_files = [k for k in files.keys() if k not in scanned]
        return {
            "new": sorted(new_files),
            "changed": sorted(changed_files),
            "removed": sorted(removed_files),
            "unchanged": sorted(unchanged_files),
        }

    def _load_processor(self):
        # Imported lazily to avoid circular imports during CLI startup.
        from run_pre_phase import PrePhaseProcessor

        return PrePhaseProcessor(framework_root=self.framework_root, call_dir=self.call_dir)

    def process_delta(
        self,
        diff_result: Dict[str, List[str]],
        manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        processor = self._load_processor()
        static_files = processor.discover_static_files()
        return processor.process_static_files(static_files, manifest=manifest)

    def recompile_context(self, process_results: Dict[str, Any]) -> Path | None:
        compiled = process_results.get("compiled_call_context") or {}
        path = compiled.get("path")
        return Path(path) if path else None

    def sync(self) -> SyncResult:
        scanned = self.scan()
        manifest = self.load_manifest()
        diff_result = self.diff(scanned, manifest)
        changed = bool(
            diff_result["new"] or diff_result["changed"] or diff_result["removed"]
        )

        existing_path = manifest.get("compiled_context_path")
        if not changed and existing_path:
            context_path = self.call_dir / existing_path
            if context_path.exists():
                return SyncResult(
                    changed=False,
                    files_processed=0,
                    context_path=context_path,
                    diff=diff_result,
                )

        process_results = self.process_delta(diff_result, manifest)
        processor = self._load_processor()
        processor.save_manifest(process_results.get("manifest", manifest))
        context_path = self.recompile_context(process_results)
        files_processed = (
            len(diff_result["new"])
            + len(diff_result["changed"])
            + len(diff_result["removed"])
        )
        return SyncResult(
            changed=True,
            files_processed=files_processed,
            context_path=context_path,
            diff=diff_result,
        )


def sync_context(call_dir: Path, framework_root: Path) -> SyncResult:
    return ContextSync(framework_root=framework_root, call_dir=call_dir).sync()

