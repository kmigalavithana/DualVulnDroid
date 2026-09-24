"""
SmartApp's normalization layer: turns raw SerpApi Google Play provider
dicts into SmartApp's own normalized shape. Every field is read
defensively (never assumed present) - a field the provider didn't return
becomes None here, never an invented value.

This module never touches ratings/trackers/ads/open-source/offline-
support beyond what the Google Play provider itself actually reports for
rating/reviewCount - see app_model.dart on the Flutter side for why
privacy/ads/open-source/offline fields are deliberately NOT populated
from Google Play metadata (Part 11: "Google Play metadata alone must NOT
be treated as authoritative tracker/privacy information").
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from . import provider
from .cache import TTLCache
from .enrichment import apply_store_facts, default_enricher
from .metadata import play_store_facts
from .models import SmartAppDetails, SmartAppItem

log = logging.getLogger("smartapp.service")

# Raw Google Play product pages, cached per (package, country, language) so
# App Details and search enrichment never pay twice for the same page.
_details_cache = TTLCache(ttl_seconds=24 * 60 * 60, max_entries=1024)


def _search_details_limit() -> int:
    """How many search results also get their Google Play product page
    (price / "Contains ads" / data safety). Each costs one SerpApi credit,
    so it is opt-in: SMARTAPP_SEARCH_DETAILS_LIMIT (default 0)."""
    try:
        return max(0, min(20, int(os.getenv("SMARTAPP_SEARCH_DETAILS_LIMIT", "0"))))
    except ValueError:
        return 0


def _cached_raw_details(package_name: str, country: str, language: str) -> Optional[dict[str, Any]]:
    return _details_cache.get_or_load(
        ("google_play_details", package_name, country, language),
        lambda: provider.get_app_details(package_name, country=country, language=language),
    )

# SmartApp's 11 existing categories, mapped to a real Google Play search
# QUERY - not a guessed Google Play category-id enum (SerpApi's own docs
# do not exhaustively document one), per the task's own explicit fallback:
# "If provider category mapping is uncertain, use a search query instead."
CATEGORY_QUERY_MAP: dict[str, str] = {
    "Productivity": "productivity",
    "Notes": "notes",
    "Photo Editing": "photo editor",
    "Video Editing": "video editor",
    "PDF & Documents": "pdf reader",
    "Music": "music player",
    "Education": "education learning",
    "Communication": "messenger chat",
    "File Management": "file manager",
    "Browsers": "web browser",
    "Utilities": "utilities tools",
}


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clean_int(value: Any) -> Optional[int]:
    """Parses a real integer out of provider values that are sometimes a
    plain number and sometimes a formatted string (e.g. "10,000+" reviews)
    - extracts the count only when unambiguous, otherwise returns None
    rather than guessing at what a "+"/"M"/"K" suffix actually means."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if text.isdigit():
        return int(text)
    return None


def normalize_search_result(raw: dict[str, Any]) -> SmartAppItem:
    package_name = _clean_str(raw.get("product_id"))
    return SmartAppItem(
        id=package_name,
        name=_clean_str(raw.get("title")),
        packageName=package_name,
        category=_clean_str(raw.get("category")),
        description=_clean_str(raw.get("description")),
        iconUrl=_clean_str(raw.get("thumbnail")),
        rating=_clean_float(raw.get("rating")),
        reviewCount=_clean_int(raw.get("reviews")),
        playStoreUrl=_clean_str(raw.get("link")),
        developer=_clean_str(raw.get("author")),
        realData=True,
        source="google_play",
    )


def _extract_developer(product_info: dict[str, Any]) -> Optional[str]:
    authors = product_info.get("authors")
    if isinstance(authors, list) and authors:
        first = authors[0]
        return _clean_str(first.get("name")) if isinstance(first, dict) else _clean_str(first)
    if isinstance(authors, dict):
        return _clean_str(authors.get("name"))
    return _clean_str(authors)


def _extract_category(raw: dict[str, Any]) -> Optional[str]:
    categories = raw.get("categories")
    if isinstance(categories, list) and categories:
        first = categories[0]
        return _clean_str(first.get("name")) if isinstance(first, dict) else _clean_str(first)
    return None


def _extract_screenshots(media: dict[str, Any]) -> list[str]:
    images = media.get("images") if isinstance(media, dict) else None
    if not isinstance(images, list):
        return []
    return [img for img in (_clean_str(i) for i in images) if img]


def normalize_details(raw: dict[str, Any], package_name: str) -> SmartAppDetails:
    product_info = raw.get("product_info") or {}
    about = raw.get("about_this_app") or {}
    media = raw.get("media") or {}

    return SmartAppDetails(
        id=package_name,
        name=_clean_str(product_info.get("title")),
        packageName=package_name,
        category=_extract_category(raw),
        description=_clean_str(about.get("snippet")),
        iconUrl=_clean_str(product_info.get("thumbnail")),
        rating=_clean_float(product_info.get("rating")),
        reviewCount=_clean_int(product_info.get("reviews")),
        # Only ever the provider's own returned URL - never constructed
        # from the package name (Part 13/18: "Do not construct fake URLs").
        playStoreUrl=_clean_str(product_info.get("link")),
        developer=_extract_developer(product_info),
        realData=True,
        source="google_play",
        version=_clean_str(about.get("version") or product_info.get("version")),
        releaseDate=_clean_str(about.get("released_on")),
        updatedOn=_clean_str(about.get("updated_on")),
        screenshots=_extract_screenshots(media),
    )


def search_apps(
    query: Optional[str] = None,
    category: Optional[str] = None,
    country: str = "us",
    language: str = "en",
    limit: int = 20,
) -> list[SmartAppItem]:
    """Resolves a category into a real search query when no direct query
    is given, calls the real provider, and returns normalized results -
    never a cached/fabricated fallback list."""
    effective_query = (query or "").strip()
    if not effective_query and category:
        effective_query = CATEGORY_QUERY_MAP.get(category, category)
    if not effective_query:
        raise ValueError("Either 'q' or 'category' must be provided.")

    raw_results = provider.search_play_store(effective_query, country=country, language=language)
    normalized = [normalize_search_result(item) for item in raw_results][: max(0, limit)]
    _add_store_facts(normalized[: _search_details_limit()], country, language)
    return default_enricher.enrich(normalized)


def _add_store_facts(apps: list[SmartAppItem], country: str, language: str) -> None:
    """Optional per-result Play product-page facts. A failed page is
    skipped - the search result itself is never lost because of it."""
    def one(app: SmartAppItem) -> None:
        if not app.packageName:
            return
        try:
            raw = _cached_raw_details(app.packageName, country, language)
        except provider.SerpApiError as exc:
            log.warning("store facts unavailable for %s: %s", app.packageName, exc)
            return
        if raw is not None:
            apply_store_facts(app, play_store_facts(raw))

    if apps:
        with ThreadPoolExecutor(max_workers=min(4, len(apps))) as pool:
            list(pool.map(one, apps))


def get_app_details(package_name: str, country: str = "us", language: str = "en") -> Optional[SmartAppDetails]:
    raw = _cached_raw_details(package_name, country, language)
    if raw is None:
        return None
    details = normalize_details(raw, package_name)
    apply_store_facts(details, play_store_facts(raw))
    return default_enricher.enrich([details])[0]
