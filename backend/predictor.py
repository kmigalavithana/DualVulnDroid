import hashlib
import os
import re
import json
import time
import joblib
import numpy as np
import xgboost as xgb
import shap

import decision_engine
from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary
from security_features import extract_security_features
from ml.feature_pipeline import build_feature_matrix, full_feature_names
from ml.evaluate import LABELS_ORDER

# =====================================================
# PATHS
# =====================================================
# Phase 11: the production model is now the RESEARCH-EVAL-1 fair-
# comparison XGBoost artifact (research_eval_artifacts/xgboost/) - the
# exact artifact whose test-set macro-F1 (0.7874) was the basis for
# selecting XGBoost as the production model over SVM/RF/LSTM/CodeBERT
# (see RESEARCH-EVAL-6's final comparison). This is DIFFERENT from the
# older ml/artifacts/ model that was loaded here previously: that one
# was trained on the "xgb_plus_dataflow_features" ablation subset
# (7,595 dims), not the full hybrid feature set (7,610 dims) the
# research comparison actually evaluated - verified by inspecting both
# artifacts' metadata, not assumed. ml/artifacts/ and xgboost_artifacts/
# are kept on disk for historical reference but are no longer loaded.

ARTIFACT_DIR = "research_eval_artifacts/xgboost"
FEATURES_DIR = "research_eval_artifacts/shared_features"

MODEL_PATH = os.path.join(ARTIFACT_DIR, "model.json")
MODEL_METADATA_PATH = os.path.join(ARTIFACT_DIR, "metadata.json")
WORD_VECTORIZER = os.path.join(FEATURES_DIR, "word_vectorizer.joblib")
CHAR_VECTORIZER = os.path.join(FEATURES_DIR, "char_vectorizer.joblib")
COUNT_VECTORIZER = os.path.join(FEATURES_DIR, "count_vectorizer.joblib")

# =====================================================
# LABEL MAPPING (matches ml/evaluate.py, the single source of truth
# used throughout training/evaluation)
# =====================================================

reverse_mapping = {i: label for i, label in enumerate(LABELS_ORDER)}

# =====================================================
# LOAD VECTORIZERS + FEATURE CONFIG
# =====================================================

word_vectorizer = joblib.load(WORD_VECTORIZER)
char_vectorizer = joblib.load(CHAR_VECTORIZER)
count_vectorizer = joblib.load(COUNT_VECTORIZER)

# research_eval/train_xgboost.py always trains on the full hybrid feature
# set (text + all 23 security features, no ablation subset) - unlike the
# older ml/train.py pipeline this replaces, there is no
# training_config.json-style ablation choice to read here.
INCLUDE_SECURITY_FEATURES, SECURITY_FEATURE_SUBSET = True, None

# =====================================================
# LOAD XGBOOST MODEL
# =====================================================
# The saved booster contains MORE trees than were actually selected
# (early stopping trains `early_stopping_rounds` extra rounds past the
# best iteration before stopping) - loading and predicting with the raw
# booster silently uses those extra, non-selected trees and does not
# reproduce the evaluated research result (a real bug found and fixed
# during the research phases; see research_eval/features.py's
# load_xgboost_booster()/xgboost_predict()). Rather than requiring every
# call site here to remember an iteration_range, the booster is sliced
# ONCE at load time to exactly the selected rounds, so predict() and the
# SHAP explainer below both automatically only ever see the right trees.

with open(MODEL_METADATA_PATH) as _f:
    _model_metadata = json.load(_f)
_NUM_BOOST_ROUND_SELECTED = _model_metadata["final_hyperparameters"]["num_boost_round_selected"]

_raw_booster = xgb.Booster()
_raw_booster.load_model(MODEL_PATH)
model = _raw_booster[0:_NUM_BOOST_ROUND_SELECTED]

PREDICTION_MODEL_NAME = "XGBoost-Hybrid" if INCLUDE_SECURITY_FEATURES else "XGBoost-Baseline"

