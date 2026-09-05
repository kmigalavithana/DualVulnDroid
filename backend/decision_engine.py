"""
Hybrid Decision Engine (Phase 3, section 12): combines the ML
probability with the static-rule and data-flow evidence into one final
decision, instead of a naive "if rule: vulnerable" or "trust only the ML
softmax" approach.

DOCUMENTED DECISION LOGIC
==========================
Every evidence source contributes a signed number to a running
`evidence_score` (positive = supports "vulnerable", negative = supports
"safe"). The weights below were chosen so that data-flow evidence -
which is a real traced/structural finding, not a guess - dominates a
merely-average-confidence ML prediction, matching the intent of
"strong evidence should not be overridden by low-to-mid ML confidence"
established in predictor.py's earlier cross-check.

  Source                                              Weight
  ------------------------------------------------------------
  ML prediction (signed by predicted class,
    magnitude = predicted-class probability)           x1.0
  Data-flow: traced source-to-sink (SQLi)              +2.0
  Data-flow: unparameterized concatenation (SQLi)      +1.2
  Data-flow: all SQL sinks confirmed parameterized     -1.5
  Data-flow: certificate check VULNERABLE              +2.0
  Data-flow: certificate check SUSPICIOUS               +0.6
  Data-flow: certificate check SAFE (delegates/throws) -1.5
  Static keyword rule also matched                     +0.4

Final decision from the total evidence_score:
  score >= VULNERABLE_THRESHOLD (1.5)   -> "VULNERABLE"
  score <= SAFE_THRESHOLD (-0.9)        -> "SAFE"
  otherwise                             -> "SUSPICIOUS_REVIEW"

These two threshold constants are reference defaults (chosen so the three
worked examples below classify correctly). ml/calibrate_decision_engine.py
data-drives a second, tuned set of thresholds from the VALIDATION split
(never the test split) and saves them to
ml/artifacts/decision_engine_thresholds.json; this module loads the
calibrated thresholds when that file exists AND explicitly declares a
`model_version` matching the model currently in production, falling back
to these defaults otherwise (P0 Step 5: a calibration file computed
against a different model artifact - different training run, different
feature dimensionality - is not valid for whatever model is actually
loaded, so it is never trusted silently). See ml/reports/model_comparison.json
for how each threshold choice performs on the held-out test set (evaluated
by ml/experiment_d.py).

Examples (from the design spec, verified in tests/test_decision_engine.py):
  ML=0.61, strong traced SQL source-to-sink            -> VULNERABLE
  ML=0.51, confirmed parameterized query                -> SAFE
  ML=0.55, no source-to-sink evidence either way         -> SUSPICIOUS_REVIEW

For backward compatibility with existing plugin/Flutter clients that
only understand a boolean `vulnerable` flag: ONLY "VULNERABLE" maps to
vulnerable=True. SAFE and SUSPICIOUS_REVIEW both map to False.
This was tested against realistic unrelated code and revisited: with the
current ~35% auto-decided coverage (see
ml/reports/model_comparison.json's experiment_d_hybrid_decision_engine),
mapping SUSPICIOUS_REVIEW to vulnerable=True would put a red warning on
most scanned files - including plainly unrelated code - since neither
the IDE plugin nor the Flutter app has a "needs review" UI yet. The full
3-way `decision` value is still returned so a future review-queue UI can
distinguish "confidently safe" from "uncertain, ask a human" without
another schema change.
"""

import hashlib
import json
import os
from collections import OrderedDict

ML_WEIGHT = 1.0
TRACED_SOURCE_TO_SINK_WEIGHT = 2.0
UNPARAMETERIZED_CONCAT_WEIGHT = 1.2
CONFIRMED_PARAMETERIZED_WEIGHT = -1.5
CERT_VULNERABLE_WEIGHT = 2.0
CERT_SUSPICIOUS_WEIGHT = 0.6
CERT_SAFE_WEIGHT = -1.5
STATIC_RULE_WEIGHT = 0.4

VULNERABLE_THRESHOLD = 1.5
SAFE_THRESHOLD = -0.9

_CALIBRATED_THRESHOLDS_PATH = os.path.join("ml", "artifacts", "decision_engine_thresholds.json")
# The production model currently loaded by predictor.py (see its own
# ARTIFACT_DIR/PRODUCTION_MODEL_INFO) - computed independently here so a
# calibration file can be checked for staleness at import time, before
# predictor.py (which imports THIS module) has computed its own copy.
_PRODUCTION_MODEL_PATH = os.path.join("research_eval_artifacts", "xgboost", "model.json")
_CURRENT_PRODUCTION_MODEL_VERSION = None
if os.path.exists(_PRODUCTION_MODEL_PATH):
    with open(_PRODUCTION_MODEL_PATH, "rb") as _f:
        _CURRENT_PRODUCTION_MODEL_VERSION = hashlib.sha256(_f.read()).hexdigest()[:12]

