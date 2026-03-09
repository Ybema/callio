from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import httpx
import logging
import re
import hashlib
import json

from app.database import get_db
from app.models.profile import UserProfile, OrgType, CollaborationPref, DeadlineHorizon
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])
logger = logging.getLogger(__name__)

class ProfileBase(BaseModel):
    organisation_type: str | None = None
    country: str | None = None
    trl_min: str | None = None
    trl_max: str | None = None
    description: str | None = None
    context_url: str | None = None
    focus_domains: list[str] | None = None
    problem_frames: list[str] | None = None
    funding_types: list[str] | None = None
    collaboration_preference: list[str] | None = None
    budget_min: str | None = None
    budget_max: str | None = None
    deadline_horizon: str | None = None


class ProfileUpsert(ProfileBase):
    pass


class ProfileOut(ProfileBase):
    id: str | None = None
    user_id: str | None = None

    class Config:
        from_attributes = True


ORG_TYPE_TO_LABEL = {
    OrgType.academic: "Academic/Research",
    OrgType.sme: "SME",
    OrgType.large_enterprise: "Large Enterprise",
    OrgType.startup: "Startup",
    OrgType.ngo: "NGO/Non-profit",
    OrgType.public_authority: "Public Authority",
    OrgType.consortium: "Consortium",
}
LABEL_TO_ORG_TYPE = {v: k for k, v in ORG_TYPE_TO_LABEL.items()}

COLLAB_TO_LABEL = {
    CollaborationPref.solo: "Single entity",
    CollaborationPref.open: "Open to consortium",
    CollaborationPref.required: "Consortium required",
}
LABEL_TO_COLLAB = {v: k for k, v in COLLAB_TO_LABEL.items()}

DEADLINE_TO_LABEL = {
    DeadlineHorizon.any: "Any EU Horizon deadline",
    DeadlineHorizon.m3: "EU Horizon deadline within 3 months",
    DeadlineHorizon.m6: "EU Horizon deadline in 3-6 months",
    DeadlineHorizon.m12: "EU Horizon deadline in 6-12 months",
}
LABEL_TO_DEADLINE = {v: k for k, v in DEADLINE_TO_LABEL.items()}


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _profile_to_out(profile: UserProfile | None, user_id: str) -> ProfileOut:
    if not profile:
        return ProfileOut(user_id=user_id)
    return ProfileOut(
        id=str(profile.id),
        user_id=str(profile.user_id),
        organisation_type=ORG_TYPE_TO_LABEL.get(profile.org_type, None) if profile.org_type else None,
        country=(profile.country or "").upper() if profile.country else None,
        trl_min=str(profile.trl_min) if profile.trl_min is not None else None,
        trl_max=str(profile.trl_max) if profile.trl_max is not None else None,
        description=profile.description,
        context_url=profile.context_url,
        focus_domains=profile.focus_domains or [],
        problem_frames=profile.problem_frames or [],
        funding_types=profile.funding_types or [],
        collaboration_preference=[COLLAB_TO_LABEL[CollaborationPref(v)] for v in (profile.collaboration or []) if v in CollaborationPref._value2member_map_] if profile.collaboration else [],
        budget_min=str(profile.budget_min) if profile.budget_min is not None else "No preference",
        budget_max=str(profile.budget_max) if profile.budget_max is not None else "No preference",
        deadline_horizon=DEADLINE_TO_LABEL.get(profile.deadline_horizon, "Any EU Horizon deadline") if profile.deadline_horizon else "Any EU Horizon deadline",
    )