with open(MODEL_PATH, "rb") as _f:
    _MODEL_VERSION = hashlib.sha256(_f.read()).hexdigest()[:12]
with open(WORD_VECTORIZER, "rb") as _f:
    _FEATURE_PIPELINE_VERSION = hashlib.sha256(_f.read()).hexdigest()[:12]

PRODUCTION_MODEL_INFO = {
    "algorithm": "XGBoost",
    "modelVersion": _MODEL_VERSION,
    "featurePipelineVersion": _FEATURE_PIPELINE_VERSION,
    "classOrder": list(LABELS_ORDER),
    "numBoostRoundSelected": _NUM_BOOST_ROUND_SELECTED,
    "researchArtifactSource": "RESEARCH-EVAL-1 (backend/research_eval_artifacts/xgboost/)",
}

print(f"[SUCCESS] XGBoost model loaded successfully ({PREDICTION_MODEL_NAME}, "
      f"security_features={INCLUDE_SECURITY_FEATURES}, subset={SECURITY_FEATURE_SUBSET}, "
      f"rounds={_NUM_BOOST_ROUND_SELECTED}/{_raw_booster.num_boosted_rounds()}, "
      f"model_version={_MODEL_VERSION})")

try:
    explainer = shap.TreeExplainer(model)
    print("[SUCCESS] SHAP TreeExplainer initialized")

    ALL_FEATURE_NAMES = np.array(full_feature_names(
        word_vectorizer, char_vectorizer, count_vectorizer,
        include_security=INCLUDE_SECURITY_FEATURES, security_feature_subset=SECURITY_FEATURE_SUBSET
    ))
    print(f"[SUCCESS] Cached {len(ALL_FEATURE_NAMES)} feature names for SHAP")
except Exception as e:
    print(f"[WARNING] Could not initialize SHAP explainer: {e}")
    explainer = None
    ALL_FEATURE_NAMES = []

# =====================================================
# LABEL INFO
# =====================================================

LABEL_INFO = {
    "s0": {"vulnerable": True, "type": "SQL Injection"},
    "s1": {"vulnerable": False, "type": "SQL Injection"},
    "v0": {"vulnerable": True, "type": "Certificate Validation"},
    "v1": {"vulnerable": False, "type": "Certificate Validation"},
}

EXPLANATION_TEXT = {
    "s0": "Potential SQL Injection detected.",
    "s1": "Secure SQL query detected.",
    "v0": "Unsafe Certificate Validation detected.",
    "v1": "Secure Certificate Validation detected.",
}

RULE_KEYWORDS = {
    "s0": ["rawquery(", "execsql(", "sqlitequerybuilder", "select ", "insert ", "update ", "delete "],
    "v0": ["hostnameverifier", "trustmanager", "sslcontext", "checkservertrusted", "checkclienttrusted", "return true"],
}

CWE_BY_TYPE = {
    "SQL Injection": "CWE-89",
    "Certificate Validation": "CWE-295",
    "Network Security": None,
    "None": None,
}

# A confident VULNERABLE/SUSPICIOUS_REVIEW/SAFE decision maps to a base
# severity; CRITICAL is reserved for a VULNERABLE decision where multiple
# strong signals concur (evidence_score comfortably clears the threshold,
# not just barely) - a deterministic function of the already-computed
# decision_engine evidence score, not a separate guess.
CRITICAL_EVIDENCE_SCORE = 3.0


def _severity_from_decision(decision: str, evidence_score: float) -> str:
    if decision == "VULNERABLE":
        return "CRITICAL" if evidence_score >= CRITICAL_EVIDENCE_SCORE else "HIGH"
    if decision == "SUSPICIOUS_REVIEW":
        return "MEDIUM"
    return "LOW"

# =====================================================
# PREDICT
# =====================================================


