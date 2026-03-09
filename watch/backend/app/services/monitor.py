"""
Core monitoring loop — runs on schedule, finds new calls, sends alerts.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.source import Source
from app.models.call import SeenCall, Alert
from app.models.user import User
from app.services.scraper import fetch_calls_smart, call_hash, call_hash_url
from app.services.adapters import get_adapter
from app.services.email_service import send_alert
from app.services.framework_handoff import handoff_calls_to_framework
from app.database import AsyncSessionLocal
from app.config import settings
import logging
import datetime

logger = logging.getLogger(__name__)

async def run_monitor():
    """Check all active sources and alert users on new calls."""
    async with AsyncSessionLocal() as db:
        sources = (await db.execute(
            select(Source).where(Source.is_active == True)
        )).scalars().all()

        for source in sources:
            try:
                await check_source(db, source)
                source.last_status = "ok"
                source.last_error = None
            except Exception as e:
                logger.error(f"Error checking source {source.id}: {e}")
                source.last_status = "error"
                source.last_error = str(e)[:500]
            source.last_checked = __import__('datetime').datetime.utcnow()
            await db.commit()

async def check_source(db: AsyncSession, source: Source):
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

    # Load already-seen hashes and URLs for this source.
    seen = (await db.execute(
        select(SeenCall.call_hash).where(SeenCall.source_id == source.id)
    )).scalars().all()
    seen_set = set(seen)
    seen_urls = (await db.execute(
        select(SeenCall.url).where(SeenCall.source_id == source.id)
    )).scalars().all()
    seen_url_hashes = {call_hash_url(url or "") for url in seen_urls if url}

    new_calls = []
    for call in calls:
        legacy_hash = call_hash(call["title"], call["url"])
        url_hash = call_hash_url(call["url"])
        if (
            url_hash not in seen_set
            and legacy_hash not in seen_set
            and url_hash not in seen_url_hashes
        ):
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
            # Keep in-memory sets updated to prevent duplicates within same scan.
            seen_set.add(url_hash)
            seen_url_hashes.add(url_hash)

    if new_calls:
        user = await db.get(User, source.user_id)
        if user and user.is_active:
            try:
                await send_alert(
                    to_email=user.email,
                    user_name=user.full_name,
                    new_calls=new_calls,
                    source_label=source.label or source.url,
                )
                user.alert_last_error = None
                user.alert_last_error_at = None
                user.alert_last_ok_at = datetime.datetime.utcnow()
            except Exception as e:
                # Alerting is a user-level service concern, not source health.
                user.alert_last_error = str(e)[:500]
                user.alert_last_error_at = datetime.datetime.utcnow()
                logger.warning(f"Alert send failed for source {source.id}: {e}")
            for call in new_calls:
                db.add(Alert(
                    user_id=user.id,
                    source_id=source.id,
                    call_title=call["title"],
                    call_url=call["url"],
                ))
        handoff_result = handoff_calls_to_framework(source, new_calls)
        logger.info(
            "Source %s handoff: created=%s skipped=%s errors=%s",
            source.id,
            handoff_result["created"],
            handoff_result["skipped"],
            handoff_result["errors"],
        )
    logger.info(f"Source {source.url}: {len(new_calls)} new calls found")
