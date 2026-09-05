"""
P0 Step 9: /predict request-size protection tests.

Normal-sized requests (A/B/C/D) are real, non-mocked integration tests
through FastAPI's TestClient against the real app - real predict_code(),
real XGBoost model, real data-flow analysis - the exact same pattern
tests/test_api.py already uses; /predict itself is never mocked. Only the
oversized-rejection proof (G) uses a test seam (monkeypatching the
predict_code name app.py actually calls) to verify the expensive ML/
data-flow pipeline is never reached - not a mock of the endpoint's HTTP
behavior, which is exercised for real in every test here.

Run from backend/:  python -m pytest tests/test_predict_size_limit.py -v
"""
import app as app_module
from app import PREDICT_MAX_CODE_SIZE_BYTES, app
from fastapi.testclient import TestClient

client = TestClient(app)

VULNERABLE_SQL_TRACED = '''
public class LoginActivity extends Activity {
    public void onCreate() {
        String username = getIntent().getStringExtra("username");
        String query = "SELECT * FROM users WHERE name=" + username;
        db.rawQuery(query, null);
    }
}
'''

SAFE_SQL = 'db.rawQuery("SELECT * FROM users WHERE id=?", new String[]{userId});'

VULNERABLE_HOSTNAME_VERIFIER = '''
val hv = object : HostnameVerifier {
    override fun verify(hostname: String, session: SSLSession): Boolean {
        return true
    }
}
'''


# ---------------------------------------------------------------------
# A/B/C: normal small requests - real pipeline, unmocked, must succeed
# ---------------------------------------------------------------------

def test_a_normal_small_sql_vulnerable_request_is_accepted():
    r = client.post("/predict", json={"code": VULNERABLE_SQL_TRACED, "fileName": "X.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is True
    assert body["vulnerabilityType"] == "SQL Injection"


def test_b_normal_small_safe_request_is_accepted():
    r = client.post("/predict", json={"code": SAFE_SQL, "fileName": "X.java"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is False


def test_c_normal_certificate_validation_request_is_accepted():
    r = client.post("/predict", json={"code": VULNERABLE_HOSTNAME_VERIFIER, "fileName": "X.kt"})
    assert r.status_code == 200
    body = r.json()
    assert body["vulnerable"] is True
    assert body["vulnerabilityType"] == "Certificate Validation"


# ---------------------------------------------------------------------
# D: exactly at / comfortably below the limit - accepted (real pipeline,
# unmocked - proves the gate does not reject legitimate large-but-valid
# requests, not just small ones)
# ---------------------------------------------------------------------

def test_d_request_comfortably_below_the_limit_is_accepted():
    padding = "// " + ("x" * (PREDICT_MAX_CODE_SIZE_BYTES - 10_000))
    code = f'public class Big {{ void m() {{ {SAFE_SQL} }} }}\n{padding}'
    assert len(code.encode("utf-8")) < PREDICT_MAX_CODE_SIZE_BYTES
    r = client.post("/predict", json={"code": code, "fileName": "Big.java"})
    assert r.status_code == 200


def test_d_request_exactly_at_the_limit_is_accepted():
    code = "a" * PREDICT_MAX_CODE_SIZE_BYTES
    assert len(code.encode("utf-8")) == PREDICT_MAX_CODE_SIZE_BYTES
    r = client.post("/predict", json={"code": code, "fileName": "AtLimit.java"})
    assert r.status_code == 200


# ---------------------------------------------------------------------
# E: just above the limit - rejected with the documented 413 status
# ---------------------------------------------------------------------

def test_e_request_just_above_the_limit_is_rejected_with_413():
    code = "a" * (PREDICT_MAX_CODE_SIZE_BYTES + 1)
    r = client.post("/predict", json={"code": code, "fileName": "OverLimit.java"})
    assert r.status_code == 413
    detail = r.json()["detail"]
    assert str(PREDICT_MAX_CODE_SIZE_BYTES) in detail
    assert "PREDICT_MAX_CODE_SIZE_BYTES" in detail


# ---------------------------------------------------------------------
# F: very large request - rejected early, same 413, not a timeout/500
# ---------------------------------------------------------------------

def test_f_very_large_request_is_rejected_with_413():
    huge = "a" * (PREDICT_MAX_CODE_SIZE_BYTES * 10)
    r = client.post("/predict", json={"code": huge, "fileName": "Huge.java"})
    assert r.status_code == 413


# ---------------------------------------------------------------------
# G: oversized input never reaches predict_code() - i.e. never reaches
# feature extraction, XGBoost, SHAP, or data-flow analysis
# ---------------------------------------------------------------------

def test_g_oversized_input_never_reaches_predict_code_pipeline(monkeypatch):
    called = {"hit": False}

    def _fail_if_called(*args, **kwargs):
        called["hit"] = True
        raise AssertionError("predict_code() must never be invoked for an oversized /predict request")

    # Patches the name app.py's /predict handler actually calls (bound via
    # `from predictor import predict_code` into app's own module globals),
    # not predictor.predict_code directly - this is the real call site,
    # not a mock of the /predict endpoint's HTTP behavior itself.
    monkeypatch.setattr(app_module, "predict_code", _fail_if_called)

    huge = "a" * (PREDICT_MAX_CODE_SIZE_BYTES + 1)
    r = client.post("/predict", json={"code": huge, "fileName": "Huge.java"})

    assert r.status_code == 413
    assert called["hit"] is False


def test_g_normal_request_still_reaches_predict_code_pipeline(monkeypatch):
    """Companion to the test above: proves the monkeypatch technique itself
    is valid (it WOULD be called for a normal-sized request) so the 'never
    called' assertion above is meaningful, not a false negative from a
    broken patch target."""
    called = {"hit": False}
    real_predict_code = app_module.predict_code

    def _tracking_wrapper(*args, **kwargs):
        called["hit"] = True
        return real_predict_code(*args, **kwargs)

    monkeypatch.setattr(app_module, "predict_code", _tracking_wrapper)

    r = client.post("/predict", json={"code": SAFE_SQL, "fileName": "X.java"})

    assert r.status_code == 200
    assert called["hit"] is True