def predict_code(code: str, file_name: str = "", capture_timing: bool = False):
    """
    capture_timing (latency-measurement experiment task, Part 3): when
    True, attaches an internal "_timing" dict (prediction_ms/dataflow_ms/
    decision_ms) to the returned result, using time.perf_counter() (a
    monotonic, high-resolution clock - never wall-clock time.time()).
    Default False, and every timing call site below is gated behind this
    flag, so a normal call (capture_timing omitted) performs exactly zero
    additional perf_counter() calls or dict work versus before this
    parameter existed - detection logic/values are completely unchanged
    either way. app.py strips "_timing" back out before deciding whether
    to expose a "timing" block in the HTTP response (only when the
    caller's own explicit debug/benchmark header was set), so this is
    never present in a normal production response.
    """

    # ----------------------------------
    # Guard: empty / whitespace-only input
    # ----------------------------------
    if not code or not code.strip():
        return {
            "prediction": "none",
            "vulnerable": False,
            "vulnerabilityType": "None",
            "confidence": 0.0,
            "explanation": "No code provided.",
            "detections": [],
            "dataFlow": [],
            "predictionModel": PREDICTION_MODEL_NAME,
            "decision": "SAFE",
            "securityFeatures": {},
            "severity": "LOW",
            "shapTopFeatures": [],
        }

    # ----------------------------------
    # XML Rule-based Engine
    # ----------------------------------
    if file_name.endswith(".xml"):
        detections = []
        is_vulnerable = False
        lines = code.splitlines()

        if file_name == "AndroidManifest.xml":
            for index, line in enumerate(lines):
                if 'android:usescleartexttraffic="true"' in line.lower():
                    detections.append({"line": index, "code": line.strip(), "type": "Network Security"})
                    is_vulnerable = True

        elif file_name == "network_security_config.xml":
            in_debug = False
            for index, line in enumerate(lines):
                lower = line.lower()
                if "<debug-overrides>" in lower:
                    in_debug = True
                if "</debug-overrides>" in lower:
                    in_debug = False

                if "<base-config" in lower and 'cleartexttrafficpermitted="true"' in lower:
                    detections.append({"line": index, "code": line.strip(), "type": "Network Security"})
                    is_vulnerable = True

                if '<certificates src="user"' in lower and not in_debug:
                    detections.append({"line": index, "code": line.strip(), "type": "Network Security"})
                    is_vulnerable = True

        return {
            "prediction": "v2" if is_vulnerable else "v3",
            "vulnerable": is_vulnerable,
            "vulnerabilityType": "Network Security" if is_vulnerable else "None",
            "confidence": 100.0 if is_vulnerable else 0.0,
            "explanation": "Risky Network Security Configuration detected." if is_vulnerable else "No risky network configuration found.",
            "detections": detections,
            "dataFlow": [],
            "predictionModel": "Rule-Based (XML)",
            "decision": "VULNERABLE" if is_vulnerable else "SAFE",
            "securityFeatures": {},
            "severity": "HIGH" if is_vulnerable else "LOW",
            "shapTopFeatures": [],
        }

    # ----------------------------------
    # ML prediction (shared feature pipeline - identical construction to training)
    # ----------------------------------
    _t_prediction_start = time.perf_counter() if capture_timing else None
    features = build_feature_matrix(
        [code], word_vectorizer, char_vectorizer, count_vectorizer,
        include_security=INCLUDE_SECURITY_FEATURES, security_feature_subset=SECURITY_FEATURE_SUBSET
    )
    dmatrix = xgb.DMatrix(features)
    probabilities = model.predict(dmatrix)
    _t_prediction_end = time.perf_counter() if capture_timing else None

    prediction = int(np.argmax(probabilities))
    confidence = float(np.max(probabilities) * 100)
    label = reverse_mapping[prediction]
    info = LABEL_INFO[label]

    # ----------------------------------
    # Per-request SHAP contributions for the predicted class (used by
    # /developer/explain). Computed unconditionally so an explanation is
    # available even when the top prediction is a SAFE class - the
    # per-class loop below only computes SHAP for classes it treats as
    # "vulnerable", which would otherwise skip this entirely.
    # ----------------------------------
    shap_top_features = []
    if explainer is not None and len(ALL_FEATURE_NAMES) > 0:
        try:
            top_class_shap_values = explainer.shap_values(dmatrix)
            if isinstance(top_class_shap_values, list):
                top_class_shap = top_class_shap_values[prediction][0]
            elif len(top_class_shap_values.shape) == 3:
                top_class_shap = top_class_shap_values[0, :, prediction]
            else:
                top_class_shap = top_class_shap_values[0]

            top_idx = np.argsort(np.abs(top_class_shap))[-8:][::-1]
            shap_top_features = [
                {"feature": str(ALL_FEATURE_NAMES[idx]), "shapValue": round(float(top_class_shap[idx]), 5)}
                for idx in top_idx
            ]
        except Exception as e:
            print(f"[SHAP ERROR] {e}")

    # ----------------------------------
    # Rule-based / SHAP line localization for all classes > 5% probability
    # ----------------------------------
    detections = []
    lines = code.splitlines()
    probs_array = probabilities[0] if len(probabilities.shape) > 1 else probabilities

    # Hoisted above the line-localization loop below (it used to only be
    # computed after it, for decision_engine.evaluate()) so the loop's own
    # placeholder suppression can reuse this already-multi-line-aware
    # analysis instead of only ever checking the single keyword line - see
    # the loop's use of it just below.
    sink_safety = sql_sink_safety_summary(code)

    for i, prob in enumerate(probs_array):
        class_prob = float(prob * 100)
        label_key = reverse_mapping[i]
        label_info = LABEL_INFO[label_key]

        if label_info["vulnerable"] and class_prob > 5.0:
            keywords = RULE_KEYWORDS.get(label_key, [])
            important_words = keywords.copy()
            shap_weights = {}

            if explainer is not None and len(ALL_FEATURE_NAMES) > 0 and i == prediction:
                try:
                    shap_values = explainer.shap_values(dmatrix)
                    if isinstance(shap_values, list):
                        current_class_shap = shap_values[i][0]
                    elif len(shap_values.shape) == 3:
                        current_class_shap = shap_values[0, :, i]
                    else:
                        current_class_shap = shap_values[0]

                    top_indices = np.argsort(current_class_shap)[-10:]
                    for idx in top_indices:
                        if current_class_shap[idx] > 0:
                            feat_name = ALL_FEATURE_NAMES[idx]
                            if len(feat_name) > 2 and feat_name.replace('_', '').isalnum():
                                important_words.append(feat_name)
                                shap_weights[feat_name] = float(current_class_shap[idx])
                except Exception as e:
                    print(f"[SHAP ERROR] {e}")

            for index, line in enumerate(lines):
                lower = line.lower()
                found_words = [word for word in important_words if word in lower]
                if not found_words:
                    continue

                if label_key == "s0" and any(k in lower for k in keywords):
                    line_has_placeholder = "?" in line
                    line_has_concat = "+" in line or "concat(" in lower
                    # The '?' placeholder and the sink call it belongs to
                    # are often on different lines (e.g. `val sql = "...?"`
                    # followed later by `db.rawQuery(sql, args)`) - the
                    # single-line check above misses that entirely.
                    # sink_safety already resolves that multi-line/
                    # variable-indirected case (dataflow.py's
                    # sql_sink_safety_summary), so trust it whenever every
                    # SQL sink call in the file was confirmed parameterized.
                    confirmed_safe_by_dataflow = (
                        sink_safety.get("sinks_found", 0) > 0 and sink_safety.get("all_parameterized")
                    )
                    if (line_has_placeholder and not line_has_concat) or confirmed_safe_by_dataflow:
                        continue

                line_risk_weight = 0.0
                line_critical_words = []
                for fw in found_words:
                    if fw in shap_weights:
                        line_risk_weight += shap_weights[fw]
                        line_critical_words.append(fw)

                detections.append({
                    "line": index,
                    "code": line.strip(),
                    "type": label_info["type"],
                    "risk_weight": round(line_risk_weight, 4) if line_risk_weight > 0 else 0.5,
                    "critical_words": line_critical_words,
                })

    rule_keyword_hit = len(detections) > 0

    # ----------------------------------
    # Limited source-to-sink data-flow analysis (CWE-89 / CWE-295) -
    # independent evidence from the ML/keyword scan above.
    # ----------------------------------
    data_flow_findings = []

    _t_dataflow_start = time.perf_counter() if capture_timing else None
    sql_flow = analyze_sql_dataflow(code)
    for f in sql_flow:
        detections.append({
            "line": f["line"], "code": f["code"], "type": "SQL Injection",
            "risk_weight": 1.0, "critical_words": [],
            "source_to_sink_path": f["path"], "dataflow_explanation": f["explanation"],
        })
        data_flow_findings.append({**f, "vulnerabilityType": "SQL Injection", "verdict": "VULNERABLE"})

    cert_flow = analyze_cert_dataflow(code)
    for f in cert_flow:
        if f["verdict"] == "SAFE":
            continue
        line_idx = f["line"]
        code_text = lines[line_idx].strip() if 0 <= line_idx < len(lines) else f["component"]
        detections.append({
            "line": line_idx, "code": code_text, "type": "Certificate Validation",
            "risk_weight": 1.0 if f["verdict"] == "VULNERABLE" else 0.5, "critical_words": [],
            "source_to_sink_path": f["path"], "dataflow_explanation": f["explanation"],
            "dataflow_verdict": f["verdict"],
        })
        data_flow_findings.append({**f, "vulnerabilityType": "Certificate Validation"})

    # sink_safety was already computed above (hoisted for the
    # line-localization loop's placeholder suppression) - reused here
    # as-is, not recomputed, so both call sites always see the same value.
    _t_dataflow_end = time.perf_counter() if capture_timing else None

    # ----------------------------------
    # Hybrid Decision Engine: combines ML probability + static rule +
    # data-flow evidence into one documented decision (see
    # decision_engine.py for the exact weights/thresholds).
    # ----------------------------------
    _t_decision_start = time.perf_counter() if capture_timing else None
    decision_result = decision_engine.evaluate(
        label, confidence, sql_flow, cert_flow, sink_safety, rule_keyword_hit
    )
    _t_decision_end = time.perf_counter() if capture_timing else None
    decision = decision_result["decision"]
    is_vulnerable = decision_result["vulnerable"]

    non_ml_reasons = [r["detail"] for r in decision_result["reasons"] if r["source"] != "ml_model"]
    if decision == "VULNERABLE":
        explanation_text = non_ml_reasons[0] if non_ml_reasons else EXPLANATION_TEXT.get(label, "Potential vulnerability detected.")
    elif decision == "SAFE":
        explanation_text = non_ml_reasons[0] if non_ml_reasons else "No strong vulnerability pattern found."
    else:
        explanation_text = (
            "Evidence is mixed or inconclusive - flagged for manual review rather than "
            "an automatic verdict. See 'reasons' for the individual signals considered."
        )

    result = {
        "prediction": label,
        "vulnerable": is_vulnerable,
        "vulnerabilityType": info["type"],
        "confidence": round(confidence, 2),
        "explanation": explanation_text,
        "detections": detections,
        "dataFlow": data_flow_findings,
        "predictionModel": PREDICTION_MODEL_NAME,
        "decision": decision,
        "decisionEvidence": decision_result["reasons"],
        "securityFeatures": dict(extract_security_features(code)),
        "severity": _severity_from_decision(decision, decision_result["evidence_score"]),
        "shapTopFeatures": shap_top_features,
    }
    if capture_timing:
        # Internal only - see this function's docstring. app.py reads
        # this key and decides whether to surface it as the response's
        # public "timing" block; it is never returned to a caller that
        # didn't explicitly ask for it.
        #
        # prediction_ms/dataflow_ms/decision_ms do NOT sum to
        # backend_total_ms (added by app.py) - the gap between
        # prediction_ms ending and dataflow_ms starting is real,
        # unlabeled-here time: the SHAP explainer run (both the
        # unconditional top-class pass and the per-class loop above,
        # lines ~257-340) plus the rule-keyword line-localization it
        # drives. Reported explicitly as shap_and_rule_detection_ms
        # rather than left as a silent, unexplained remainder.
        result["_timing"] = {
            "prediction_ms": (_t_prediction_end - _t_prediction_start) * 1000,
            "shap_and_rule_detection_ms": (_t_dataflow_start - _t_prediction_end) * 1000,
            "dataflow_ms": (_t_dataflow_end - _t_dataflow_start) * 1000,
            "decision_ms": (_t_decision_end - _t_decision_start) * 1000,
        }
    return result

