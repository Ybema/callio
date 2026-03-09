from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from urllib.parse import urlparse
from typing import Any
from app.database import get_db
from app.models.source import Source
from app.models.user import User, PlanTier
from app.routers.auth import get_current_user
from app.services.adapters import get_filter_options_for_url
from pydantic import BaseModel
router = APIRouter(prefix="/sources", tags=["sources"])

SOURCE_LIMITS = {PlanTier.free: 3, PlanTier.pro: 999, PlanTier.team: 999}

class SourceCreate(BaseModel):
    url: str
    label: str | None = None
    keywords: list[str] = []
    filter_config: dict[str, Any] | None = None


class SourceUpdate(BaseModel):
    url: str
    label: str | None = None
    keywords: list[str] = []
    filter_config: dict[str, Any] | None = None


class SourceOut(BaseModel):
    id: str
    url: str
    label: str | None
    keywords: list[str]
    fetch_mode: str
    origin_country_code: str | None
    last_checked: datetime | None
    last_status: str | None
    last_error: str | None
    crawl_config: dict | None = None
    class Config: from_attributes = True

class SourceListOut(BaseModel):
    items: list[SourceOut]
    total: int
    page: int
    page_size: int
    pages: int


class SourceDetectFiltersRequest(BaseModel):
    url: str


class SourceFilterOptionsOut(BaseModel):
    options: list[dict]
    filter_config: dict[str, Any]


def infer_country_code_from_url(url: str) -> str | None:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    if not host:
        return None
    tld = host.split(".")[-1]
    if len(tld) == 2 and tld.isalpha():
        return tld.upper()
    return None


def normalize_filter_config(url: str, raw_filter_config: dict[str, Any] | None) -> dict[str, Any]:
    if not raw_filter_config:
        return {}

    options = get_filter_options_for_url(url)
    if not options:
        return {}

    normalized: dict[str, Any] = {}
    for opt in options:
        key = str(opt.get("key") or "").strip()
        filter_type = str(opt.get("type") or "").strip()
        allowed_values = {
            str(item.get("value"))
            for item in (opt.get("options") or [])
            if item.get("value") is not None
        }
        if not key or key not in raw_filter_config:
            continue

        current = raw_filter_config.get(key)
        if filter_type == "single-select":
            value = None
            if isinstance(current, list):
                value = str(current[0]) if current else None
            elif current is not None:
                value = str(current)
            if value and value in allowed_values:
                normalized[key] = value
        else:
            values = current if isinstance(current, list) else [current]
            cleaned = [str(v) for v in values if v is not None and str(v) in allowed_values]
            if cleaned:
                normalized[key] = cleaned

    return normalized


@router.get("/", response_model=SourceListOut)
async def list_sources(
    country: str | None = Query(default=None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    status: str | None = Query(default=None),
    fetch_mode: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Source).where(Source.user_id == user.id)
    count_query = select(func.count(Source.id)).where(Source.user_id == user.id)

    if country:
        normalized_country = country.strip().upper()
        query = query.where(Source.origin_country_code == normalized_country)
        count_query = count_query.where(Source.origin_country_code == normalized_country)

    if status:
        normalized_status = status.strip().lower()
        query = query.where(Source.last_status == normalized_status)
        count_query = count_query.where(Source.last_status == normalized_status)

    if fetch_mode:
        normalized_mode = fetch_mode.strip().lower()
        query = query.where(Source.fetch_mode == normalized_mode)
        count_query = count_query.where(Source.fetch_mode == normalized_mode)

    total = (await db.execute(count_query)).scalar_one()
    offset = (page - 1) * page_size
    query = query.order_by(Source.created_at.desc()).offset(offset).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    pages = (total + page_size - 1) // page_size if total else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }

@router.post("/", response_model=SourceOut)
async def add_source(req: SourceCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = len((await db.execute(select(Source).where(Source.user_id == user.id, Source.is_active == True))).scalars().all())
    limit = SOURCE_LIMITS.get(user.plan, 3)
    if count >= limit:
        raise HTTPException(status_code=403, detail=f"Source limit reached for {user.plan} plan ({limit} sources)")
    normalized_country = infer_country_code_from_url(req.url)
    source = Source(
        user_id=user.id,
        url=req.url,
        label=req.label,
        keywords=req.keywords,
        fetch_mode="fetch",
        origin_country_code=normalized_country,
        crawl_config={"filter_config": normalize_filter_config(req.url, req.filter_config)},
    )
    db.add(source)
    await db.commit()
    return source


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: str,
    req: SourceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(select(Source).where(Source.id == source_id, Source.user_id == user.id))).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.url = req.url
    source.label = req.label
    source.keywords = req.keywords
    source.origin_country_code = infer_country_code_from_url(req.url)
    current_config = dict(source.crawl_config or {})
    current_config["filter_config"] = normalize_filter_config(req.url, req.filter_config)
    source.crawl_config = current_config

    await db.commit()
    await db.refresh(source)
    return source


@router.post("/detect-filters")
async def detect_filters(
    req: SourceDetectFiltersRequest,
    user: User = Depends(get_current_user),
):
    _ = user  # enforce auth
    return get_filter_options_for_url(req.url)


@router.get("/{source_id}/filter-options", response_model=SourceFilterOptionsOut)
async def get_source_filter_options(
    source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(select(Source).where(Source.id == source_id, Source.user_id == user.id))).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return {
        "options": get_filter_options_for_url(source.url),
        "filter_config": (source.crawl_config or {}).get("filter_config", {}),
    }


@router.put("/{source_id}/filters", response_model=SourceOut)
async def update_source_filters(
    source_id: str,
    req: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(select(Source).where(Source.id == source_id, Source.user_id == user.id))).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    current_config = dict(source.crawl_config or {})
    current_config["filter_config"] = normalize_filter_config(source.url, req)
    source.crawl_config = current_config
    await db.commit()
    await db.refresh(source)
    return source

@router.delete("/{source_id}")
async def delete_source(source_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    source = (await db.execute(select(Source).where(Source.id == source_id, Source.user_id == user.id))).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"ok": True}
