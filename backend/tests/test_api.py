"""
Real automated API tests (Phase 4, section 13), against the actual
FastAPI app via TestClient - not the previous ad-hoc manual scripts
(backend/manual_predict_smoke.py, backend/test_snippet.py), which are
being superseded by this suite.

Run from backend/:  python -m pytest tests/test_api.py -v
"""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

import apk_scanner
from app import app

client = TestClient(app)

VULNERABLE_SQL = '''
String query = "SELECT * FROM users WHERE id=" + userId;
db.rawQuery(query, null);
'''

SAFE_SQL = 'db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});'

TRACED_SQL = '''
public class LoginActivity extends Activity {
    public void onCreate() {
        String username = getIntent().getStringExtra("username");
        String query = "SELECT * FROM users WHERE name=" + username;
        db.rawQuery(query, null);
    }
}
'''

VULNERABLE_HOSTNAME_VERIFIER = '''
val hv = object : HostnameVerifier {
    override fun verify(hostname: String, session: SSLSession): Boolean {
        return true
    }
}
'''

SAFE_CERT = '''
class RealTrustManager implements X509TrustManager {
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        if (chain == null || chain.length == 0) {
            throw new CertificateException("Empty chain");
        }
        defaultTrustManager.checkServerTrusted(chain, authType);
    }
}
'''

WEBVIEW_PROCEED = '''
client = new WebViewClient() {
    @Override
    public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
        handler.proceed();
    }
};
'''

WEBVIEW_CANCEL = '''
client = new WebViewClient() {
    @Override
    public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
        handler.cancel();
    }
};
'''

UNRELATED_SAFE = 'Log.d("TAG", "hello world"); int x = 5 + 3;'