# =====================================================
# RESPONSE ADAPTERS (Phase 4)
#
# Pure reshaping of predict_code()'s output - no new analysis happens
# here, so /developer/predict and /developer/explain can never disagree
# with /predict's verdict. This is what keeps the API layer from
# duplicating the shared pipeline.
# =====================================================

RECOMMENDATION_BY_DECISION = {
    "VULNERABLE": "REVIEW",
    "SUSPICIOUS_REVIEW": "MANUAL_REVIEW_RECOMMENDED",
    "SAFE": "NONE",
}


def _normalize_dataflow_entry(f: dict) -> dict:
    return {
        "source": f["path"][0] if f.get("path") else None,
        "sink": f.get("sink") or f.get("component"),
        "path": f.get("path", []),
        "verdict": f.get("verdict"),
    }


def _evidence_score_from_reasons(reasons: list) -> float:
    return sum(r.get("contribution", 0) for r in reasons)


def generate_explanation_sentences(result: dict) -> list:
    """
    Builds a human-readable explanation purely from already-computed real
    values (security features, decision evidence, model output). Every
    sentence is only included when the underlying real signal is present
    for THIS request - nothing here is a fixed/fabricated template.
    """
    sentences = []
    feats = result.get("securityFeatures", {})
    vuln_type = result.get("vulnerabilityType")

    if vuln_type == "SQL Injection":
        if feats.get("sql_source_to_sink"):
            sentences.append("User-controlled input reaches SQL execution.")
        if feats.get("sql_string_concatenation"):
            sentences.append("SQL string concatenation is present.")
        if feats.get("sql_sink_detected") and not feats.get("sql_parameterized_query"):
            sentences.append("Parameterized query arguments are absent.")
        elif feats.get("sql_parameterized_query"):
            sentences.append("SQL sink calls use parameterized placeholders with a separate arguments array.")
    elif vuln_type == "Certificate Validation":
        if feats.get("certificate_return_true"):
            sentences.append("HostnameVerifier.verify() unconditionally returns true.")
        if feats.get("certificate_empty_trust_check"):
            sentences.append("A TrustManager check method has an empty body.")
        if feats.get("certificate_exception_validation") or feats.get("certificate_default_verifier"):
            sentences.append("Certificate/hostname validation delegates to a real check.")
        if feats.get("webview_handler_proceed"):
            sentences.append("The WebView SSL error handler calls proceed() unconditionally.")
        if feats.get("webview_handler_cancel"):
            sentences.append("The WebView SSL error handler calls cancel(), rejecting the connection.")

    cwe = CWE_BY_TYPE.get(vuln_type)
    if cwe:
        confidence = result.get("confidence", 0)
        confidence_word = "high" if confidence >= 75 else ("moderate" if confidence >= 50 else "low")
        sentences.append(
            f"{result.get('predictionModel', 'The model')} predicts a {confidence_word} "
            f"probability ({confidence:.1f}%) of {cwe}."
        )

    for r in result.get("decisionEvidence", []):
        if r["source"] != "ml_model" and r["detail"] not in sentences:
            sentences.append(r["detail"])

    return sentences if sentences else ["No strong evidence found for or against this classification."]


