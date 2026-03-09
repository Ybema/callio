from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.call import SeenCall
from app.models.source import Source
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.doc_acquirer import acquire_documents
from app.services.framework_handoff import (
    derive_call_slug,
    derive_source_slug,
    get_call_workspace_dir,
    handoff_calls_to_framework,
)

router = APIRouter(prefix="/calls", tags=["prepare"])


def _framework_root() -> Path:
    return Path(__file__).resolve().parents[4] / "framework"


def _prepare_status_path(call_dir: Path) -> Path:
    return call_dir / "output" / "watch_handoff" / "prepare_status.json"


def _load_prepare_status(call_dir: Path) -> dict:
    status_path = _prepare_status_path(call_dir)
    if not status_path.exists():
        return {}
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_prepare_status(call_dir: Path, payload: dict) -> None:
    status_path = _prepare_status_path(call_dir)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@router.post("/{seen_call_id}/prepare")
async def prepare_call_for_framework(
    seen_call_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SeenCall, Source)
        .join(Source, SeenCall.source_id == Source.id)
        .where(SeenCall.id == seen_call_id, Source.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Call not found")

    seen_call, source = row
    source_slug = derive_source_slug(source.label, source.url)
    call_slug = derive_call_slug(seen_call.title, seen_call.url)
    framework_root = _framework_root()
    call_dir = get_call_workspace_dir(framework_root, source_slug, call_slug)

    call_payload = {
        "title": seen_call.title,
        "url": seen_call.url,
        "deadline": seen_call.deadline,
        "summary": seen_call.summary,
        "call_hash": seen_call.call_hash,
        "call_slug": call_slug,
    }
    handoff_result = handoff_calls_to_framework(source, [call_payload])

    if not call_dir.exists():
        raise HTTPException(status_code=500, detail="Failed to create framework workspace")

    existing_status = _load_prepare_status(call_dir)
    if (
        existing_status.get("status") == "ready"
        and existing_status.get("call_url") == (seen_call.url or source.url)
    ):
        return {
            "status": "ok",
            "already_prepared": True,
            "workspace_path": str(call_dir),
            "call_slug": call_slug,
            "source_slug": source_slug,
            "handoff": handoff_result,
            "documents": [],
            "documents_downloaded": int(existing_status.get("documents_downloaded", 0)),
            "documents_errors": int(existing_status.get("documents_errors", 0)),
            "prepared_at": existing_status.get("prepared_at"),
        }

    call_documents_dir = call_dir / "input" / "call_documents"
    doc_results = await acquire_documents(
        call_url=seen_call.url or source.url,
        target_dir=call_documents_dir,
    )
    downloaded_count = sum(1 for r in doc_results if r.get("status") == "downloaded")
    skipped_count = sum(1 for r in doc_results if r.get("status") == "skipped_existing")
    error_count = sum(1 for r in doc_results if r.get("status") == "error")
    prepared_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    status = "ready" if error_count == 0 else "partial"
    _save_prepare_status(
        call_dir,
        {
            "status": status,
            "prepared_at": prepared_at,
            "seen_call_id": str(seen_call.id),
            "call_url": seen_call.url or source.url,
            "documents_downloaded": downloaded_count,
            "documents_skipped_existing": skipped_count,
            "documents_errors": error_count,
        },
    )

    return {
        "status": "ok",
        "already_prepared": False,
        "workspace_path": str(call_dir),
        "call_slug": call_slug,
        "source_slug": source_slug,
        "handoff": handoff_result,
        "documents": doc_results,
        "documents_downloaded": downloaded_count,
        "documents_skipped_existing": skipped_count,
        "documents_errors": error_count,
        "prepared_at": prepared_at,
    }
