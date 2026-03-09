"""
Source-specific adapters that bypass the generic crawler for known funding portals.
Each adapter returns clean, structured call data via a dedicated API or optimized scraper.
"""
from .base import BaseAdapter
from .rvo import RvoAdapter

ADAPTERS = {
    "rvo.nl": RvoAdapter,
}


def get_adapter(url: str):
    """Return an adapter instance if the URL matches a known source, else None."""
    url_lower = (url or "").lower()
    for pattern, cls in ADAPTERS.items():
        if pattern in url_lower:
            return cls()
    return None


def get_filter_options_for_url(url: str) -> list[dict]:
    adapter = get_adapter(url)
    if not adapter:
        return []
    return adapter.get_filter_options()


__all__ = ["BaseAdapter", "get_adapter", "get_filter_options_for_url", "ADAPTERS"]