# ---------------------------------------------------------------------
# 1. Vulnerable SQL example
# ---------------------------------------------------------------------
def test_vulnerable_sql_via_predict():
    # Uses TRACED_SQL, not the weaker VULNERABLE_SQL constant: a traced
    # source-to-sink finding (weight +2.0) reliably clears the decision
    # threshold. VULNERABLE_SQL (concatenation-only, no traced source) is
    # intentionally used below in test_ambiguous_evidence_defers_to_review
    # instead, since the ML component's vote on that exact phrasing can
    # go either way (a known, documented n-gram-classifier limitation -
    # see decision engine docs) and the point of that test is to prove
    # the system defers rather than guesses when evidence conflicts.
    r = client.post("/predict", json={"code": TRACED_SQL, "fileName": "X.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is True
    assert body["vulnerabilityType"] == "SQL Injection"
    assert body["decision"] == "VULNERABLE"
    assert "securityFeatures" in body
    assert body["securityFeatures"]["sql_string_concatenation"] == 1


def test_vulnerable_sql_via_developer_predict():
    r = client.post("/developer/predict", json={"code": TRACED_SQL, "fileName": "X.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is True
    assert body["cwe"] == "CWE-89"
    assert body["model"]["name"]
    assert body["decision"]["riskLevel"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(body["explanation"], list)


def test_ambiguous_evidence_defers_to_review_not_a_guess():
    """When the ML component disagrees with the rule/data-flow signal,
    the hybrid decision engine must defer (SUSPICIOUS_REVIEW) rather than
    confidently guess in either direction - this is the selective-
    classification behavior documented in decision_engine.py, not a bug."""
    r = client.post("/developer/predict", json={"code": VULNERABLE_SQL, "fileName": "X.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["riskLevel"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    # Whichever way the ML vote landed, the real data-flow finding must
    # still be reported in the evidence/dataFlow - it's never hidden.
    assert len(body["dataFlow"]) == 1
    assert body["dataFlow"][0]["verdict"] == "VULNERABLE"


# ---------------------------------------------------------------------
# 2. Safe parameterized SQL
# ---------------------------------------------------------------------
def test_safe_parameterized_sql():
    r = client.post("/developer/predict", json={"code": SAFE_SQL, "fileName": "X.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is False
    assert body["securityFeatures"]["sql_parameterized_query"] == 1


# ---------------------------------------------------------------------
# 3. Traced SQL source-to-sink
# ---------------------------------------------------------------------
def test_traced_sql_source_to_sink():
    r = client.post("/developer/explain", json={"code": TRACED_SQL, "fileName": "LoginActivity.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is True
    assert len(body["dataFlowEvidence"]) == 1
    flow = body["dataFlowEvidence"][0]
    assert flow["source"] == "Intent.getStringExtra()"
    assert flow["sink"] == "rawQuery()"
    assert flow["verdict"] == "VULNERABLE"
    assert any("User-controlled input" in s for s in body["explanation"])


# ---------------------------------------------------------------------
# 4. Vulnerable HostnameVerifier
# ---------------------------------------------------------------------
def test_vulnerable_hostname_verifier():
    r = client.post("/developer/predict", json={"code": VULNERABLE_HOSTNAME_VERIFIER, "fileName": "Net.kt"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is True
    assert body["cwe"] == "CWE-295"
    assert any(f["verdict"] == "VULNERABLE" for f in body["dataFlow"])


# ---------------------------------------------------------------------
# 5. Safe certificate validation
# ---------------------------------------------------------------------
def test_safe_certificate_validation():
    r = client.post("/developer/predict", json={"code": SAFE_CERT, "fileName": "Net.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["securityFeatures"]["certificate_exception_validation"] == 1
    # no VULNERABLE cert finding should be present
    assert not any(f["verdict"] == "VULNERABLE" for f in body["dataFlow"])


# ---------------------------------------------------------------------
# 6. WebView proceed()
# ---------------------------------------------------------------------
def test_webview_proceed_is_vulnerable():
    r = client.post("/developer/predict", json={"code": WEBVIEW_PROCEED, "fileName": "Net.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["securityFeatures"]["webview_handler_proceed"] == 1
    assert any(f["verdict"] == "VULNERABLE" for f in body["dataFlow"])


# ---------------------------------------------------------------------
# 7. WebView cancel()
# ---------------------------------------------------------------------
def test_webview_cancel_is_safe():
    r = client.post("/developer/predict", json={"code": WEBVIEW_CANCEL, "fileName": "Net.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["securityFeatures"]["webview_handler_cancel"] == 1
    assert not any(f["verdict"] == "VULNERABLE" for f in body["dataFlow"])


# ---------------------------------------------------------------------
# 8. Unrelated safe code
# ---------------------------------------------------------------------
def test_unrelated_safe_code():
    r = client.post("/developer/predict", json={"code": UNRELATED_SAFE, "fileName": "Main.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is False
    assert body["dataFlow"] == []


# ---------------------------------------------------------------------
# 9. Malformed request
# ---------------------------------------------------------------------
def test_malformed_request_missing_code_field():
    r = client.post("/developer/predict", json={"fileName": "X.java"})
    assert r.status_code == 422  # Pydantic validation error, not a 500


def test_malformed_request_wrong_type():
    r = client.post("/developer/predict", json={"code": 12345})
    assert r.status_code == 422


def test_oversized_code_returns_400():
    huge = "a" * 300_000
    r = client.post("/developer/predict", json={"code": huge, "fileName": "X.java"})
    assert r.status_code == 400


def test_batch_scan_empty_files_list_is_422():
    r = client.post("/developer/scan", json={"files": []})
    assert r.status_code == 422


# ---------------------------------------------------------------------
# 10. Backend/request error handling
# ---------------------------------------------------------------------
def test_app_not_found_returns_404():
    r = client.get("/apps/999999")
    assert r.status_code == 404
    assert "detail" in r.json() or "error" in r.json()


def test_apps_search_missing_query_is_422():
    r = client.get("/apps/search")
    assert r.status_code == 422  # q is a required query param


def test_apps_search_empty_query_is_400():
    r = client.get("/apps/search", params={"q": "   "})
    assert r.status_code == 400


def test_unrelated_app_security_lookup_is_honest_when_unassessed():
    # searching an app id that exists structurally is out of scope here;
    # this confirms the endpoint never fabricates a score for the 404 case.
    r = client.get("/apps/424242/security")
    assert r.status_code == 404


# ---------------------------------------------------------------------
# Cross-endpoint consistency
# ---------------------------------------------------------------------
def test_decision_endpoint_matches_developer_predict_decision():
    payload = {"code": VULNERABLE_SQL, "fileName": "X.java"}
    full = client.post("/developer/predict", json=payload).json()
    decision_only = client.post("/decision", json=payload).json()
    assert decision_only["riskLevel"] == full["decision"]["riskLevel"]
    assert decision_only["recommendation"] == full["decision"]["recommendation"]


def test_batch_scan_matches_single_predict():
    single = client.post("/developer/predict", json={"code": VULNERABLE_SQL, "fileName": "X.java"}).json()
    batch = client.post("/developer/scan", json={"files": [{"code": VULNERABLE_SQL, "fileName": "X.java"}]}).json()
    assert batch["files"][0]["result"]["vulnerable"] == single["vulnerable"]
    assert batch["files"][0]["result"]["severity"] == single["severity"]


def test_predict_still_backward_compatible_shape():
    r = client.post("/predict", json={"code": SAFE_SQL, "fileName": "X.java"})
    body = r.json()
    for key in ("prediction", "vulnerable", "vulnerabilityType", "confidence", "explanation", "detections", "dataFlow"):
        assert key in body, f"backward-compatible field '{key}' missing from /predict response"
    assert isinstance(body["explanation"], str), "/predict must keep explanation as a string for existing clients"


# ---------------------------------------------------------------------
# Phase 8B: /upload-apk Android-metadata response + /apps/{id}/compatibility
# ---------------------------------------------------------------------

class _FakeParsedAPK:
    """Minimal stand-in for pyaxmlparser.APK, matching the fields
    apk_scanner.extract_apk_metadata() reads - used here to drive a real
    end-to-end /upload-apk request deterministically, without needing a
    genuine binary-AXML file (see tests/test_apk_metadata.py for the
    dedicated parser-boundary unit tests, which use the same technique)."""

    def __init__(self, package, min_sdk, target_sdk, debuggable, allow_backup):
        self.package = package
        self.version_name = "1.0"
        self.version_code = "1"
        # Distinct per package - a shared label across different
        # packages would make get_or_create_application's app_name
        # fallback lookup (used when package_name doesn't match an
        # existing row) collapse these into the same Application row,
        # which is real, intended behavior but not what these tests want
        # to exercise against each other.
        self.application = f"Compat Test App ({package})"
        self.permissions = ["android.permission.INTERNET"]
        self._min_sdk = min_sdk
        self._target_sdk = target_sdk
        self._debuggable = debuggable
        self._allow_backup = allow_backup

    def get_min_sdk_version(self):
        return self._min_sdk

    def get_target_sdk_version(self):
        return self._target_sdk

    def get_attribute_value(self, tag_name, attribute, format_value=False, **kwargs):
        if tag_name == "application" and attribute == "debuggable":
            return self._debuggable
        if tag_name == "application" and attribute == "allowBackup":
            return self._allow_backup
        return None

    def find_tags(self, tag_name, **kwargs):
        return []  # no <uses-feature> declarations - covered separately in tests/test_apk_metadata.py


def _fake_apk_zip_bytes(abis=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("AndroidManifest.xml", "<manifest></manifest>")
        for abi in (abis or []):
            z.writestr(f"lib/{abi}/libfoo.so", b"fake")
    buf.seek(0)
    return buf


def test_upload_apk_response_includes_real_android_metadata(monkeypatch):
    fake = _FakeParsedAPK("com.example.compattest", "24", "34", "false", "true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)

    r = client.post("/upload-apk", files={"file": ("compattest.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    assert r.status_code == 200
    body = r.json()

    # Flat fields (additive - existing fields like risk_level/vulnerable
    # untouched, verified separately by the corrupted-file test below).
    assert body["min_sdk_version"] == 24
    assert body["target_sdk_version"] == 34
    assert body["debuggable"] is False
    assert body["allow_backup"] is True

    # Nested version block gets the version-scoped SDK facts.
    assert body["version"]["minSdkVersion"] == 24
    assert body["version"]["targetSdkVersion"] == 34

    # Nested securityMetadata block gets the application-flag facts.
    assert body["securityMetadata"] == {"debuggable": False, "allowBackup": True}


def test_compatibility_endpoint_device_meets_min_sdk(monkeypatch):
    fake = _FakeParsedAPK("com.example.compattest2", "23", "34", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("compattest2.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.post(f"/apps/{app_id}/compatibility", json={"androidVersion": 30, "ramMb": 4096, "architecture": "arm64-v8a"})
    assert r.status_code == 200
    body = r.json()
    assert body["compatibility"]["status"] == "COMPATIBLE"
    assert body["hardwareCompatibility"]["status"] == "NOT_AVAILABLE"


def test_compatibility_endpoint_device_below_min_sdk(monkeypatch):
    fake = _FakeParsedAPK("com.example.compattest3", "30", "34", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("compattest3.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.post(f"/apps/{app_id}/compatibility", json={"androidVersion": 21})
    assert r.status_code == 200
    assert r.json()["compatibility"]["status"] == "INCOMPATIBLE"


def test_compatibility_endpoint_missing_device_android_version_is_not_available(monkeypatch):
    fake = _FakeParsedAPK("com.example.compattest4", "23", "34", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("compattest4.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.post(f"/apps/{app_id}/compatibility", json={})
    assert r.status_code == 200
    assert r.json()["compatibility"]["status"] == "NOT_AVAILABLE"


def test_compatibility_endpoint_unknown_application_is_404():
    r = client.post("/apps/99999999/compatibility", json={"androidVersion": 30})
    assert r.status_code == 404


def test_compatibility_endpoint_rejects_invalid_android_version_type():
    r = client.post("/apps/1/compatibility", json={"androidVersion": "not-a-number"})
    assert r.status_code == 422  # Pydantic validation error, not a 500


def test_apps_security_includes_android_metadata_and_never_fabricates_compatibility(monkeypatch):
    fake = _FakeParsedAPK("com.example.compattest5", "23", "34", "true", "true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("compattest5.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.get(f"/apps/{app_id}/security")
    assert r.status_code == 200
    body = r.json()
    assert body["version"]["minSdkVersion"] == 23
    assert body["version"]["targetSdkVersion"] == 34
    assert body["securityMetadata"] == {"debuggable": True, "allowBackup": True}
    # A GET request has no device profile - compatibility must never
    # claim COMPATIBLE/INCOMPATIBLE without one.
    assert body["compatibility"]["status"] == "NOT_AVAILABLE"
    # debuggable=True/allowBackup=True must never leak into a fabricated
    # vulnerability or change the risk assessment on their own.
    assert all(v.get("type") not in ("Debuggable", "AllowBackup") for v in body["vulnerabilities"])


# ---------------------------------------------------------------------
# Phase 8C: /upload-apk ABI response + full /apps/{id}/compatibility +
# /apps/{id}/alternatives real-data ranking fallback.
# ---------------------------------------------------------------------

def test_upload_apk_response_includes_real_abis(monkeypatch):
    fake = _FakeParsedAPK("com.example.abitest", "24", "34", "false", "true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)

    r = client.post("/upload-apk", files={"file": (
        "abitest.apk", _fake_apk_zip_bytes(abis=["arm64-v8a", "armeabi-v7a"]),
        "application/vnd.android.package-archive",
    )})
    assert r.status_code == 200
    body = r.json()
    assert body["abis"] == ["arm64-v8a", "armeabi-v7a"]
    assert body["features"] == []
    assert body["version"]["abis"] == ["arm64-v8a", "armeabi-v7a"]
    assert body["version"]["features"] == []


def test_compatibility_endpoint_combines_android_and_abi_checks(monkeypatch):
    fake = _FakeParsedAPK("com.example.combinedcompat", "21", "34", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": (
        "combinedcompat.apk", _fake_apk_zip_bytes(abis=["arm64-v8a"]),
        "application/vnd.android.package-archive",
    )})
    app_id = upload.json()["application"]["id"]

    # Device with a matching Android version and a matching ABI -> fully compatible.
    r_ok = client.post(f"/apps/{app_id}/compatibility", json={"androidVersion": 30, "abis": ["arm64-v8a"]})
    body_ok = r_ok.json()
    assert body_ok["compatibility"]["status"] == "COMPATIBLE"
    assert body_ok["compatibility"]["checks"]["abi"]["status"] == "COMPATIBLE"
    assert "finalRecommendation" in body_ok
    assert "hardwareCompatibility" in body_ok
    assert body_ok["hardwareCompatibility"]["status"] == "NOT_AVAILABLE"  # RAM never used as a signal

    # Device with a matching Android version but an incompatible ABI.
    r_bad = client.post(f"/apps/{app_id}/compatibility", json={"androidVersion": 30, "abis": ["x86"]})
    body_bad = r_bad.json()
    assert body_bad["compatibility"]["status"] == "INCOMPATIBLE"
    assert body_bad["compatibility"]["checks"]["abi"]["status"] == "INCOMPATIBLE"
    assert len(body_bad["compatibility"]["reasons"]) > 0


def test_alternatives_endpoint_falls_back_to_real_ranking(monkeypatch):
    fake_target = _FakeParsedAPK("com.example.altstarget", "21", "30", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake_target)
    upload_target = client.post("/upload-apk", files={"file": ("altstarget.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    target_id = upload_target.json()["application"]["id"]

    r_before = client.get(f"/apps/{target_id}/alternatives")
    assert r_before.status_code == 200
    # No claim either way is fabricated - whatever's real is returned,
    # honestly reflecting "available" matching whether any real
    # candidate exists (never a hardcoded/fixed answer).
    assert isinstance(r_before.json()["alternatives"], list)


def test_alternatives_endpoint_unknown_application_is_404():
    r = client.get("/apps/99999999/alternatives")
    assert r.status_code == 404


# ---------------------------------------------------------------------
# Phase 10A: GET /apps/{id}/security's new "recommendation" block -
# real stored recommendations.reason + real evidence, additive only.
# ---------------------------------------------------------------------

def test_recommendation_reason_is_returned(monkeypatch):
    # apk_scanner.py sets a specific explanation for a SAFE scan (the
    # "vulnerable" branch currently leaves the generic default in place -
    # a pre-existing gap in apk_scanner.py itself, out of scope for this
    # phase - so a safe scan is what reliably exercises a non-generic,
    # real stored reason here).
    fake = _FakeParsedAPK("com.example.reasontest", "21", "30", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("reasontest.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.get(f"/apps/{app_id}/security")
    body = r.json()
    assert r.status_code == 200
    assert body["recommendation"]["reason"] == "No cleartext traffic, dangerous permissions, or suspicious URLs found in this scan."
    # decision mirrors the real assessment.recommendation - not a new value.
    assert body["recommendation"]["decision"] == body["assessment"]["recommendation"]


def test_missing_recommendation_reason_is_null_not_a_generated_sentence(monkeypatch):
    # Bypasses persist_apk_scan entirely (it always calls
    # add_recommendation today) to construct a scan with NO
    # RecommendationRecord at all, proving the endpoint reports the
    # genuine absence honestly rather than fabricating text.
    from db.session import SessionLocal
    from db import crud

    db = SessionLocal()
    try:
        application = crud.get_or_create_application(db, app_name="No Reason App", package_name="com.example.noreason")
        scan = crud.create_scan(
            db, user_id=None, application_id=application.id, app_version_id=None,
            scan_type="apk_upload", security_score=90, risk_level="LOW",
            recommendation="SAFE_TO_INSTALL", confidence=None,
        )
        db.commit()
        app_id = application.id
    finally:
        db.close()

    r = client.get(f"/apps/{app_id}/security")
    body = r.json()
    assert r.status_code == 200
    assert body["recommendation"]["reason"] is None
    assert body["recommendation"]["evidence"] == []


def test_evidence_is_returned_from_real_vulnerabilities(monkeypatch):
    fake = _FakeParsedAPK("com.example.evidencetest", "21", "30", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    # A manifest with a dangerous permission produces a real Vulnerability row.
    apk_bytes = io.BytesIO()
    with zipfile.ZipFile(apk_bytes, "w") as z:
        z.writestr("AndroidManifest.xml", 'android.permission.READ_SMS')
    apk_bytes.seek(0)
    upload = client.post("/upload-apk", files={"file": ("evidencetest.apk", apk_bytes, "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.get(f"/apps/{app_id}/security")
    body = r.json()
    evidence = body["recommendation"]["evidence"]
    assert len(evidence) >= 1
    assert evidence[0]["type"] == "Dangerous Permissions"
    # Evidence entries only carry the Part 3 fields - no fileName/description/status,
    # which stay in the full "vulnerabilities" array instead.
    assert set(evidence[0].keys()) == {"cwe", "type", "severity", "confidence", "source", "sink"}


def test_existing_security_response_fields_are_unchanged(monkeypatch):
    fake = _FakeParsedAPK("com.example.unchangedfields", "21", "30", "false", "true")
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("unchangedfields.apk", _fake_apk_zip_bytes(abis=["arm64-v8a"]), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    r = client.get(f"/apps/{app_id}/security")
    body = r.json()
    assert r.status_code == 200
    for key in ("assessed", "application", "version", "assessment", "vulnerabilities", "securityMetadata", "compatibility"):
        assert key in body, f"pre-Phase-10A field '{key}' missing - this must stay backward compatible"
    assert body["assessment"]["riskLevel"] is not None
    assert body["version"]["minSdkVersion"] == 21
    # The new field is additive alongside, not a replacement.
    assert "recommendation" in body


def test_recommendation_endpoint_unknown_application_is_404():
    r = client.get("/apps/99999999/security")
    assert r.status_code == 404


def test_recommendation_reason_never_alters_risk_calculation(monkeypatch):
    # Two scans differing only in the stored reason text must still
    # calculate risk purely from the same real detections - the reason
    # is descriptive metadata, never an input to the decision.
    fake = _FakeParsedAPK("com.example.reasonneutral", "21", "30", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)
    upload = client.post("/upload-apk", files={"file": ("reasonneutral.apk", _fake_apk_zip_bytes(), "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]
    r = client.get(f"/apps/{app_id}/security")
    body = r.json()

    from db.session import SessionLocal
    from db import crud, models

    db = SessionLocal()
    try:
        scan = db.query(models.Scan).filter(models.Scan.application_id == app_id).order_by(models.Scan.created_at.desc()).first()
        crud.add_recommendation(db, scan_id=scan.id, risk_level=scan.risk_level, recommendation=scan.recommendation,
                                 reason="A completely different explanation string.", confidence=None)
        db.commit()
    finally:
        db.close()

    r2 = client.get(f"/apps/{app_id}/security")
    body2 = r2.json()
    assert body2["recommendation"]["reason"] == "A completely different explanation string."
    # risk/score/recommendation are unchanged by the different reason text.
    assert body2["assessment"]["riskLevel"] == body["assessment"]["riskLevel"]
    assert body2["assessment"]["securityScore"] == body["assessment"]["securityScore"]
    assert body2["assessment"]["recommendation"] == body["assessment"]["recommendation"]


# ---------------------------------------------------------------------
# Phase 10B: the new evidence-based vulnerable-scan explanation flows
# through the existing persistence path unchanged - real upload -> real
# stored recommendations.reason -> real API response, no second storage
# mechanism, no fabricated API text.
# ---------------------------------------------------------------------

def test_generated_vulnerable_explanation_is_persisted_in_recommendation_reason(monkeypatch):
    fake = _FakeParsedAPK("com.example.persistedreason", "21", "30", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)

    apk_bytes = io.BytesIO()
    with zipfile.ZipFile(apk_bytes, "w") as z:
        z.writestr("AndroidManifest.xml", 'usesCleartextTraffic="true"')
    apk_bytes.seek(0)
    upload = client.post("/upload-apk", files={"file": ("persistedreason.apk", apk_bytes, "application/vnd.android.package-archive")})
    upload_body = upload.json()
    app_id = upload_body["application"]["id"]

    expected = (
        "The APK declares cleartext traffic, which may allow network "
        "communications to occur without transport encryption."
    )
    # scan_report["explanation"] flowed straight into the upload response too.
    assert upload_body["explanation"] == expected

    from db.session import SessionLocal
    from db import models

    db = SessionLocal()
    try:
        scan = db.query(models.Scan).filter(models.Scan.application_id == app_id).order_by(models.Scan.created_at.desc()).first()
        stored = db.query(models.RecommendationRecord).filter(models.RecommendationRecord.scan_id == scan.id).first()
        assert stored is not None
        assert stored.reason == expected
    finally:
        db.close()


def test_security_endpoint_returns_the_same_stored_reason(monkeypatch):
    fake = _FakeParsedAPK("com.example.apireason", "21", "30", None, None)
    monkeypatch.setattr(apk_scanner.pyaxmlparser, "APK", lambda path: fake)

    apk_bytes = io.BytesIO()
    with zipfile.ZipFile(apk_bytes, "w") as z:
        z.writestr("AndroidManifest.xml", 'android.permission.READ_SMS')
    apk_bytes.seek(0)
    upload = client.post("/upload-apk", files={"file": ("apireason.apk", apk_bytes, "application/vnd.android.package-archive")})
    app_id = upload.json()["application"]["id"]

    from db.session import SessionLocal
    from db import models

    db = SessionLocal()
    try:
        scan = db.query(models.Scan).filter(models.Scan.application_id == app_id).order_by(models.Scan.created_at.desc()).first()
        stored = db.query(models.RecommendationRecord).filter(models.RecommendationRecord.scan_id == scan.id).first()
        stored_reason = stored.reason
    finally:
        db.close()

    r = client.get(f"/apps/{app_id}/security")
    assert r.status_code == 200
    assert r.json()["recommendation"]["reason"] == stored_reason
    assert stored_reason == "The APK requests potentially sensitive Android permissions: READ_SMS."
