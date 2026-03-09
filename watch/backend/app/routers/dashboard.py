from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pathlib import Path
import json
from urllib.parse import urlparse
from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.source import Source
from app.models.call import SeenCall, Alert, CallFeedback
from app.routers.auth import get_current_user
from app.services.framework_handoff import derive_call_slug, derive_source_slug, get_call_workspace_dir

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _normalize_url(raw: str | None) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    parsed = urlparse(raw)
    normalized_path = (parsed.path or "/").rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{normalized_path}"


def _dedupe_call_key(title: str | None, url: str | None) -> str:
    normalized = _normalize_url(url)
    if normalized:
        return normalized
    return f"{(title or '').strip().lower()}|{(url or '').strip().lower()}"


def _framework_root() -> Path:
    return Path(__file__).resolve().parents[4] / "framework"


def _load_prepare_status(call_dir: Path) -> dict:
    status_path = call_dir / "output" / "watch_handoff" / "prepare_status.json"
    if not status_path.exists():
        return {}
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class CallFeedbackIn(BaseModel):
    seen_call_id: str
    label: Literal["relevant", "not_relevant"]
    reason: str | None = None


@router.post("/reset-results")
async def reset_results(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sources = (await db.execute(
        select(Source).where(Source.user_id == user.id)
    )).scalars().all()
    source_ids = [s.id for s in sources]

    deleted_seen_calls = 0
    if source_ids:
        deleted_seen_calls = (await db.execute(
            delete(SeenCall).where(SeenCall.source_id.in_(source_ids))
        )).rowcount or 0

    deleted_feedback = (await db.execute(
        delete(CallFeedback).where(CallFeedback.user_id == user.id)
    )).rowcount or 0
    deleted_alerts = (await db.execute(
        delete(Alert).where(Alert.user_id == user.id)
    )).rowcount or 0

    for source in sources:
        source.last_status = "pending"
        source.last_error = None
        source.last_checked = None

    await db.commit()
    return {
        "ok": True,
        "deleted_seen_calls": int(deleted_seen_calls),
        "deleted_feedback": int(deleted_feedback),
        "deleted_alerts": int(deleted_alerts),
    }

@router.get("/stats")
async def get_stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sources = (await db.execute(select(Source).where(Source.user_id == user.id))).scalars().all()

    total_sources = len(sources)
    active = sum(1 for s in sources if s.last_status == "ok")
    errors = sum(1 for s in sources if s.last_status == "error")
    pending = sum(1 for s in sources if not s.last_status or s.last_status == "pending")

    # Unique keywords across all sources
    all_keywords = set()
    for s in sources:
        if s.keywords:
            for kw in s.keywords:
                all_keywords.add(kw)

    min_score = max(0, min(100, settings.matcher_min_score))

    # Total calls found and total relevant
    source_ids = [s.id for s in sources]
    total_calls = 0
    total_relevant = 0
    if source_ids:
        total_calls = (await db.execute(
            select(func.count(SeenCall.id)).where(SeenCall.source_id.in_(source_ids))
        )).scalar() or 0
        # total_relevant is computed after per-source URL dedupe for consistency

    # Alerts sent
    alerts_sent = (await db.execute(
        select(func.count(Alert.id)).where(Alert.user_id == user.id)
    )).scalar() or 0

    # Last check time
    last_checked = None
    for s in sorted(sources, key=lambda x: str(x.last_checked or ""), reverse=True):
        if s.last_checked:
            last_checked = str(s.last_checked)
            break

    # Per-source summary
    source_summary = []
    for s in sources:
        call_count = (await db.execute(
            select(func.count(SeenCall.id)).where(SeenCall.source_id == s.id)
        )).scalar() or 0
        relevant_rows = (await db.execute(
            select(SeenCall.title, SeenCall.url).where(
                SeenCall.source_id == s.id,
                SeenCall.relevance_score.is_not(None),
                SeenCall.relevance_score >= min_score,
            )
        )).all()
        relevant_keys = {
            _dedupe_call_key(title, url)
            for title, url in relevant_rows
        }
        relevant_count = len(relevant_keys)
        total_relevant += relevant_count
        source_summary.append({
            "id": s.id,
            "label": s.label or s.url[:40],
            "status": s.last_status or "pending",
            "calls_found": call_count,
            "relevant_count": relevant_count,
            "keywords": s.keywords or [],
            "last_checked": str(s.last_checked) if s.last_checked else None,
        })

    return {
        "plan": user.plan.value if user.plan else "free",
        "total_sources": total_sources,
        "active": active,
        "errors": errors,
        "pending": pending,
        "total_keywords": len(all_keywords),
        "keywords": sorted(all_keywords),
        "total_calls": total_calls,
        "total_relevant": total_relevant,
        "alerts_sent": alerts_sent,
        "alert_last_error": user.alert_last_error,
        "alert_last_error_at": str(user.alert_last_error_at) if user.alert_last_error_at else None,
        "alert_last_ok_at": str(user.alert_last_ok_at) if user.alert_last_ok_at else None,
        "last_checked": last_checked,
        "sources": source_summary,
    }

@router.post("/call-feedback")
async def save_call_feedback(
    req: CallFeedbackIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    seen_call = (await db.execute(
        select(SeenCall, Source)
        .join(Source, SeenCall.source_id == Source.id)
        .where(SeenCall.id == req.seen_call_id)
    )).first()
    if not seen_call:
        raise HTTPException(status_code=404, detail="Call not found")

    call_row, source_row = seen_call
    if str(source_row.user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Not allowed")

    existing = (await db.execute(
        select(CallFeedback).where(
            CallFeedback.user_id == user.id,
            CallFeedback.seen_call_id == call_row.id,
        )
    )).scalar_one_or_none()

    if existing:
        existing.label = req.label
        existing.reason = req.reason
    else:
        db.add(CallFeedback(
            user_id=user.id,
            seen_call_id=call_row.id,
            label=req.label,
            reason=req.reason,
        ))

    await db.commit()
    return {"ok": True, "seen_call_id": req.seen_call_id, "label": req.label}


@router.get("/source-calls/{source_id}")
async def get_source_calls(
    source_id: str,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    safe_limit = max(1, min(limit, 200))
    min_score = max(0, min(100, settings.matcher_min_score))
    scored_count = (await db.execute(
        select(func.count(SeenCall.id)).where(
            SeenCall.source_id == source.id,
            SeenCall.scored_at.is_not(None),
        )
    )).scalar() or 0
    if scored_count == 0:
        return {
            "source": {
                "id": str(source.id),
                "label": source.label or source.url,
                "status": source.last_status or "pending",
                "last_checked": str(source.last_checked) if source.last_checked else None,
            },
            "calls": [],
            "scored": False,
            "warning": "Run a scan to score calls for this source.",
        }

    # Fetch extra rows to allow URL de-duplication while still filling requested limit.
    query_limit = min(safe_limit * 3, 200)
    seen_calls = (await db.execute(
        select(SeenCall)
        .where(
            SeenCall.source_id == source.id,
            SeenCall.relevance_score.is_not(None),
            SeenCall.relevance_score >= min_score,
        )
        .order_by(SeenCall.relevance_score.desc(), SeenCall.first_seen.desc())
        .limit(query_limit)
    )).scalars().all()

    deduped_calls = []
    seen_keys: set[str] = set()
    for call in seen_calls:
        key = _dedupe_call_key(call.title, call.url)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_calls.append(call)
        if len(deduped_calls) >= safe_limit:
            break

    seen_call_ids = [str(c.id) for c in deduped_calls]
    feedback_by_seen_call = {}
    if seen_call_ids:
        feedback_rows = (await db.execute(
            select(CallFeedback.seen_call_id, CallFeedback.label)
            .where(
                CallFeedback.user_id == user.id,
                CallFeedback.seen_call_id.in_(seen_call_ids),
            )
        )).all()
        feedback_by_seen_call = {str(seen_call_id): label for seen_call_id, label in feedback_rows}

    framework_root = _framework_root()
    source_slug = derive_source_slug(source.label, source.url)
    scored_calls = []
    for c in deduped_calls:
        call_slug = derive_call_slug(c.title, c.url)
        call_dir = get_call_workspace_dir(framework_root, source_slug, call_slug)
        prepared = _load_prepare_status(call_dir)
        scored_calls.append(
            {
                "id": str(c.id),
                "title": c.title,
                "url": c.url,
                "deadline": c.deadline,
                "summary": c.summary,
                "score": c.relevance_score,
                "reasons": [c.relevance_reason] if c.relevance_reason else [],
                "first_seen": str(c.first_seen) if c.first_seen else None,
                "feedback_label": feedback_by_seen_call.get(str(c.id)),
                "prepare_status": prepared.get("status", "not_prepared"),
                "prepared_at": prepared.get("prepared_at"),
                "workspace_path": str(call_dir),
                "prepared_documents_downloaded": int(prepared.get("documents_downloaded", 0)),
                "prepared_documents_errors": int(prepared.get("documents_errors", 0)),
            }
        )

    return {
        "source": {
            "id": str(source.id),
            "label": source.label or source.url,
            "status": source.last_status or "pending",
            "last_checked": str(source.last_checked) if source.last_checked else None,
        },
        "calls": scored_calls,
        "scored": True,
    }