def to_developer_response(result: dict) -> dict:
    """Reshapes predict_code()'s output for /developer/predict and /developer/scan."""
    evidence_score = _evidence_score_from_reasons(result.get("decisionEvidence", []))
    decision_confidence = (
        round(1 / (1 + np.exp(-evidence_score)), 4)
        if result.get("decisionEvidence") else round(result["confidence"] / 100, 4)
    )

    return {
        "vulnerable": result["vulnerable"],
        "vulnerabilityType": result["vulnerabilityType"],
        "cwe": CWE_BY_TYPE.get(result["vulnerabilityType"]),
        "confidence": result["confidence"],
        "severity": result["severity"],
        "model": {
            "name": result["predictionModel"], "version": "production",
            **PRODUCTION_MODEL_INFO,
        },
        "dataFlow": [_normalize_dataflow_entry(f) for f in result.get("dataFlow", [])],
        "securityFeatures": result.get("securityFeatures", {}),
        "decision": {
            "riskLevel": result["severity"],
            "recommendation": RECOMMENDATION_BY_DECISION.get(result["decision"], "REVIEW"),
            "decisionConfidence": decision_confidence,
            "evidence": result.get("decisionEvidence", []),
        },
        "explanation": generate_explanation_sentences(result),
        "detections": result.get("detections", []),
    }


