"""
Applies SmartApp's verified-metadata providers to already-normalized
Google Play apps.

Rules:
  * Google Play stays the primary source - enrichment only ADDS fields.
  * A provider that is unconfigured or fails is skipped for that app; the
    app is still returned (one enrichment source never breaks the
    pipeline).
  * "Not found" at a provider sets nothing - it is not evidence.
  * No field is inferred from another (tracker count never implies ads,
    open source, or offline support).
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Iterable, Optional

from .metadata import (
    ExodusPrivacyProvider,
    FDroidProvider,
    PlayStoreFacts,
    PrivacyMetadataProvider,
    ProviderUnavailable,
)
from .models import SmartAppItem

log = logging.getLogger("smartapp.enrichment")

# The 7 recommendation attributes coverage is measured over. The Flutter
# app (AppInfo.metadataCoverage) uses the same list.
COVERAGE_ATTRIBUTES = ("rating", "privacy", "resource", "price", "ads", "openSource", "offline")

_MAX_WORKERS = 8


def metadata_coverage(app: SmartAppItem) -> float:
    known = [
        app.rating is not None,
        app.trackerCount is not None,
        app.sizeMb is not None,
        app.isFree is not None,
        app.hasAds is not None,
        app.isOpenSource is not None,
        app.supportsOffline is not None,
    ]
    return round(sum(known) / len(known), 4)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def apply_store_facts(app: SmartAppItem, facts: PlayStoreFacts) -> None:
    app.isFree = facts.is_free
    app.price = facts.price
    app.currency = facts.currency
    if facts.has_ads is not None:
        app.hasAds = facts.has_ads
    app.inAppPurchases = facts.in_app_purchases
    if facts.permissions is not None:
        app.permissions = facts.permissions
    app.dataSafety = list(facts.data_safety)
    app.storeDetailsAvailable = True
    if "google_play_details" not in app.metadataSources:
        app.metadataSources.append("google_play_details")


class Enricher:
    def __init__(self, privacy: Optional[PrivacyMetadataProvider] = None, fdroid: Optional[FDroidProvider] = None):
        self.privacy = privacy if privacy is not None else ExodusPrivacyProvider()
        self.fdroid = fdroid if fdroid is not None else FDroidProvider()

    def _enrich_one(self, app: SmartAppItem) -> SmartAppItem:
        package = app.packageName
        if package:
            self._apply_privacy(app, package)
            self._apply_fdroid(app, package)
        app.resourceMetadataAvailable = app.sizeMb is not None
        app.metadataUpdatedAt = _now()
        app.metadataCoverage = metadata_coverage(app)
        return app

    def _apply_privacy(self, app: SmartAppItem, package: str) -> None:
        try:
            privacy = self.privacy.lookup(package)
        except ProviderUnavailable as exc:
            log.debug("privacy provider unavailable for %s: %s", package, exc)
            return
        except Exception:  # a buggy provider must not break Google Play results
            log.exception("privacy provider crashed for %s", package)
            return
        if privacy is None:
            return
        app.trackerCount = privacy.tracker_count
        app.trackerNames = list(privacy.tracker_names)
        if privacy.permissions is not None:
            app.permissions = list(privacy.permissions)
        app.privacyReportVersion = privacy.report_version
        app.privacyMetadataUpdatedAt = privacy.report_updated_at
        app.privacyDataSource = privacy.source
        app.privacyMetadataAvailable = True
        if privacy.source not in app.metadataSources:
            app.metadataSources.append(privacy.source)

    def _apply_fdroid(self, app: SmartAppItem, package: str) -> None:
        try:
            meta = self.fdroid.lookup(package)
        except ProviderUnavailable as exc:
            log.debug("F-Droid unavailable for %s: %s", package, exc)
            return
        except Exception:
            log.exception("F-Droid provider crashed for %s", package)
            return
        if meta is None:
            return  # not on F-Droid: NOT evidence of closed source
        app.isOpenSource = meta.is_open_source
        app.license = meta.license
        app.antiFeatures = list(meta.anti_features)
        app.fdroidAvailable = True
        app.fdroidSourceUrl = meta.source_url
        if meta.declares_ads:
            app.hasAds = True  # explicit F-Droid "Ads" anti-feature
        app.openSourceMetadataAvailable = True
        if "fdroid" not in app.metadataSources:
            app.metadataSources.append("fdroid")

    def enrich(self, apps: Iterable[SmartAppItem]) -> list[SmartAppItem]:
        apps = list(apps)
        if not apps:
            return apps
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(apps))) as pool:
            return list(pool.map(self._enrich_one, apps))


default_enricher = Enricher()
