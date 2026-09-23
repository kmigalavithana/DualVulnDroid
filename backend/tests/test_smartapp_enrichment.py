"""
Tests for SmartApp's verified-metadata layer (smartapp/metadata.py,
smartapp/enrichment.py, smartapp/cache.py). Every provider HTTP call is
served by a fake client - no real network, no real credentials.

    python -m pytest tests/test_smartapp_enrichment.py -v
"""

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from smartapp import enrichment, metadata, service
from smartapp.cache import MISSING, TTLCache
from smartapp.enrichment import Enricher, metadata_coverage
from smartapp.metadata import (
    ExodusPrivacyProvider,
    FDroidProvider,
    ProviderUnavailable,
    play_store_facts,
)
from smartapp.models import SmartAppItem
from smartapp.service import normalize_search_result

client = TestClient(app)
PKG = "com.example.noteflow"
PLAY_URL = f"https://play.google.com/store/apps/details?id={PKG}"
TOKEN = "test-token-never-leak-123"


class FakeHttp:
    """Serves canned responses by URL; records every request."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers=None, timeout=None, follow_redirects=None):
        self.calls.append((url, headers or {}))
        for prefix, (status, body) in self.routes.items():
            if url.startswith(prefix):
                request = httpx.Request("GET", url)
                if isinstance(body, str):
                    return httpx.Response(status, text=body, request=request)
                return httpx.Response(status, json=body, request=request)
        raise AssertionError(f"unexpected URL {url}")


class Offline:
    def lookup(self, package_name):
        raise ProviderUnavailable("offline")


class Crashing:
    def lookup(self, package_name):
        raise RuntimeError("provider bug")


def _item(**overrides):
    raw = {
        "title": "NoteFlow",
        "product_id": PKG,
        "link": PLAY_URL,
        "rating": 4.6,
        "author": "Example Dev",
        "category": "Productivity",
        "thumbnail": "https://example.com/icon.png",
    }
    raw.update(overrides)
    return normalize_search_result(raw)


def _exodus(routes):
    http = FakeHttp(routes)
    return ExodusPrivacyProvider(base_url="https://exodus.test", token=TOKEN, client=http), http


EXODUS_REPORT = {
    PKG: {
        "name": "NoteFlow",
        "reports": [
            {"id": 1, "updated_at": "2023-01-01T00:00:00Z", "version_name": "1.0", "trackers": [1, 2, 3]},
            {"id": 2, "updated_at": "2024-05-01T00:00:00Z", "version_name": "2.0", "trackers": [7, 9]},
        ],
    }
}
EXODUS_TRACKERS = {"trackers": {"7": {"id": 7, "name": "Google Firebase Analytics"}, "9": {"id": 9, "name": "AppsFlyer"}}}


@pytest.fixture(autouse=True)
def _clean():
    metadata.metadata_cache.clear()
    service._details_cache.clear()
    yield
    metadata.metadata_cache.clear()
    service._details_cache.clear()


# 1 / 19 --------------------------------------------------------------------

def test_google_play_metadata_and_real_url_stay_intact_after_enrichment():
    app = Enricher(privacy=Offline(), fdroid=Offline()).enrich([_item()])[0]
    assert (app.name, app.packageName, app.rating, app.developer) == ("NoteFlow", PKG, 4.6, "Example Dev")
    assert app.playStoreUrl == PLAY_URL
    assert app.realData is True and app.source == "google_play"
    assert app.metadataSources == ["google_play"]


# 2 / 3 / 4 -----------------------------------------------------------------

def test_exodus_enrichment_uses_the_latest_report():
    provider, http = _exodus({
        f"https://exodus.test/api/search/{PKG}/": (200, EXODUS_REPORT),
        "https://exodus.test/api/trackers": (200, EXODUS_TRACKERS),
    })
    app = Enricher(privacy=provider, fdroid=Offline()).enrich([_item()])[0]
    assert app.trackerCount == 2
    assert app.trackerNames == ["Google Firebase Analytics", "AppsFlyer"]
    assert app.privacyReportVersion == "2.0"
    assert app.privacyMetadataUpdatedAt == "2024-05-01T00:00:00Z"
    assert app.privacyDataSource == "exodus" and app.privacyMetadataAvailable is True
    assert app.metadataSources == ["google_play", "exodus"]
    assert http.calls[0][1]["Authorization"] == f"Token {TOKEN}"
    # Tracker count never implies these:
    assert app.hasAds is None and app.isOpenSource is None and app.supportsOffline is None


def test_exodus_package_not_found_sets_nothing():
    provider, _ = _exodus({f"https://exodus.test/api/search/{PKG}/": (200, {})})
    app = Enricher(privacy=provider, fdroid=Offline()).enrich([_item()])[0]
    assert app.trackerCount is None and app.privacyMetadataAvailable is False
    assert "exodus" not in app.metadataSources


def test_exodus_unconfigured_is_unavailable_not_a_failure():
    provider = ExodusPrivacyProvider(base_url="", token="")
    assert provider.configured is False
    with pytest.raises(ProviderUnavailable):
        provider.lookup(PKG)
    app = Enricher(privacy=provider, fdroid=Offline()).enrich([_item()])[0]
    assert app.trackerCount is None and app.name == "NoteFlow"


def test_exodus_http_error_is_unavailable_and_never_leaks_the_token():
    provider, _ = _exodus({f"https://exodus.test/api/search/{PKG}/": (500, {"detail": f"bad {TOKEN}"})})
    with pytest.raises(ProviderUnavailable) as exc:
        provider.lookup(PKG)
    assert TOKEN not in str(exc.value)


# 5 / 6 / 9 -----------------------------------------------------------------

FDROID_YML = """License: GPL-3.0-only
SourceCode: https://github.com/example/noteflow
AntiFeatures:
  - Ads
  - NonFreeNet
