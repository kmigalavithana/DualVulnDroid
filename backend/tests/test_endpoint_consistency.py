"""
Phase 5B, sections 8-10: verifies /predict and /developer/scan (via a
single-file batch) never produce contradictory classifications for the
same input. Both routes ultimately call predictor.predict_code() - this
test proves that's actually true end-to-end via the real HTTP layer,
rather than just asserting it by inspection of app.py.

This is a backend-level consistency question (both endpoints live in the
same FastAPI app), so it's verified here with TestClient rather than
requiring a live server from the Kotlin/Gradle side - the same pattern
already used by test_api.py.

Run from backend/:  python -m pytest tests/test_endpoint_consistency.py -v
"""

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

CONFIDENCE_TOLERANCE_PCT = 0.01  # both routes call predict_code() once each; should match exactly

# Mirrors predictor.py's RECOMMENDATION_BY_DECISION exactly - used only to
# translate /predict's raw decision string into the same vocabulary
# /developer/scan's decision.recommendation uses, so the two can be
# compared. (/developer/scan's decision.riskLevel is the SEVERITY tier,
# not the raw decision - already checked separately via `severity`.)
RECOMMENDATION_BY_DECISION = {
    "VULNERABLE": "REVIEW",
    "SUSPICIOUS_REVIEW": "MANUAL_REVIEW_RECOMMENDED",
    "SAFE": "NONE",
}


SQL_VULNERABLE = '''
public class LoginActivity extends Activity {
    public void onCreate() {
        String username = getIntent().getStringExtra("username");
        String query = "SELECT * FROM users WHERE name=" + username;
        db.rawQuery(query, null);
    }
}
'''

SQL_SAFE = 'db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});'

CERT_VULNERABLE = '''
val hv = object : HostnameVerifier {
    override fun verify(hostname: String, session: SSLSession): Boolean {
        return true
    }
}
'''

CERT_SAFE = '''
class RealTrustManager implements X509TrustManager {
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        if (chain == null || chain.length == 0) {
            throw new CertificateException("Empty chain");
        }
        defaultTrustManager.checkServerTrusted(chain, authType);
    }
}
'''

UNRELATED_SAFE = 'Log.d("TAG", "hello world"); int x = 5 + 3;'


def _predict_result(code, file_name):
    r = client.post("/predict", json={"code": code, "fileName": file_name})
    assert r.status_code == 200
    return r.json()


def _developer_scan_result(code, file_name):
    r = client.post("/developer/scan", json={"files": [{"code": code, "fileName": file_name}]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["files"]) == 1
    entry = body["files"][0]
    assert entry.get("error") is None, f"batch scan returned an error: {entry.get('error')}"
    return entry["result"]


def _assert_consistent(code, file_name, expected_vulnerable):
    predict = _predict_result(code, file_name)
    scan = _developer_scan_result(code, file_name)

    # ---- vulnerability type ----
    assert predict["vulnerabilityType"] == scan["vulnerabilityType"], (
        f"vulnerabilityType mismatch: /predict={predict['vulnerabilityType']!r} "
        f"vs /developer/scan={scan['vulnerabilityType']!r}"
    )

    # ---- CWE: /predict has no `cwe` field, so only check when /developer/scan has one ----
    if scan.get("cwe") is not None:
        expected_cwe = {"SQL Injection": "CWE-89", "Certificate Validation": "CWE-295"}.get(scan["vulnerabilityType"])
        assert scan["cwe"] == expected_cwe

    # ---- severity ----
    assert predict["severity"] == scan["severity"], (
        f"severity mismatch: /predict={predict['severity']!r} vs /developer/scan={scan['severity']!r}"
    )

    # ---- confidence, within tolerance (should be exact - same model, same input) ----
    assert abs(predict["confidence"] - scan["confidence"]) <= CONFIDENCE_TOLERANCE_PCT, (
        f"confidence mismatch beyond tolerance: /predict={predict['confidence']} vs /developer/scan={scan['confidence']}"
    )

    # ---- data-flow result ----
    predict_flow_verdicts = sorted(f["verdict"] for f in predict["dataFlow"])
    scan_flow_verdicts = sorted(f["verdict"] for f in scan["dataFlow"])
    assert predict_flow_verdicts == scan_flow_verdicts, (
        f"dataFlow verdicts mismatch: /predict={predict_flow_verdicts} vs /developer/scan={scan_flow_verdicts}"
    )

    # ---- decision result ----
    # /predict exposes the raw decision string (VULNERABLE/SAFE/SUSPICIOUS_REVIEW);
    # /developer/scan exposes it translated into a recommendation - both
    # endpoints must be deriving from the SAME underlying decision.
    expected_recommendation = RECOMMENDATION_BY_DECISION[predict["decision"]]
    assert scan["decision"]["recommendation"] == expected_recommendation, (
        f"decision mismatch: /predict.decision={predict['decision']!r} implies recommendation="
        f"{expected_recommendation!r}, but /developer/scan.decision.recommendation="
        f"{scan['decision']['recommendation']!r}"
    )
    # riskLevel is severity-derived on both sides - already cross-checked via `severity` above,
    # this just confirms the sub-object is internally consistent with it.
    assert scan["decision"]["riskLevel"] == scan["severity"]
    assert predict["vulnerable"] == scan["vulnerable"] == expected_vulnerable, (
        f"vulnerable mismatch for expected={expected_vulnerable}: "
        f"/predict={predict['vulnerable']} vs /developer/scan={scan['vulnerable']}"
    )


# ---------------------------------------------------------------------
# Section 9: the 5 required cases
# ---------------------------------------------------------------------

def test_sql_vulnerable_is_consistent():
    _assert_consistent(SQL_VULNERABLE, "Login.java", expected_vulnerable=True)


def test_sql_parameterized_safe_is_consistent():
    _assert_consistent(SQL_SAFE, "Login.java", expected_vulnerable=False)


def test_certificate_vulnerable_is_consistent():
    _assert_consistent(CERT_VULNERABLE, "Net.kt", expected_vulnerable=True)


def test_certificate_safe_is_consistent():
    _assert_consistent(CERT_SAFE, "Net.java", expected_vulnerable=False)


def test_unrelated_safe_code_is_consistent():
    _assert_consistent(UNRELATED_SAFE, "Main.java", expected_vulnerable=False)


# ---------------------------------------------------------------------
# Section 10: explicit non-contradiction check across all 5 at once
# ---------------------------------------------------------------------

def test_no_endpoint_ever_contradicts_the_other_across_all_cases():
    cases = [
        (SQL_VULNERABLE, "Login.java"),
        (SQL_SAFE, "Login.java"),
        (CERT_VULNERABLE, "Net.kt"),
        (CERT_SAFE, "Net.java"),
        (UNRELATED_SAFE, "Main.java"),
    ]
    contradictions = []
    for code, file_name in cases:
        predict = _predict_result(code, file_name)
        scan = _developer_scan_result(code, file_name)
        if predict["vulnerable"] != scan["vulnerable"]:
            contradictions.append((file_name, predict["vulnerable"], scan["vulnerable"]))

    assert contradictions == [], f"Found contradictory vulnerable verdicts: {contradictions}"
