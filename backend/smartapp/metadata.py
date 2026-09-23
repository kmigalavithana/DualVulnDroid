"""
SmartApp's VERIFIED-metadata providers - a layer separate from the Google
Play provider (provider.py) and from the recommendation engine (which
lives in the Flutter app and never calls any provider itself).

Every provider returns one of three things for a package:
  * a metadata object   - the provider verified something about this app
  * None                - the provider was asked and has no record of it
                          (NOT evidence of anything - e.g. "not on F-Droid"
                          never means "closed source")
  * ProviderUnavailable - the provider isn't configured or failed; the
                          caller keeps going without it

Credentials (EXODUS_API_TOKEN) are read from the environment only, sent
only to the configured provider, and never logged or returned.

Nothing here imports, or is imported by, the DualVulnDroid security
backend (predictor.py, dataflow.py, security_features.py, decision_engine.py).
"""

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
import yaml

from .cache import TTLCache

_TIMEOUT_SECONDS = 6.0

# Provider answers change slowly (new Exodus reports, F-Droid releases),
# so a day is a reasonable freshness window.
_CACHE_TTL_SECONDS = 24 * 60 * 60
metadata_cache = TTLCache(ttl_seconds=_CACHE_TTL_SECONDS, max_entries=4096)


class ProviderUnavailable(Exception):
    """A provider is not configured or its request failed. Never cached,
    never converted into a fake value."""


# ---------------------------------------------------------------------------
# Privacy (trackers) - Exodus
# ---------------------------------------------------------------------------


@dataclass
class PrivacyMetadata:
    tracker_count: int
    tracker_names: list[str] = field(default_factory=list)
    permissions: Optional[list[str]] = None
    report_version: Optional[str] = None
    report_updated_at: Optional[str] = None
    source: str = "exodus"


class PrivacyMetadataProvider:
    name = "privacy"

    def lookup(self, package_name: str) -> Optional[PrivacyMetadata]:  # pragma: no cover - interface
        raise NotImplementedError


