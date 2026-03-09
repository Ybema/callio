"""
Smart scraping engine for funding calls.

The crawler discovers call links from source pages, listing pages, and pagination.
It intentionally avoids keyword gating at discovery time. Relevance filtering is
performed later by the matcher.
"""
import hashlib
import re
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; FundWatch/1.0; +https://sustainovate.com)"

DEADLINE_PATTERN = re.compile(
    r"(?:deadline|closing|due|closes?|submission|end date)[:\s]*"
    r"(\d{1,2}[\s./-]\w+[\s./-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

CALL_INDICATORS = re.compile(
    r"call for|funding|grant|subsid|proposal|programme|program|tender|"
    r"opportunity|expression of interest|open call|aanvraag|regeling|"
    r"utlysning|søknad|tilskud",
    re.IGNORECASE,
)

LISTING_INDICATORS = re.compile(
    r"\ball calls\b|\bopen calls\b|\bview all\b|\bbrowse\b|"
    r"\balle regelingen\b|\baktuelle utlysninger\b|\bopportunities\b|"
    r"\bfunding calls\b|\btenders\b",
    re.IGNORECASE,
)

PAGINATION_INDICATORS = re.compile(
    r"^(next|prev|previous|volgende|neste|older|newer|\d{1,3})$",
    re.IGNORECASE,
)

CALL_PATH_HINTS = (
    "/call",
    "/opportunit",
    "/regeling",
    "/subsid",
    "/funding",
    "/grant",
    "/tender",
    "/programme",
    "/utlysning",
)

LISTING_PATH_HINTS = ("/calls", "/opportunities", "/tenders")
JS_RENDER_HINTS = ("id=\"root\"", "data-reactroot", "ng-app", "<noscript")


async def fetch_calls(
    url: str,
    keywords: list[str] | None = None,
    use_playwright: bool = False,
) -> list[dict]:
    """
    Backward-compatible wrapper around smart crawling.
    `keywords` is ignored by design.
    """
    mode = "playwright" if use_playwright else "auto"
    calls, _ = await fetch_calls_smart(url=url, fetch_mode=mode, crawl_config=None, max_calls=50)
    return calls


async def fetch_calls_smart(
    url: str,
    fetch_mode: str = "auto",
    crawl_config: dict | None = None,
    max_calls: int = 50,
    max_pages: int = 5,
    max_listing_links: int = 3,
) -> tuple[list[dict], dict]:
    """
    Smart crawler that discovers call links on source, listing, and pagination pages.
    Returns (calls, updated_crawl_config).
    """
    crawl_config = dict(crawl_config or {})
    queue: list[tuple[str, int, str]] = [(url, 0, "root")]
    visited_pages: set[str] = set()
    visited_links: set[str] = set()
    calls_by_hash: dict[str, dict] = {}
    discovered_listing_urls: list[str] = []
    pages_followed = 0

    preset_listing_urls = crawl_config.get("listing_urls") or []
    for listing_url in preset_listing_urls:
        normalized = _normalize_url(url, listing_url)
        if normalized and normalized not in visited_pages:
            queue.append((normalized, 1, "listing"))

    effective_mode = crawl_config.get("effective_fetch_mode")
    if effective_mode not in {"fetch", "playwright"}:
        effective_mode = fetch_mode

    while queue and len(calls_by_hash) < max_calls and pages_followed < max_pages:
        page_url, depth, page_kind = queue.pop(0)
        if page_url in visited_pages:
            continue
        visited_pages.add(page_url)
        pages_followed += 1

        html, used_mode = await _fetch_page_with_auto(page_url, effective_mode)
        if used_mode in {"fetch", "playwright"}:
            effective_mode = used_mode

        soup = BeautifulSoup(html, "html.parser")
        call_links, listing_links, pagination_links = _classify_links(soup, page_url)

        for link in call_links:
            call = _extract_call_from_link(link, page_url)
            if not call:
                continue
            h = call["hash"]
            if h in calls_by_hash:
                continue
            calls_by_hash[h] = call
            if len(calls_by_hash) >= max_calls:
                break

        if len(calls_by_hash) >= max_calls:
            break

        root_call_count = len(call_links) if page_kind == "root" else 0
        allow_listing_follow = page_kind == "root" and root_call_count < 5
        if allow_listing_follow:
            for listing_url in listing_links[:max_listing_links]:
                if listing_url in visited_pages:
                    continue
                queue.append((listing_url, depth + 1, "listing"))
                discovered_listing_urls.append(listing_url)

        for next_url in pagination_links:
            if next_url in visited_pages:
                continue
            queue.append((next_url, depth, "pagination"))

    calls = list(calls_by_hash.values())
    calls.sort(key=lambda item: item.get("score", 0), reverse=True)
    calls = calls[:max_calls]

    updated_crawl_config = {
        "effective_fetch_mode": "playwright" if effective_mode == "playwright" else "fetch",
        "listing_urls": _unique_preserve_order(
            [*_clean_urls(url, preset_listing_urls), *discovered_listing_urls]
        )[:max_listing_links],
        "last_pages_followed": pages_followed,
    }
    return calls, updated_crawl_config


async def _fetch_page_with_auto(url: str, mode: str) -> tuple[str, str]:
    mode = (mode or "auto").strip().lower()
    if mode == "playwright":
        html = await _playwright_fetch(url)
        return html, "playwright"
    if mode == "fetch":
        html = await _http_fetch(url)
        return html, "fetch"

    html = await _http_fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    link_count = len(soup.find_all("a", href=True))
    if link_count < 3 and _needs_playwright(html):
        try:
            pw_html = await _playwright_fetch(url)
            return pw_html, "playwright"
        except Exception:
            return html, "fetch"
    return html, "fetch"


async def _http_fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text


async def _playwright_fetch(url: str) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        content = await page.content()
        await browser.close()
        return content


def _classify_links(soup: BeautifulSoup, base_url: str) -> tuple[list, list[str], list[str]]:
    call_links = []
    listing_urls: list[str] = []
    pagination_urls: list[str] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        text = _clean_text(link.get_text(" ", strip=True))
        href = link.get("href", "")
        normalized = _normalize_url(base_url, href)
        if not normalized or normalized in seen_urls:
            continue
        if not _is_same_host(base_url, normalized):
            continue
        seen_urls.add(normalized)

        parent = link.parent
        context = _clean_text(parent.get_text(" ", strip=True) if parent else "")
        rel = " ".join(link.get("rel", [])) if isinstance(link.get("rel"), list) else str(link.get("rel", ""))
        in_nav = bool(link.find_parent("nav"))

        href_l = normalized.lower()
        text_l = text.lower()
        context_l = context.lower()

        is_pagination = (
            in_nav
            or "next" in rel.lower()
            or PAGINATION_INDICATORS.match(text_l or "") is not None
            or re.search(r"(?:[?&](page|p|offset)=\d+)|/page/\d+", href_l) is not None
        )
        if is_pagination:
            pagination_urls.append(normalized)
            continue

        has_deadline = DEADLINE_PATTERN.search(context_l or text_l) is not None
        is_call = (
            (10 <= len(text) <= 300 and CALL_INDICATORS.search(text_l) is not None)
            or any(hint in href_l for hint in CALL_PATH_HINTS)
            or has_deadline
        )
        if is_call:
            call_links.append(link)
            continue

        is_listing = (
            LISTING_INDICATORS.search(text_l) is not None
            or any(hint in href_l for hint in LISTING_PATH_HINTS)
            or ("?page=" in href_l or "?p=" in href_l)
            or "call" in text_l and "open" in text_l
        )
        if is_listing:
            listing_urls.append(normalized)

    return call_links, _unique_preserve_order(listing_urls), _unique_preserve_order(pagination_urls)


def _extract_call_from_link(link, base_url: str) -> dict | None:
    text = _clean_text(link.get_text(" ", strip=True))
    href = link.get("href", "")
    normalized = _normalize_url(base_url, href)
    if not normalized:
        return None

    parent = link.parent
    context = _clean_text(parent.get_text(" ", strip=True) if parent else "")
    title = text or normalized
    if len(title) < 5:
        return None

    deadline_match = DEADLINE_PATTERN.search(context)
    deadline = deadline_match.group(1) if deadline_match else None
    score = 3 if CALL_INDICATORS.search(title.lower()) else 1
    if deadline:
        score += 2

    h = call_hash(title, normalized)
    summary = context[:300] if context and context != title else None
    return {
        "title": title[:200],
        "url": normalized,
        "deadline": deadline,
        "summary": summary,
        "hash": h,
        "score": score,
    }


def _needs_playwright(html: str) -> bool:
    lower = html.lower()
    if any(hint in lower for hint in JS_RENDER_HINTS):
        return True
    if "window.__next_data__" in lower or "data-server-rendered" in lower:
        return True
    return False


def _normalize_url(base_url: str, raw_href: str) -> str | None:
    href = (raw_href or "").strip()
    if not href or href.startswith("#"):
        return None
    if href.startswith(("mailto:", "tel:", "javascript:")):
        return None

    absolute = urljoin(base_url, href)
    clean, _ = urldefrag(absolute)
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"}:
        return None
    return clean


def _is_same_host(base_url: str, target_url: str) -> bool:
    base = urlparse(base_url).hostname or ""
    target = urlparse(target_url).hostname or ""
    return bool(base and target and base == target)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _clean_urls(base_url: str, urls: list[str]) -> list[str]:
    cleaned = []
    for url in urls:
        normalized = _normalize_url(base_url, url)
        if normalized:
            cleaned.append(normalized)
    return cleaned


def call_hash(title: str, url: str) -> str:
    return hashlib.sha256(f"{title}{url}".encode()).hexdigest()[:16]


def call_hash_url(url: str) -> str:
    normalized = (url or "").strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