def _normalize_whitespace(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_string_list(value: list[str] | None, max_items: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _normalize_whitespace(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text[:80])
        if len(out) >= max_items:
            break
    return out


def _normalize_context_url(value: str | None) -> str | None:
    url = _normalize_whitespace(value)
    if not url:
        return None
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        return None
    return url[:1024]


def _matcher_profile_hash(payload: dict) -> str:
    # Stable matcher fingerprint for auditability and selective re-scoring.
    canonical = {
        "org_type": payload.get("org_type"),
        "trl_min": payload.get("trl_min"),
        "trl_max": payload.get("trl_max"),
        "description": _normalize_whitespace(payload.get("description")),
        "context_text": _normalize_whitespace(payload.get("context_text")),
        "focus_domains": payload.get("focus_domains") or [],
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_effective_matcher_payload(
    profile: UserProfile | None,
    mapped: dict,
) -> dict:
    def get_value(key: str):
        if key in mapped:
            return mapped[key]
        return getattr(profile, key, None) if profile else None

    return {
        "org_type": get_value("org_type"),
        "trl_min": get_value("trl_min"),
        "trl_max": get_value("trl_max"),
        "description": get_value("description"),
        "context_text": get_value("context_text"),
        "focus_domains": get_value("focus_domains"),
    }


async def _fetch_context_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        response = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FundWatch/1.0; +https://sustainovate.com)"},
        )
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    parts: list[str] = []
    if soup.title and soup.title.get_text():
        parts.append(_normalize_whitespace(soup.title.get_text()))
    for el in soup.find_all(["h1", "h2", "p"], limit=30):
        text = _normalize_whitespace(el.get_text(" ", strip=True))
        if len(text) >= 30:
            parts.append(text)

    return _normalize_whitespace(" ".join(parts))[:6000]


@router.get("/", response_model=ProfileOut)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()

    return _profile_to_out(profile, str(user.id))


@router.put("/", response_model=ProfileOut)
async def upsert_profile(
    req: ProfileUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()

    payload = req.model_dump(exclude_unset=True)
    context_url = _normalize_context_url(payload.get("context_url"))
    context_text = None
    context_last_fetched_at = None
    if payload.get("context_url") is not None:
        if context_url:
            try:
                context_text = await _fetch_context_text(context_url)
                context_last_fetched_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning("Could not fetch profile context URL (%s): %s", context_url, exc)
                context_text = None
                context_last_fetched_at = None

    mapped = {
        "org_type": LABEL_TO_ORG_TYPE.get(payload.get("organisation_type")) if payload.get("organisation_type") else None,
        "country": payload.get("country").strip().upper() if payload.get("country") else None,
        "trl_min": _to_int(payload.get("trl_min")),
        "trl_max": _to_int(payload.get("trl_max")),
        "description": payload.get("description"),
        "context_url": context_url,
        "context_text": context_text,
        "context_last_fetched_at": context_last_fetched_at,
        "focus_domains": _normalize_string_list(payload.get("focus_domains")),
        "problem_frames": payload.get("problem_frames") or [],
        "funding_types": payload.get("funding_types") or [],
        "collaboration": [LABEL_TO_COLLAB[label].value for label in (payload.get("collaboration_preference") or []) if label in LABEL_TO_COLLAB] or None,
        "budget_min": _to_int(payload.get("budget_min")),
        "budget_max": _to_int(payload.get("budget_max")),
        "deadline_horizon": LABEL_TO_DEADLINE.get(payload.get("deadline_horizon"), DeadlineHorizon.any),
    }

    if payload.get("context_url") is None:
        mapped.pop("context_url")
        mapped.pop("context_text")
        mapped.pop("context_last_fetched_at")

    old_matcher_hash = profile.matcher_profile_hash if profile else None
    new_matcher_hash = _matcher_profile_hash(_build_effective_matcher_payload(profile, mapped))
    matcher_relevant_changed = old_matcher_hash != new_matcher_hash

    if profile:
        for field, value in mapped.items():
            setattr(profile, field, value)
        profile.matcher_profile_hash = new_matcher_hash
    else:
        profile = UserProfile(user_id=user.id, matcher_profile_hash=new_matcher_hash, **mapped)
        db.add(profile)

    if matcher_relevant_changed:
        logger.info(
            "Profile matcher context changed for user %s: matcher_hash=%s",
            user.id,
            new_matcher_hash,
        )
    else:
        logger.info(
            "Profile updated for user %s with unchanged matcher hash: %s",
            user.id,
            new_matcher_hash,
        )

    await db.commit()
    await db.refresh(profile)
    return _profile_to_out(profile, str(user.id))