class ExodusPrivacyProvider(PrivacyMetadataProvider):
    """Reads tracker reports from an Exodus instance.

    Configuration (environment only):
      EXODUS_BASE_URL   e.g. https://reports.exodus-privacy.eu.org (or your own instance)
      EXODUS_API_TOKEN  API token for that instance

    Exodus asks production end-user products to run their own instance
    rather than lean on the public API - point EXODUS_BASE_URL at it.
    Without both variables this provider reports ProviderUnavailable and
    SmartApp simply shows privacy data as "Not verified".
    """

    name = "exodus"

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, client: Optional[httpx.Client] = None):
        self._base_url = (base_url if base_url is not None else os.getenv("EXODUS_BASE_URL", "")).rstrip("/")
        self._token = token if token is not None else os.getenv("EXODUS_API_TOKEN", "")
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._token)

    def _get(self, path: str) -> Any:
        if not self.configured:
            raise ProviderUnavailable("Exodus is not configured (EXODUS_BASE_URL / EXODUS_API_TOKEN).")
        headers = {"Authorization": f"Token {self._token}", "Accept": "application/json"}
        try:
            client = self._client or httpx
            response = client.get(f"{self._base_url}{path}", headers=headers, timeout=_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Exodus request failed: {type(exc).__name__}") from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            # Deliberately no response body / headers in the message - they
            # could echo request details.
            raise ProviderUnavailable(f"Exodus returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUnavailable("Exodus returned invalid JSON") from exc

    def _tracker_names(self) -> dict[str, str]:
        def load() -> dict[str, str]:
            data = self._get("/api/trackers") or {}
            trackers = data.get("trackers", data) if isinstance(data, dict) else {}
            names: dict[str, str] = {}
            if isinstance(trackers, dict):
                for tracker_id, info in trackers.items():
                    if isinstance(info, dict) and info.get("name"):
                        names[str(info.get("id", tracker_id))] = str(info["name"])
            return names

        return metadata_cache.get_or_load(("exodus", "__trackers__"), load)

    def lookup(self, package_name: str) -> Optional[PrivacyMetadata]:
        def load() -> Optional[PrivacyMetadata]:
            data = self._get(f"/api/search/{package_name}/")
            entry = data.get(package_name) if isinstance(data, dict) else None
            reports = entry.get("reports") if isinstance(entry, dict) else None
            if not reports:
                return None  # Exodus has no report for this package
            latest = max(reports, key=lambda r: (str(r.get("updated_at") or ""), r.get("id") or 0))
            tracker_ids = [str(t) for t in (latest.get("trackers") or [])]
            names_by_id = self._tracker_names() if tracker_ids else {}
            permissions = latest.get("permissions")
            return PrivacyMetadata(
                tracker_count=len(tracker_ids),
                tracker_names=[names_by_id[t] for t in tracker_ids if t in names_by_id],
                permissions=[str(p) for p in permissions] if isinstance(permissions, list) else None,
                report_version=_str_or_none(latest.get("version_name")),
                report_updated_at=_str_or_none(latest.get("updated_at")),
            )

        return metadata_cache.get_or_load(("exodus", package_name), load)


# ---------------------------------------------------------------------------
# Open source / anti-features - F-Droid
# ---------------------------------------------------------------------------


@dataclass
class OpenSourceMetadata:
    license: Optional[str]
    anti_features: list[str]
    source_url: Optional[str]
    source: str = "fdroid"

    @property
    def is_open_source(self) -> bool:
        # F-Droid's main repository only accepts free/open-source apps, so a
        # match there IS open-source evidence.
        return True

    @property
    def declares_ads(self) -> bool:
        return "Ads" in self.anti_features


class FDroidProvider:
    """Looks a package up in F-Droid's main repository.

    FDROID_API_BASE       default https://f-droid.org/api/v1
    FDROID_METADATA_BASE  default https://gitlab.com/fdroid/fdroiddata/-/raw/master/metadata
    SMARTAPP_FDROID_ENABLED  set to 0 to switch the provider off

    A package that isn't on F-Droid returns None - which is NOT evidence
    that the app is closed source.
    """

    name = "fdroid"

    def __init__(self, api_base: Optional[str] = None, metadata_base: Optional[str] = None,
                 enabled: Optional[bool] = None, client: Optional[httpx.Client] = None):
        self._api_base = (api_base or os.getenv("FDROID_API_BASE", "https://f-droid.org/api/v1")).rstrip("/")
        self._metadata_base = (metadata_base or os.getenv(
            "FDROID_METADATA_BASE", "https://gitlab.com/fdroid/fdroiddata/-/raw/master/metadata")).rstrip("/")
        self._enabled = enabled if enabled is not None else os.getenv("SMARTAPP_FDROID_ENABLED", "1") != "0"
        self._client = client

    @property
    def configured(self) -> bool:
        return self._enabled

    def _get(self, url: str) -> httpx.Response:
        try:
            client = self._client or httpx
            return client.get(url, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"F-Droid request failed: {type(exc).__name__}") from exc

    def lookup(self, package_name: str) -> Optional[OpenSourceMetadata]:
        if not self._enabled:
            raise ProviderUnavailable("F-Droid lookups are disabled (SMARTAPP_FDROID_ENABLED=0).")

        def load() -> Optional[OpenSourceMetadata]:
            listing = self._get(f"{self._api_base}/packages/{package_name}")
            if listing.status_code == 404:
                return None  # not in F-Droid's repository - no evidence either way
            if listing.status_code != 200:
                raise ProviderUnavailable(f"F-Droid returned HTTP {listing.status_code}")

            license_id: Optional[str] = None
            anti_features: list[str] = []
            source_url: Optional[str] = None
            # The package exists; its fdroiddata metadata adds license /
            # source / anti-features. If that file can't be read we still
            # know it's on F-Droid (open source), just without the extras.
            try:
                meta_response = self._get(f"{self._metadata_base}/{package_name}.yml")
                if meta_response.status_code == 200:
                    meta = yaml.safe_load(meta_response.text) or {}
                    if isinstance(meta, dict):
                        license_id = _str_or_none(meta.get("License"))
                        source_url = _str_or_none(meta.get("SourceCode"))
                        anti_features = _anti_features(meta.get("AntiFeatures"))
            except (ProviderUnavailable, yaml.YAMLError):
                pass
            return OpenSourceMetadata(license=license_id, anti_features=anti_features, source_url=source_url)

        return metadata_cache.get_or_load(("fdroid", package_name), load)


def _anti_features(value: Any) -> list[str]:
    # fdroiddata uses either a list ("- Ads") or a mapping ("Ads: {en-US: reason}").
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, dict):
        return [str(k) for k in value.keys()]
    return []


# ---------------------------------------------------------------------------
# Store facts from the Google Play product page (already fetched by
# provider.get_app_details - no extra request here)
# ---------------------------------------------------------------------------


@dataclass
class PlayStoreFacts:
    is_free: Optional[bool] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    has_ads: Optional[bool] = None
    in_app_purchases: Optional[bool] = None
    permissions: Optional[list[str]] = None
    data_safety: list[str] = field(default_factory=list)


def play_store_facts(raw_details: dict[str, Any]) -> PlayStoreFacts:
    """Extracts only what the Play product page states explicitly.

    - Price: an offer with a numeric `extracted_price` -> paid (or free if
      it is 0); a plain "Install" offer with no price -> free. Anything
      else -> unknown. Currency is only set if the provider names it.
    - Ads / in-app purchases: Play shows "Contains ads" / "In-app
      purchases" labels. A label present -> True. A label absent is NOT
      read as False (that would turn missing data into a positive claim),
      so it stays None.
    - Size / offline support: the provider doesn't report them - never set.
    """
    product_info = raw_details.get("product_info") or {}
    about = raw_details.get("about_this_app") or {}
    facts = PlayStoreFacts()

    for offer in product_info.get("offers") or []:
        if not isinstance(offer, dict):
            continue
        extracted = offer.get("extracted_price")
        if isinstance(extracted, (int, float)) and not isinstance(extracted, bool):
            facts.is_free = extracted == 0
            facts.price = _str_or_none(offer.get("price"))
            facts.currency = _str_or_none(offer.get("currency"))
            break
        text = str(offer.get("text") or "").strip().lower()
        if text == "install" and offer.get("price") is None:
            facts.is_free = True
            break

    labels = {str(e).strip().lower() for e in (product_info.get("extensions") or [])}
    if "contains ads" in labels:
        facts.has_ads = True
    if "in-app purchases" in labels:
        facts.in_app_purchases = True

    permissions = about.get("permissions")
    if isinstance(permissions, list):
        names = []
        for p in permissions:
            name = p.get("name") if isinstance(p, dict) else p
            if name:
                names.append(str(name))
        facts.permissions = names

    for item in raw_details.get("data_safety") or []:
        if isinstance(item, dict) and item.get("text"):
            sub = _str_or_none(item.get("subtext"))
            facts.data_safety.append(f"{item['text']}: {sub}" if sub else str(item["text"]))

    return facts


def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
