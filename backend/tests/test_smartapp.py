"""
Tests for SmartApp's isolated backend module (backend/smartapp/).

Every outbound SerpApi call is mocked at the provider boundary
(smartapp.provider.search_play_store / get_app_details) - these tests
never make a real network request and never require a real
SERPAPI_API_KEY. This mirrors tests/test_api.py's existing
TestClient(app)-against-the-real-app style, so SmartApp's tests run
exactly the same way as the rest of this suite:

    python -m pytest tests/test_smartapp.py -v
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import app
from smartapp import enrichment, metadata, service
from smartapp.metadata import ProviderUnavailable
from smartapp.provider import SerpApiError

client = TestClient(app)


class _OfflineProvider:
    """Stands in for Exodus/F-Droid so these tests never hit the network."""

    def lookup(self, package_name):
        raise ProviderUnavailable("offline test provider")


@pytest.fixture(autouse=True)
def _isolated_providers(monkeypatch):
    # Fresh caches per test, and no real enrichment requests.
    service._details_cache.clear()
    metadata.metadata_cache.clear()
    monkeypatch.setattr(enrichment.default_enricher, "privacy", _OfflineProvider())
    monkeypatch.setattr(enrichment.default_enricher, "fdroid", _OfflineProvider())
    monkeypatch.delenv("SMARTAPP_SEARCH_DETAILS_LIMIT", raising=False)
    yield


def _raw_search_item(**overrides):
    base = {
        "title": "NoteFlow",
        "product_id": "com.example.noteflow",
        "link": "https://play.google.com/store/apps/details?id=com.example.noteflow",
        "rating": 4.6,
        "reviews": "18,400",
        "author": "Example Dev",
        "category": "Productivity",
        "thumbnail": "https://example.com/icon.png",
        "description": "A note app.",
    }
    base.update(overrides)
    return base


def _raw_details(**overrides):
    base = {
        "product_info": {
            "title": "NoteFlow",
            "rating": 4.6,
            "reviews": "18,400",
            "thumbnail": "https://example.com/icon.png",
            "authors": [{"name": "Example Dev"}],
            "link": "https://play.google.com/store/apps/details?id=com.example.noteflow",
        },
        "about_this_app": {
            "snippet": "A note app.",
            "released_on": "Jan 1, 2020",
            "updated_on": "Jan 1, 2024",
        },
        "media": {"images": ["https://example.com/s1.png"]},
        "categories": [{"name": "Productivity"}],
    }
    base.update(overrides)
    return base


class TestSearchEndpoint:
    def test_search_returns_normalized_real_apps(self):
        with patch("smartapp.provider.search_play_store", return_value=[_raw_search_item()]):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "google_play"
        assert data["isLiveData"] is True
        assert len(data["apps"]) == 1
        item = data["apps"][0]
        assert item["name"] == "NoteFlow"
        assert item["packageName"] == "com.example.noteflow"
        assert item["rating"] == 4.6
        assert item["reviewCount"] == 18400
        assert item["realData"] is True
        assert item["source"] == "google_play"

    def test_missing_rating_is_null_not_fabricated(self):
        with patch("smartapp.provider.search_play_store", return_value=[_raw_search_item(rating=None)]):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.json()["apps"][0]["rating"] is None

    def test_missing_review_count_is_null_not_zero(self):
        with patch("smartapp.provider.search_play_store", return_value=[_raw_search_item(reviews=None)]):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.json()["apps"][0]["reviewCount"] is None

    def test_non_numeric_review_string_is_null_not_guessed(self):
        # "1M+" can't be turned into an exact int without guessing what
        # the suffix means - must stay None, never rounded/estimated.
        with patch("smartapp.provider.search_play_store", return_value=[_raw_search_item(reviews="1M+")]):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.json()["apps"][0]["reviewCount"] is None

    def test_missing_play_store_url_is_null(self):
        raw = _raw_search_item()
        del raw["link"]
        with patch("smartapp.provider.search_play_store", return_value=[raw]):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.json()["apps"][0]["playStoreUrl"] is None

    def test_empty_search_returns_empty_list_not_fake_apps(self):
        with patch("smartapp.provider.search_play_store", return_value=[]):
            resp = client.get("/smartapp/apps/search", params={"q": "zzz_no_such_app_zzz"})
        assert resp.status_code == 200
        assert resp.json()["apps"] == []

    def test_category_maps_to_a_real_search_query_when_no_q_given(self):
        with patch("smartapp.provider.search_play_store", return_value=[]) as mock_search:
            resp = client.get("/smartapp/apps/search", params={"category": "Notes"})
        assert resp.status_code == 200
        mock_search.assert_called_once()
        called_query = mock_search.call_args.args[0] if mock_search.call_args.args else mock_search.call_args.kwargs.get("query")
        assert called_query == "notes"

    def test_neither_q_nor_category_is_a_client_error(self):
        resp = client.get("/smartapp/apps/search")
        assert resp.status_code == 400

    def test_provider_error_returns_502_not_fake_data(self):
        with patch("smartapp.provider.search_play_store", side_effect=SerpApiError("boom")):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.status_code == 502
        assert "apps" not in resp.json()

    def test_missing_api_key_surfaces_as_502_not_a_silent_fallback(self):
        with patch("smartapp.provider.search_play_store", side_effect=SerpApiError("SERPAPI_API_KEY is not configured")):
            resp = client.get("/smartapp/apps/search", params={"q": "note"})
        assert resp.status_code == 502

    def test_limit_is_respected(self):
        items = [_raw_search_item(product_id=f"com.example.app{i}") for i in range(10)]
        with patch("smartapp.provider.search_play_store", return_value=items):
            resp = client.get("/smartapp/apps/search", params={"q": "note", "limit": 3})
        assert len(resp.json()["apps"]) == 3


class TestDetailsEndpoint:
    def test_details_returns_normalized_real_app(self):
        with patch("smartapp.provider.get_app_details", return_value=_raw_details()):
            resp = client.get("/smartapp/apps/details/com.example.noteflow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "google_play"
        assert data["isLiveData"] is True
        app_data = data["app"]
        assert app_data["name"] == "NoteFlow"
        assert app_data["packageName"] == "com.example.noteflow"
        assert app_data["developer"] == "Example Dev"
        assert app_data["category"] == "Productivity"
        assert app_data["screenshots"] == ["https://example.com/s1.png"]
        assert app_data["realData"] is True

    def test_missing_privacy_and_security_fields_are_never_present_or_fabricated(self):
        # Google Play metadata alone is not authoritative privacy/security
        # information - nothing may be guessed, e.g. trackerCount=0.
        with patch("smartapp.provider.get_app_details", return_value=_raw_details()):
            resp = client.get("/smartapp/apps/details/com.example.noteflow")
        body = resp.json()["app"]
        # These fields now exist (verified enrichment can fill them), but with
        # no verified source they must stay null - never a guessed value.
        for unverified_field in ("trackerCount", "isOpenSource", "hasAds", "supportsOffline", "sizeMb"):
            assert body[unverified_field] is None

    def test_app_not_found_returns_404_not_fake_details(self):
        with patch("smartapp.provider.get_app_details", return_value=None):
            resp = client.get("/smartapp/apps/details/com.does.not.exist")
        assert resp.status_code == 404

    def test_provider_error_returns_502(self):
        with patch("smartapp.provider.get_app_details", side_effect=SerpApiError("boom")):
            resp = client.get("/smartapp/apps/details/com.example.noteflow")
        assert resp.status_code == 502

    def test_missing_play_store_url_is_null_never_constructed(self):
        raw = _raw_details()
        raw["product_info"] = dict(raw["product_info"])
        del raw["product_info"]["link"]
        with patch("smartapp.provider.get_app_details", return_value=raw):
            resp = client.get("/smartapp/apps/details/com.example.noteflow")
        # Specifically NOT the deterministic play.google.com/.../id=... URL
        # that could be trivially constructed from the package name alone -
        # the endpoint must only ever use what the provider actually returned.
        assert resp.json()["app"]["playStoreUrl"] is None

    def test_missing_rating_and_reviews_stay_null(self):
        raw = _raw_details()
        raw["product_info"] = dict(raw["product_info"])
        raw["product_info"]["rating"] = None
        raw["product_info"]["reviews"] = None
        with patch("smartapp.provider.get_app_details", return_value=raw):
            resp = client.get("/smartapp/apps/details/com.example.noteflow")
        body = resp.json()["app"]
        assert body["rating"] is None
        assert body["reviewCount"] is None


class TestSmartAppIsolation:
    """Regression protection (Part 20): SmartApp's presence must not
    change any existing security endpoint's behavior."""

    def test_existing_security_endpoints_are_still_registered_unchanged(self):
        route_paths = set(app.openapi()["paths"].keys())
        for existing_path in (
            "/predict",
            "/developer/predict",
            "/developer/scan",
            "/developer/explain",
            "/developer/rescan",
            "/decision",
            "/apps/search",
            "/apps/{app_id}",
            "/apps/{app_id}/security",
            "/apps/{app_id}/compatibility",
            "/apps/{app_id}/alternatives",
            "/upload-apk",
            "/login",
            "/register",
        ):
            assert existing_path in route_paths, f"existing route {existing_path} missing after SmartApp integration"

    def test_smartapp_routes_are_registered_under_their_own_prefix(self):
        route_paths = set(app.openapi()["paths"].keys())
        assert "/smartapp/apps/search" in route_paths
        assert "/smartapp/apps/details/{package_name}" in route_paths