def to_explain_response(result: dict) -> dict:
    """Reshapes predict_code()'s output for /developer/explain."""
    rule_evidence = [d for d in result.get("detections", []) if "source_to_sink_path" not in d]
    return {
        "vulnerability": result["vulnerabilityType"],
        "cwe": CWE_BY_TYPE.get(result["vulnerabilityType"]),
        "vulnerable": result["vulnerable"],
        "confidence": result["confidence"],
        "severity": result["severity"],
        "shapContributions": result.get("shapTopFeatures", []),
        "dataFlowEvidence": [_normalize_dataflow_entry(f) for f in result.get("dataFlow", [])],
        "ruleEvidence": rule_evidence,
        "securityFeatures": result.get("securityFeatures", {}),
        "explanation": generate_explanation_sentences(result),
    }


# =====================================================
# URL HEURISTIC CHECK (rule-based, NOT a trained model)
# =====================================================


def predict_url(url: str):
    """
    Rule-based heuristic check for suspicious URLs (IP-literal hosts,
    known phishing/malware keyword patterns). This is not a trained
    classifier - callers/UI must not present it as an ML/AI verdict.
    """
    url_lower = url.lower()

    has_ip = bool(re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', url_lower))

    suspicious_keywords = ["free-", "hack", "update-now", "win-prize", "stealer", "trojan", "malware", ".ru", "admin"]
    has_suspicious_keyword = any(kw in url_lower for kw in suspicious_keywords)

    is_malicious = False
    reasons = []

    if has_ip:
        is_malicious = True
        reasons.append("Contains IP Address instead of Domain")

    if has_suspicious_keyword:
        is_malicious = True
        reasons.append("Contains suspicious keywords typical of phishing/malware")

    return {
        "url": url,
        "is_malicious": is_malicious,
        "reason": ", ".join(reasons) if is_malicious else "Safe",
    }

# =====================================================
# TEST
# =====================================================


if __name__ == "__main__":

    sample = """
    Cursor cursor = db.rawQuery(
        "SELECT * FROM users WHERE id=" + userId,
        null
    );
    """

    result = predict_code(sample)

    print("\n========================================")
    print(" XGBoost Prediction")
    print("========================================")

    print(json.dumps(result, indent=4))

    print("========================================")