CALIBRATION_SOURCE = "hand-picked defaults (no calibration file found)"
if os.path.exists(_CALIBRATED_THRESHOLDS_PATH):
    try:
        with open(_CALIBRATED_THRESHOLDS_PATH) as _f:
            _calibrated = json.load(_f)
        _calibrated_model_version = _calibrated.get("model_version")
        # P0 Step 5: a calibration file is only trusted when it
        # explicitly declares the exact production model_version it was
        # computed against AND that matches what's actually loaded right
        # now. Thresholds calibrated against a different model artifact
        # (different training run, different feature dimensionality) are
        # not valid for this one - silently reusing them would mean the
        # VULNERABLE/SAFE cutoffs no longer correspond to this model's
        # real evidence-score distribution. Any ambiguity (field missing,
        # mismatch, or the production model file not found) falls back
        # to the hand-picked reference defaults above rather than
        # guessing.
        if (
            _calibrated_model_version is not None
            and _CURRENT_PRODUCTION_MODEL_VERSION is not None
            and _calibrated_model_version == _CURRENT_PRODUCTION_MODEL_VERSION
        ):
            VULNERABLE_THRESHOLD = _calibrated["vulnerable_threshold"]
            SAFE_THRESHOLD = _calibrated["safe_threshold"]
            CALIBRATION_SOURCE = (
                f"calibrated on validation set ({_CALIBRATED_THRESHOLDS_PATH}), "
                f"model_version={_calibrated_model_version}"
            )
        else:
            print(
                f"[decision_engine] ignoring {_CALIBRATED_THRESHOLDS_PATH}: it was calibrated "
                f"for model_version={_calibrated_model_version!r}, but the current production "
                f"model is {_CURRENT_PRODUCTION_MODEL_VERSION!r} - falling back to the "
                "hand-picked reference defaults until a calibration matching the current "
                "model is produced."
            )
            CALIBRATION_SOURCE = (
                f"hand-picked defaults ({_CALIBRATED_THRESHOLDS_PATH} exists but does not match "
                f"the current production model_version={_CURRENT_PRODUCTION_MODEL_VERSION!r}; ignored)"
            )
    except Exception as _e:
        print(f"[decision_engine] failed to load calibrated thresholds, using defaults: {_e}")

VULNERABLE_ML_LABELS = {"s0", "v0"}


