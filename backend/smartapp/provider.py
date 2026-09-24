"""
SmartApp's ONLY integration point with the SerpApi Google Play provider.

SERPAPI_API_KEY is read from the environment (see backend/.env.example)
ONLY in this module, via _require_api_key() below - it is never
hardcoded, never included in any response returned to Flutter, never
logged, and never committed to git (backend/.env is gitignored).

Returns RAW provider dicts exactly as SerpApi sent them - normalization
into SmartApp's own shape happens in service.py, never here, so this
module has exactly one job: talk to the real provider or raise
SerpApiError. Nothing here invents, caches, or falls back to fake data.

Completely isolated from the DualVulnDroid security backend - this module
is not imported by, and does not import, predictor.py, dataflow.py,
security_features.py, the XGBoost model, or any /developer|/apps security
route in app.py.
"""

import os
from typing import Any, Optional

import httpx

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
_TIMEOUT_SECONDS = 10.0


class SerpApiError(Exception):
    """Raised when the SerpApi Google Play provider call fails, is
    misconfigured (missing API key), or returns a provider-side error -
    the caller must surface this honestly (e.g. as an HTTP 502), never
    swallow it into a fake/empty success."""


def _require_api_key() -> str:
    key = os.getenv("SERPAPI_API_KEY")
    if not key:
        raise SerpApiError(
            "SERPAPI_API_KEY is not configured on the server. Set it as an "
            "environment variable (see backend/.env.example) - it must never be hardcoded."
        )
    return key


def _get(params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.get(SERPAPI_ENDPOINT, params=params, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SerpApiError(f"Google Play provider request failed: {exc}") from exc
    data = response.json()
    if isinstance(data, dict) and data.get("error"):
        raise SerpApiError(f"Google Play provider error: {data['error']}")
    return data


def search_play_store(query: str, country: str = "us", language: str = "en") -> list[dict[str, Any]]:
    """Calls SerpApi's real Google Play search engine (engine=google_play,
    store=apps) and returns the RAW list of app-result dicts exactly as
    the provider sent them - each `organic_results` section's `items`,
    flattened into one list. No normalization, no invented fields."""
    params = {
        "engine": "google_play",
        "store": "apps",
        "q": query,
        "gl": country,
        "hl": language,
        "api_key": _require_api_key(),
    }
    data = _get(params)
    apps: list[dict[str, Any]] = []
    for section in data.get("organic_results", []) or []:
        items = section.get("items") if isinstance(section, dict) else None
        if items:
            apps.extend(items)
    return apps


def get_app_details(package_name: str, country: str = "us", language: str = "en") -> Optional[dict[str, Any]]:
    """Calls SerpApi's real Google Play product engine
    (engine=google_play_product) for one app and returns the RAW provider
    response dict, or None if the provider genuinely has no product_info
    for this package (never a fabricated placeholder)."""
    params = {
        "engine": "google_play_product",
        "store": "apps",
        "product_id": package_name,
        "gl": country,
        "hl": language,
        "api_key": _require_api_key(),
    }
    data = _get(params)
    if not data.get("product_info"):
        return None
    return data
