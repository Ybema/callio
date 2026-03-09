from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.database import get_db, AsyncSessionLocal
from app.config import settings
from app.models.user import User
from app.models.source import Source
from app.models.profile import UserProfile
from app.models.call import SeenCall, CallFeedback
from app.routers.auth import get_current_user
from app.services.scraper import fetch_calls_smart, call_hash, call_hash_url
from app.services.adapters import get_adapter
from app.services.matcher import score_calls
from app.services.framework_handoff import handoff_calls_to_framework
import datetime
import logging

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)

async def scan_sources(user_id: str):
    """Background task: scan all sources for a user."""
    async with AsyncSessionLocal() as db:
        profile = (await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )).scalar_one_or_none()
        current_matcher_hash = (profile.matcher_profile_hash or "").strip() if profile else ""
        provider = (settings.matcher_llm_provider or "anthropic").strip().lower()
        has_llm_key = bool((settings.anthropic_api_key or "").strip()) if provider == "anthropic" else bool((settings.openai_api_key or "").strip())

        feedback_items: list[dict] = []
        if profile:
            feedback_rows = (await db.execute(
                select(CallFeedback, SeenCall, Source)
                .join(SeenCall, CallFeedback.seen_call_id == SeenCall.id)
                .join(Source, SeenCall.source_id == Source.id)
                .where(CallFeedback.user_id == user_id)
                .order_by(CallFeedback.created_at.desc())
                .limit(300)
            )).all()
            feedback_items = [
                {
                    "label": fb.label,
                    "title": seen.title,
                    "summary": seen.summary,
                    "source_keywords": src.keywords or [],
                }
                for fb, seen, src in feedback_rows
            ]

        sources = (await db.execute(
            select(Source).where(Source.user_id == user_id, Source.is_active == True)
        )).scalars().all()

        for source in sources:
            try:
                adapter = get_adapter(source.url)
                if adapter:
                    filter_config = (source.crawl_config or {}).get("filter_config")
                    calls = await adapter.fetch_calls(
                        max_calls=settings.crawler_max_calls_per_source,
                        filter_config=filter_config,
                    )
                    source.fetch_mode = "playwright"
                    new_config = dict(source.crawl_config or {})
                else:
                    calls, new_config = await fetch_calls_smart(
                        url=source.url,
                        fetch_mode=(
                            (source.crawl_config or {}).get("effective_fetch_mode", "auto")
                            if source.crawl_config
                            else ("playwright" if source.fetch_mode == "playwright" else "auto")
                        ),
                        crawl_config=source.crawl_config or {},
                        max_calls=settings.crawler_max_calls_per_source,
                        max_pages=settings.crawler_max_pages,
                        max_listing_links=settings.crawler_max_listing_links,
                    )
                source.crawl_config = new_config

                seen = set((await db.execute(
                    select(SeenCall.call_hash).where(SeenCall.source_id == source.id)
                )).scalars().all())
                seen_urls = (await db.execute(
                    select(SeenCall.url).where(SeenCall.source_id == source.id)
                )).scalars().all()
                seen_url_hashes = {call_hash_url(url or "") for url in seen_urls if url}

                new_count = 0
                new_calls = []
                for call in calls:
                    legacy_hash = call_hash(call["title"], call["url"])
                    url_hash = call_hash_url(call["url"])
                    if (
                        url_hash not in seen
                        and legacy_hash not in seen
                        and url_hash not in seen_url_hashes
                    ):
                        new_count += 1
                        call_with_hash = dict(call)
                        call_with_hash["call_hash"] = url_hash
                        new_calls.append(call_with_hash)
                        db.add(SeenCall(
                            source_id=source.id,
                            call_hash=url_hash,
                            title=call["title"],
                            url=call["url"],
                            deadline=call.get("deadline"),
                            summary=call.get("summary"),
                        ))
                        # Keep in-memory sets updated to avoid duplicates in same run.
                        seen.add(url_hash)
                        seen_url_hashes.add(url_hash)

                source.last_status = "ok"
                source.last_error = None
                logger.info(f"Scan {source.label}: {new_count} new calls")
                if new_calls:
                    handoff_result = handoff_calls_to_framework(source, new_calls)
                    logger.info(
                        "Scan handoff source %s: created=%s skipped=%s errors=%s",
                        source.id,
                        handoff_result["created"],
                        handoff_result["skipped"],
                        handoff_result["errors"],
                    )

                if profile and has_llm_key:
                    if current_matcher_hash:
                        unscored_calls = (await db.execute(
                            select(SeenCall)
                            .where(
                                SeenCall.source_id == source.id,
                                or_(
                                    SeenCall.relevance_score.is_(None),
                                    SeenCall.scored_profile_hash.is_(None),
                                    SeenCall.scored_profile_hash != current_matcher_hash,
                                ),
                            )
                            .order_by(SeenCall.first_seen.desc())
                        )).scalars().all()
                    else:
                        unscored_calls = (await db.execute(
                            select(SeenCall)
                            .where(
                                SeenCall.source_id == source.id,
                                SeenCall.relevance_score.is_(None),
                            )
                            .order_by(SeenCall.first_seen.desc())
                        )).scalars().all()
                    if unscored_calls:
                        calls_to_score = [
                            {
                                "id": str(c.id),
                                "title": c.title,
                                "url": c.url,
                                "deadline": c.deadline,
                                "summary": c.summary,
                                "source_id": str(source.id),
                                "source_label": source.label or source.url,
                                "source_keywords": source.keywords or [],
                                "first_seen": str(c.first_seen) if c.first_seen else None,
                            }
                            for c in unscored_calls
                        ]
                        scored = await score_calls(
                            calls_to_score,
                            profile.context_text or profile.description or "",
                            profile.org_type,
                            (profile.trl_min, profile.trl_max),
                            feedback_items=feedback_items,
                            focus_domains=profile.focus_domains or [],
                        )
                        scored_map = {
                            str(item.get("id")): (
                                int(item.get("score", 0)),
                                (item.get("reasons") or ["Not relevant"])[0],
                            )
                            for item in scored
                        }
                        scored_at = datetime.datetime.utcnow()
                        for row in unscored_calls:
                            cached = scored_map.get(str(row.id))
                            if cached:
                                row.relevance_score = cached[0]
                                row.relevance_reason = cached[1]
                            else:
                                row.relevance_score = 0
                                row.relevance_reason = "Not relevant"
                            row.scored_at = scored_at
                            row.scored_profile_hash = current_matcher_hash or None

            except Exception as e:
                source.last_status = "error"
                source.last_error = str(e)[:500]
                logger.error(f"Scan error {source.label}: {e}")

            source.last_checked = datetime.datetime.utcnow()
            await db.commit()


@router.post("/scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate scan of all user's sources."""
    sources = (await db.execute(
        select(Source).where(Source.user_id == user.id, Source.is_active == True)
    )).scalars().all()
    for source in sources:
        source.last_status = "pending"
        source.last_error = None
    await db.commit()

    background_tasks.add_task(scan_sources, str(user.id))
    return {
        "status": "scanning",
        "pending_sources": len(sources),
        "message": "Scan started in background. Dashboard will update as sources finish.",
    }