def compute_evidence(label: str, ml_confidence_pct: float, sql_flow: list, cert_flow: list,
                      sink_safety: dict, rule_keyword_hit: bool) -> tuple:
    """
    Computes the raw evidence_score + reasons, WITHOUT applying the final
    VULNERABLE/SAFE/SUSPICIOUS_REVIEW thresholds - kept separate from
    evaluate() so the thresholds can be calibrated on a validation set
    (see ml/calibrate_decision_engine.py) without re-deriving the score
    itself.

    label: predicted top-1 class ("s0"/"v0"/"s1"/"v1")
    ml_confidence_pct: probability of that class, 0-100 (matches predictor.py's existing scale)
    sql_flow: output of dataflow.analyze_sql_dataflow()
    cert_flow: output of dataflow.analyze_cert_dataflow()
    sink_safety: output of dataflow.sql_sink_safety_summary()
    rule_keyword_hit: whether the SHAP/keyword rule scan independently found a supporting line

    Returns (evidence_score: float, reasons: list).
    """
    ml_confidence = max(0.0, min(1.0, ml_confidence_pct / 100.0))
    evidence_score = 0.0
    reasons = []

    # ---- ML evidence ----
    signed_ml = ml_confidence if label in VULNERABLE_ML_LABELS else -ml_confidence
    evidence_score += signed_ml * ML_WEIGHT
    reasons.append({
        "source": "ml_model",
        "detail": f"XGBoost predicts '{label}' with {ml_confidence_pct:.1f}% confidence",
        "contribution": round(signed_ml * ML_WEIGHT, 3),
    })

    # ---- SQL data-flow evidence ----
    traced = [f for f in sql_flow if f["detection_basis"] in ("traced-source", "traced-source-interprocedural")]
    concat_only = [f for f in sql_flow if f["detection_basis"] == "unparameterized-concatenation"]

    if traced:
        evidence_score += TRACED_SOURCE_TO_SINK_WEIGHT
        reasons.append({
            "source": "dataflow_sql",
            "detail": traced[0]["explanation"],
            "contribution": TRACED_SOURCE_TO_SINK_WEIGHT,
        })
    elif concat_only:
        evidence_score += UNPARAMETERIZED_CONCAT_WEIGHT
        reasons.append({
            "source": "dataflow_sql",
            "detail": concat_only[0]["explanation"],
            "contribution": UNPARAMETERIZED_CONCAT_WEIGHT,
        })
    elif sink_safety.get("sinks_found", 0) > 0 and sink_safety.get("all_parameterized"):
        evidence_score += CONFIRMED_PARAMETERIZED_WEIGHT
        reasons.append({
            "source": "dataflow_sql",
            "detail": "All SQL sink calls use parameterized placeholders with a separate arguments array",
            "contribution": CONFIRMED_PARAMETERIZED_WEIGHT,
        })

    # ---- Certificate data-flow evidence ----
    cert_vulnerable = [f for f in cert_flow if f["verdict"] == "VULNERABLE"]
    cert_suspicious = [f for f in cert_flow if f["verdict"] == "SUSPICIOUS"]
    cert_safe = [f for f in cert_flow if f["verdict"] == "SAFE"]

    if cert_vulnerable:
        evidence_score += CERT_VULNERABLE_WEIGHT
        reasons.append({
            "source": "dataflow_cert",
            "detail": cert_vulnerable[0]["explanation"],
            "contribution": CERT_VULNERABLE_WEIGHT,
        })
    elif cert_suspicious:
        evidence_score += CERT_SUSPICIOUS_WEIGHT
        reasons.append({
            "source": "dataflow_cert",
            "detail": cert_suspicious[0]["explanation"],
            "contribution": CERT_SUSPICIOUS_WEIGHT,
        })
    elif cert_safe:
        evidence_score += CERT_SAFE_WEIGHT
        reasons.append({
            "source": "dataflow_cert",
            "detail": cert_safe[0]["explanation"],
            "contribution": CERT_SAFE_WEIGHT,
        })

    # ---- Static keyword rule (weak, corroborating only) ----
    # A keyword hit only proves security-relevant API vocabulary is
    # present (e.g. every X509TrustManager/HostnameVerifier override -
    # safe or not - necessarily contains words like "checkServerTrusted"
    # or "HostnameVerifier"), never that its usage is unsafe. It must not
    # be allowed to nudge the score toward "vulnerable" when the real
    # structural data-flow check for the SAME category has already
    # confirmed SAFE (P0 Step 5) - otherwise the mere structural presence
    # of a security-relevant API would push a genuinely safe
    # implementation toward SUSPICIOUS_REVIEW for no real reason. It still
    # applies normally whenever that structural check found something
    # actually unsafe (or didn't run at all), so it keeps corroborating a
    # real vulnerable/ambiguous signal exactly as before.
    contradicted_by_confirmed_safe_dataflow = (
        (bool(cert_safe) and not cert_vulnerable and not cert_suspicious)
        or (
            sink_safety.get("sinks_found", 0) > 0
            and sink_safety.get("all_parameterized")
            and not traced
            and not concat_only
        )
    )
    if rule_keyword_hit and not contradicted_by_confirmed_safe_dataflow:
        evidence_score += STATIC_RULE_WEIGHT
        reasons.append({
            "source": "static_rule",
            "detail": "Keyword-based static rule also matched a supporting line",
            "contribution": STATIC_RULE_WEIGHT,
        })

    return evidence_score, reasons


def decide(evidence_score: float, vulnerable_threshold: float = VULNERABLE_THRESHOLD,
           safe_threshold: float = SAFE_THRESHOLD) -> str:
    if evidence_score >= vulnerable_threshold:
        return "VULNERABLE"
    elif evidence_score <= safe_threshold:
        return "SAFE"
    return "SUSPICIOUS_REVIEW"


def evaluate(label: str, ml_confidence_pct: float, sql_flow: list, cert_flow: list,
             sink_safety: dict, rule_keyword_hit: bool,
             vulnerable_threshold: float = VULNERABLE_THRESHOLD,
             safe_threshold: float = SAFE_THRESHOLD) -> dict:
    evidence_score, reasons = compute_evidence(
        label, ml_confidence_pct, sql_flow, cert_flow, sink_safety, rule_keyword_hit
    )
    decision = decide(evidence_score, vulnerable_threshold, safe_threshold)

    return OrderedDict([
        ("decision", decision),
        ("vulnerable", decision == "VULNERABLE"),
        ("evidence_score", round(evidence_score, 3)),
        ("reasons", reasons),
    ])
