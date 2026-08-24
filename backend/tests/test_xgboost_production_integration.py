"""
PHASE 11: regression tests for making the RESEARCH-EVAL-1 XGBoost
artifact (research_eval_artifacts/xgboost/) the explicit production
model, replacing the older ml/artifacts/ model that predictor.py
previously loaded.

Run from backend/:  python -m pytest tests/test_xgboost_production_integration.py -v
"""

import numpy as np
import pytest

import predictor
from ml.evaluate import LABELS_ORDER

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

UNRELATED_SAFE = 'Log.d("TAG", "hello world"); int x = 5 + 3;'


# ---------------------------------------------------------------------
# 1. Production model loads successfully
# ---------------------------------------------------------------------

def test_production_model_loaded_from_research_eval_artifact():
    assert predictor.model is not None
    assert predictor.PRODUCTION_MODEL_INFO["algorithm"] == "XGBoost"
    assert predictor.PRODUCTION_MODEL_INFO["researchArtifactSource"].startswith("RESEARCH-EVAL-1")


def test_booster_is_sliced_to_the_selected_rounds_not_the_raw_saved_count():
    """The real bug the research phases found: loading the raw saved
    booster (which contains extra post-early-stopping trees) without
    respecting the selected cutoff silently changes predictions."""
    assert predictor.model.num_boosted_rounds() == predictor.PRODUCTION_MODEL_INFO["numBoostRoundSelected"]
    assert predictor.model.num_boosted_rounds() < predictor._raw_booster.num_boosted_rounds()


# ---------------------------------------------------------------------
# 2. Feature dimension matches model expectation
# ---------------------------------------------------------------------

def test_feature_dimension_is_the_full_hybrid_7610_not_the_old_7595():
    assert len(predictor.ALL_FEATURE_NAMES) == 7610


# ---------------------------------------------------------------------
# 3. Class order is correct
# ---------------------------------------------------------------------

def test_class_order_is_s0_v0_s1_v1():
    assert LABELS_ORDER == ["s0", "v0", "s1", "v1"]
    assert predictor.PRODUCTION_MODEL_INFO["classOrder"] == ["s0", "v0", "s1", "v1"]
    assert predictor.reverse_mapping == {0: "s0", 1: "v0", 2: "s1", 3: "v1"}


# ---------------------------------------------------------------------
# 4. Predictions are deterministic
# ---------------------------------------------------------------------

def test_predictions_are_deterministic():
    r1 = predictor.predict_code(VULNERABLE_SQL_TRACED)
    r2 = predictor.predict_code(VULNERABLE_SQL_TRACED)
    assert r1["prediction"] == r2["prediction"]
    assert r1["confidence"] == r2["confidence"]


# ---------------------------------------------------------------------
# 5. Probabilities sum approximately to 1
# ---------------------------------------------------------------------

def test_class_probabilities_sum_to_one():
    from ml.feature_pipeline import build_feature_matrix
    import xgboost as xgb
    features = build_feature_matrix(
        [VULNERABLE_SQL_TRACED], predictor.word_vectorizer, predictor.char_vectorizer, predictor.count_vectorizer,
        include_security=predictor.INCLUDE_SECURITY_FEATURES, security_feature_subset=predictor.SECURITY_FEATURE_SUBSET,
    )
    probs = predictor.model.predict(xgb.DMatrix(features))
    assert probs.shape[-1] == 4
    assert abs(float(np.sum(probs)) - 1.0) < 1e-4


# ---------------------------------------------------------------------
# 6. Confidence corresponds to the selected class probability
# ---------------------------------------------------------------------

def test_confidence_matches_the_predicted_classs_own_probability():
    from ml.feature_pipeline import build_feature_matrix
    import xgboost as xgb
    result = predictor.predict_code(VULNERABLE_SQL_TRACED)
    features = build_feature_matrix(
        [VULNERABLE_SQL_TRACED], predictor.word_vectorizer, predictor.char_vectorizer, predictor.count_vectorizer,
        include_security=predictor.INCLUDE_SECURITY_FEATURES, security_feature_subset=predictor.SECURITY_FEATURE_SUBSET,
    )
    probs = predictor.model.predict(xgb.DMatrix(features))[0]
    top_idx = int(np.argmax(probs))
    assert predictor.reverse_mapping[top_idx] == result["prediction"]
    assert abs(float(probs[top_idx]) * 100 - result["confidence"]) < 0.01


# ---------------------------------------------------------------------
# 7. SHAP is produced
# ---------------------------------------------------------------------