"""


def _fdroid(routes):
    http = FakeHttp(routes)
    return FDroidProvider(api_base="https://fdroid.test/api/v1", metadata_base="https://meta.test", enabled=True, client=http), http


def test_fdroid_match_verifies_open_source_license_and_anti_features():
    provider, _ = _fdroid({
        f"https://fdroid.test/api/v1/packages/{PKG}": (200, {"packageName": PKG}),
        f"https://meta.test/{PKG}.yml": (200, FDROID_YML),
    })
    app = Enricher(privacy=Offline(), fdroid=provider).enrich([_item()])[0]
    assert app.isOpenSource is True and app.fdroidAvailable is True
    assert app.license == "GPL-3.0-only"
    assert app.fdroidSourceUrl == "https://github.com/example/noteflow"
    assert app.antiFeatures == ["Ads", "NonFreeNet"]
    assert app.hasAds is True, "an explicit F-Droid Ads anti-feature is verified evidence"
    assert app.metadataSources == ["google_play", "fdroid"]


def test_fdroid_no_match_is_not_evidence_of_closed_source():
    provider, _ = _fdroid({f"https://fdroid.test/api/v1/packages/{PKG}": (404, {"detail": "not found"})})
    app = Enricher(privacy=Offline(), fdroid=provider).enrich([_item()])[0]
    assert app.isOpenSource is None, "absence from F-Droid must not become isOpenSource=False"
    assert app.fdroidAvailable is None and app.openSourceMetadataAvailable is False


def test_fdroid_match_without_readable_metadata_still_verifies_open_source_only():
    provider, _ = _fdroid({
        f"https://fdroid.test/api/v1/packages/{PKG}": (200, {"packageName": PKG}),
        f"https://meta.test/{PKG}.yml": (404, "missing"),
    })
    app = Enricher(privacy=Offline(), fdroid=provider).enrich([_item()])[0]
    assert app.isOpenSource is True and app.license is None and app.hasAds is None


# 7 / 8 / 10 ----------------------------------------------------------------

def test_unverified_attributes_stay_null_with_no_fake_fallback():
    app = Enricher(privacy=Offline(), fdroid=Offline()).enrich([_item()])[0]
    for attr in ("trackerCount", "sizeMb", "isOpenSource", "hasAds", "supportsOffline", "isFree"):
        assert getattr(app, attr) is None, attr
    assert app.resourceMetadataAvailable is False and app.privacyMetadataAvailable is False


# Store facts (Play product page) -------------------------------------------

def test_store_facts_free_paid_and_labels():
    free = play_store_facts({"product_info": {"offers": [{"text": "Install"}], "extensions": ["In-app purchases"]}})
    assert free.is_free is True and free.in_app_purchases is True
    assert free.has_ads is None, "no 'Contains ads' label must stay unknown, not False"

    paid = play_store_facts({"product_info": {"offers": [{"text": "$6.99 Buy", "price": "$6.99", "extracted_price": 6.99}]}})
    assert paid.is_free is False and paid.price == "$6.99" and paid.currency is None

    ads = play_store_facts({"product_info": {"extensions": ["Contains ads"]}, "data_safety": [{"text": "Data is encrypted in transit"}]})
    assert ads.has_ads is True and ads.data_safety == ["Data is encrypted in transit"]

    unknown = play_store_facts({"product_info": {"offers": [{"text": "Pre-register"}]}})
    assert unknown.is_free is None


# 11 ------------------------------------------------------------------------

def test_metadata_coverage_counts_only_verified_attributes():
    app = SmartAppItem(rating=4.2)
    assert metadata_coverage(app) == round(1 / 7, 4)
    app.trackerCount = 0
    app.isFree = True
    app.isOpenSource = True
    assert metadata_coverage(app) == round(4 / 7, 4)
    app.hasAds = True  # a verified "yes" counts as known too
    assert metadata_coverage(app) == round(5 / 7, 4)


# 17 ------------------------------------------------------------------------

def test_provider_results_are_cached_per_package_and_provider():
    provider, http = _exodus({
        f"https://exodus.test/api/search/{PKG}/": (200, EXODUS_REPORT),
        "https://exodus.test/api/trackers": (200, EXODUS_TRACKERS),
    })
    provider.lookup(PKG)
    provider.lookup(PKG)
    assert [u for u, _ in http.calls].count(f"https://exodus.test/api/search/{PKG}/") == 1
    assert metadata.metadata_cache.get(("exodus", PKG)) is not MISSING


def test_not_found_is_cached_but_failures_are_not():
    provider, http = _fdroid({f"https://fdroid.test/api/v1/packages/{PKG}": (404, {})})
    provider.lookup(PKG)
    provider.lookup(PKG)
    assert len(http.calls) == 1

    failing, fhttp = _fdroid({f"https://fdroid.test/api/v1/packages/{PKG}": (503, {})})
    metadata.metadata_cache.clear()
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            failing.lookup(PKG)
    assert len(fhttp.calls) == 2


def test_cache_is_bounded_and_expires():
    now = [0.0]
    cache = TTLCache(ttl_seconds=10, max_entries=2, clock=lambda: now[0])
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert len(cache) == 2 and cache.get("a") is MISSING
    now[0] = 11
    assert cache.get("b") is MISSING


# 18 ------------------------------------------------------------------------

def test_provider_failures_never_break_google_play_search_results(monkeypatch):
    monkeypatch.setattr(enrichment.default_enricher, "privacy", Crashing())
    monkeypatch.setattr(enrichment.default_enricher, "fdroid", Offline())
    raw = {"title": "NoteFlow", "product_id": PKG, "link": PLAY_URL, "rating": 4.6}
    with patch("smartapp.provider.search_play_store", return_value=[raw]):
        resp = client.get("/smartapp/apps/search", params={"q": "notes"})
    assert resp.status_code == 200
    app = resp.json()["apps"][0]
    assert app["name"] == "NoteFlow" and app["playStoreUrl"] == PLAY_URL
    assert app["trackerCount"] is None
    assert TOKEN not in resp.text


def test_google_play_failure_is_not_replaced_by_enrichment(monkeypatch):
    monkeypatch.setattr(enrichment.default_enricher, "privacy", Offline())
    monkeypatch.setattr(enrichment.default_enricher, "fdroid", Offline())
    with patch("smartapp.provider.search_play_store", side_effect=service.provider.SerpApiError("down")):
        resp = client.get("/smartapp/apps/search", params={"q": "notes"})
    assert resp.status_code == 502


# Search-time store facts are opt-in (credit cost) --------------------------

def test_search_store_facts_only_when_enabled(monkeypatch):
    monkeypatch.setattr(enrichment.default_enricher, "privacy", Offline())
    monkeypatch.setattr(enrichment.default_enricher, "fdroid", Offline())
    raw = {"title": "NoteFlow", "product_id": PKG, "link": PLAY_URL, "rating": 4.6}
    details = {"product_info": {"title": "NoteFlow", "offers": [{"text": "Install"}], "extensions": ["Contains ads"]}}

    with patch("smartapp.provider.search_play_store", return_value=[raw]), \
         patch("smartapp.provider.get_app_details", return_value=details) as get_details:
        off = client.get("/smartapp/apps/search", params={"q": "notes"}).json()["apps"][0]
        assert get_details.call_count == 0 and off["isFree"] is None

        monkeypatch.setenv("SMARTAPP_SEARCH_DETAILS_LIMIT", "5")
        on = client.get("/smartapp/apps/search", params={"q": "notes"}).json()["apps"][0]
        assert on["isFree"] is True and on["hasAds"] is True
        assert "google_play_details" in on["metadataSources"]
        client.get("/smartapp/apps/search", params={"q": "notes"})
        assert get_details.call_count == 1, "product pages are cached"


def test_details_endpoint_adds_store_facts_and_coverage(monkeypatch):
    monkeypatch.setattr(enrichment.default_enricher, "privacy", Offline())
    monkeypatch.setattr(enrichment.default_enricher, "fdroid", Offline())
    details = {
        "product_info": {"title": "NoteFlow", "rating": 4.6, "link": PLAY_URL, "offers": [{"text": "Install"}]},
        "about_this_app": {"snippet": "A note app."},
    }
    with patch("smartapp.provider.get_app_details", return_value=details):
        body = client.get(f"/smartapp/apps/details/{PKG}").json()["app"]
    assert body["isFree"] is True and body["playStoreUrl"] == PLAY_URL
    assert body["metadataCoverage"] == round(2 / 7, 4)
