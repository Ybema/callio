"""
RVO.nl adapter — scrapes the subsidies listing via Playwright.
The JSON API is broken (ignores pagination/filters, caps at 50).
The HTML page is JS-rendered, paginated at 50 per page.

Default URL: https://www.rvo.nl/subsidies-financiering (loads with status=open+upcoming)
We filter client-side to "Open voor aanvragen" only.
"""
import re
from urllib.parse import quote_plus

from playwright.async_api import async_playwright
from app.services.scraper import call_hash_url
from .base import BaseAdapter

BASE_URL = "https://www.rvo.nl"
# Paginated listing — page param is 0-indexed
LISTING_URL = "https://www.rvo.nl/subsidies-financiering?sortBy=title&sortOrder=ASC&status=3294&page={page}"
MAX_PAGES = 5

# Only keep strictly open calls
OPEN_STATUS = "open voor aanvragen"


def _parse_link_text(text: str) -> tuple[str, str | None, str | None]:
    """
    RVO link text is concatenated: "InnovatiekredietOpen voor aanvragenKrediet voor..."
    Split into (title, status, summary).
    """
    status_patterns = [
        "Bijna open voor aanvragen",
        "Binnenkort open voor aanvragen",
        "Open voor aanvragen",
        "Tijdelijk gesloten voor aanvragen",
        "Gesloten voor aanvragen",
    ]
    for pat in status_patterns:
        if pat in text:
            parts = text.split(pat, 1)
            title = parts[0].strip()
            summary = parts[1].strip() if len(parts) > 1 else None
            return title, pat, summary
    return text.strip(), None, None


def _build_listing_url(page: int, categories: list[str] | None = None) -> str:
    url = LISTING_URL.format(page=page)
    if not categories:
        return url
    # RVO filter pattern: ?category[slug]=slug
    params = [f"category[{quote_plus(slug)}]={quote_plus(slug)}" for slug in categories if slug]
    if not params:
        return url
    return f"{url}&{'&'.join(params)}"


class RvoAdapter(BaseAdapter):
    """Scrape open subsidies from RVO via Playwright (JS-rendered, multi-page)."""

    @classmethod
    def get_filter_options(cls) -> list[dict]:
        # Verified against RVO category paths and URL filter pattern used by the site.
        return [
            {
                "key": "category",
                "label": "Categorie",
                "type": "multi-select",
                "options": [
                    {
                        "value": "innovatie-onderzoek-en-onderwijs",
                        "label": "Innovatie, Onderzoek & Onderwijs",
                    },
                    {
                        "value": "internationaal-ondernemen",
                        "label": "Internationaal ondernemen",
                    },
                    {
                        "value": "duurzaam-ondernemen",
                        "label": "Duurzaam ondernemen",
                    },
                    {
                        "value": "financiering",
                        "label": "Financiering",
                    },
                    {
                        "value": "agrarisch-ondernemen",
                        "label": "Agrarisch ondernemen",
                    },
                ],
            }
        ]

    async def fetch_calls(
        self,
        max_calls: int = 200,
        browser=None,
        filter_config: dict | None = None,
    ) -> list[dict]:
        own_browser = browser is None
        pw = None

        try:
            if own_browser:
                pw = await async_playwright().start()
                browser = await pw.chromium.launch(headless=True)

            calls = []
            seen_urls = set()
            category_filters = filter_config.get("category", []) if isinstance(filter_config, dict) else []
            if isinstance(category_filters, str):
                category_filters = [category_filters]
            category_filters = [str(item).strip() for item in category_filters if str(item).strip()]

            for page_num in range(MAX_PAGES):
                page = await browser.new_page()
                url = _build_listing_url(page=page_num, categories=category_filters)
                await page.goto(url, wait_until="networkidle", timeout=30000)

                raw_links = await page.eval_on_selector_all(
                    'a[href*="/subsidies-financiering/"]',
                    """els => els.map(el => ({
                        text: el.textContent.trim(),
                        href: el.href
                    }))"""
                )
                await page.close()

                if not raw_links:
                    break

                new_on_page = 0
                for item in raw_links:
                    text = item.get("text", "").strip()
                    href = item.get("href", "").strip()

                    if not text or len(text) < 5 or not href:
                        continue
                    if href.rstrip("/").endswith("/subsidies-financiering"):
                        continue
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    title, status, summary = _parse_link_text(text)
                    if not title or len(title) < 3:
                        continue

                    # Strict: only "Open voor aanvragen"
                    if not status or status.lower() != OPEN_STATUS:
                        continue

                    calls.append({
                        "title": title[:200],
                        "url": href,
                        "deadline": None,
                        "summary": summary[:500] if summary else None,
                        "hash": call_hash_url(href),
                        "score": 3,
                    })
                    new_on_page += 1

                    if len(calls) >= max_calls:
                        break

                if new_on_page == 0 or len(calls) >= max_calls:
                    break

            return calls

        finally:
            if own_browser:
                if browser:
                    await browser.close()
                if pw:
                    await pw.stop()