def test_shap_produced_for_vulnerable_prediction():
    result = predictor.predict_code(VULNERABLE_SQL_TRACED)
    assert isinstance(result["shapTopFeatures"], list)
    assert len(result["shapTopFeatures"]) > 0
    assert all("feature" in f and "shapValue" in f for f in result["shapTopFeatures"])


def test_shap_produced_for_safe_prediction():
    result = predictor.predict_code(SAFE_SQL)
    assert isinstance(result["shapTopFeatures"], list)
    assert len(result["shapTopFeatures"]) > 0


# ---------------------------------------------------------------------
# 8-12. Representative example outcomes
# ---------------------------------------------------------------------

def test_safe_sql_produces_safe_result():
    result = predictor.predict_code(SAFE_SQL)
    assert result["decision"] in ("SAFE", "SUSPICIOUS_REVIEW")
    assert result["securityFeatures"]["sql_parameterized_query"] == 1


def test_vulnerable_sql_produces_vulnerability_result():
    result = predictor.predict_code(VULNERABLE_SQL_TRACED)
    assert result["vulnerable"] is True
    assert result["vulnerabilityType"] == "SQL Injection"
    assert result["decision"] == "VULNERABLE"


def test_vulnerable_certificate_produces_certificate_result():
    result = predictor.predict_code(VULNERABLE_HOSTNAME_VERIFIER)
    assert result["vulnerable"] is True
    assert result["vulnerabilityType"] == "Certificate Validation"


def test_safe_certificate_produces_safe_result():
    result = predictor.predict_code(SAFE_CERT)
    assert not any(f["verdict"] == "VULNERABLE" for f in result["dataFlow"])


def test_unrelated_safe_code_remains_safe():
    result = predictor.predict_code(UNRELATED_SAFE)
    assert result["vulnerable"] is False
    assert result["dataFlow"] == []


# ---------------------------------------------------------------------
# 13. Decision Engine still receives the same evidence
# ---------------------------------------------------------------------

def test_decision_engine_receives_real_ml_label_and_confidence():
    """predict_code() must pass the ACTUAL top-1 label/confidence from
    THIS model into decision_engine.evaluate() - not a stale or
    hardcoded value - verified by checking the evidence reasons record
    the model's real predicted label."""
    result = predictor.predict_code(VULNERABLE_SQL_TRACED)
    ml_reason = next(r for r in result["decisionEvidence"] if r["source"] == "ml_model")
    assert result["prediction"] in ml_reason["detail"]
    assert f"{result['confidence']:.1f}%" in ml_reason["detail"]


# ---------------------------------------------------------------------
# 14. Old /predict contract remains compatible
# ---------------------------------------------------------------------

def test_predict_code_output_keys_unchanged():
    result = predictor.predict_code(VULNERABLE_SQL_TRACED)
    required_keys = {
        "prediction", "vulnerable", "vulnerabilityType", "confidence", "explanation",
        "detections", "dataFlow", "predictionModel", "decision", "securityFeatures",
        "severity", "shapTopFeatures", "decisionEvidence",
    }
    assert required_keys.issubset(result.keys())


def test_developer_response_model_field_is_additive_not_breaking():
    from predictor import to_developer_response
    result = predictor.predict_code(VULNERABLE_SQL_TRACED)
    dev = to_developer_response(result)
    # original fields must still be present and correctly typed
    assert dev["model"]["name"]
    assert dev["model"]["version"] == "production"
    # new fields are additive
    assert dev["model"]["algorithm"] == "XGBoost"
    assert dev["model"]["classOrder"] == ["s0", "v0", "s1", "v1"]


# ---------------------------------------------------------------------
# Cross-check against the research evaluation (Part 11 of the spec)
# ---------------------------------------------------------------------

def test_production_path_matches_research_evaluation_on_frozen_test_set():
    """The strongest possible integration check: run every one of the
    168 frozen test rows through the real predict_code() production
    path and verify its raw top-1 ML accuracy/macro-F1 exactly match the
    frozen research_eval_artifacts/xgboost/test_metrics.json result."""
    import json
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from research_eval.data_split import load_split, ARTIFACT_DIR
    from sklearn.metrics import f1_score

    _, _, test_df, _ = load_split()
    label_to_int = {l: i for i, l in enumerate(LABELS_ORDER)}

    y_true, y_pred = [], []
    for _, row in test_df.iterrows():
        result = predictor.predict_code(row["vulnerable_line"])
        y_true.append(label_to_int[row["label"]])
        y_pred.append(label_to_int[result["prediction"]])

    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    with open(os.path.join(ARTIFACT_DIR, "xgboost", "test_metrics.json")) as f:
        frozen = json.load(f)

    assert abs(accuracy - frozen["accuracy"]) < 1e-9
    assert abs(macro_f1 - frozen["macro_f1"]) < 1e-9
