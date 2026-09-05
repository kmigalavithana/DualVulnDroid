"""
Data-driven calibration of decision_engine.py's VULNERABLE_THRESHOLD /
SAFE_THRESHOLD, using the VALIDATION split only (never test).

The decision engine is a selective/triage classifier: it auto-decides
VULNERABLE or SAFE when the evidence is strong enough, and otherwise
defers to SUSPICIOUS_REVIEW for a human to check. The right calibration
objective for that kind of system is "how accurate are the auto-decided
cases", subject to auto-deciding a reasonable share of cases (if the
thresholds are so wide that almost nothing gets auto-decided, the engine
isn't useful; if they're so narrow that almost everything is force-
decided, the review bucket is pointless and it degenerates into a plain
ML threshold).

Run from backend/, after ml/train.py has produced ml/artifacts/:
    python -m ml.calibrate_decision_engine
"""

import hashlib
import json
import os
import numpy as np
import pandas as pd
import joblib
import xgboost as xgb

import decision_engine
from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary
from ml.feature_pipeline import build_feature_matrix, load_production_feature_config
from ml.evaluate import LABELS_ORDER
from ml.experiment_d import rule_keyword_hit_for

ARTIFACT_DIR = "ml/artifacts"
DATA_DIR = "ml/data"

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}
MIN_COVERAGE = 0.40


def collect_val_evidence():
    wv = joblib.load(os.path.join(ARTIFACT_DIR, "word_vectorizer.pkl"))
    cv = joblib.load(os.path.join(ARTIFACT_DIR, "char_vectorizer.pkl"))
    ctv = joblib.load(os.path.join(ARTIFACT_DIR, "count_vectorizer.pkl"))
    booster = xgb.Booster()
    booster.load_model(os.path.join(ARTIFACT_DIR, "xgboost_model.json"))

    val_df = pd.read_csv(os.path.join(DATA_DIR, "val.csv"))
    include_security, security_subset = load_production_feature_config(ARTIFACT_DIR)
    X_val = build_feature_matrix(val_df["vulnerable_line"], wv, cv, ctv,
                                  include_security=include_security, security_feature_subset=security_subset)
    probs = booster.predict(xgb.DMatrix(X_val))

    scores, true_is_vulnerable = [], []
    for i, row in val_df.reset_index(drop=True).iterrows():
        code = row["vulnerable_line"]
        true_label = row["label"]
        p = probs[i]
        top_idx = int(np.argmax(p))
        ml_label = INT_TO_LABEL[top_idx]
        ml_confidence_pct = float(p[top_idx] * 100)

        sql_flow = analyze_sql_dataflow(code)
        cert_flow = analyze_cert_dataflow(code)
        sink_safety = sql_sink_safety_summary(code)
        rule_hit = rule_keyword_hit_for(code, ml_label)

        evidence_score, _ = decision_engine.compute_evidence(
            ml_label, ml_confidence_pct, sql_flow, cert_flow, sink_safety, rule_hit
        )
        scores.append(evidence_score)
        true_is_vulnerable.append(true_label in ("s0", "v0"))

    return np.array(scores), np.array(true_is_vulnerable)


def calibrate(scores, true_is_vulnerable):
    candidates = np.unique(np.round(np.percentile(scores, np.arange(5, 96, 5)), 3))

    best = None
    for safe_thr in candidates:
        for vuln_thr in candidates:
            if vuln_thr <= safe_thr:
                continue
            auto_vuln = scores >= vuln_thr
            auto_safe = scores <= safe_thr
            auto_mask = auto_vuln | auto_safe
            coverage = auto_mask.mean()
            if coverage < MIN_COVERAGE:
                continue

            correct = ((auto_vuln & true_is_vulnerable) | (auto_safe & ~true_is_vulnerable)).sum()
            accuracy_among_auto = correct / auto_mask.sum()

            candidate_result = (accuracy_among_auto, coverage, safe_thr, vuln_thr)
            if best is None or (accuracy_among_auto, coverage) > (best[0], best[1]):
                best = candidate_result

    return best


def main():
    scores, true_is_vulnerable = collect_val_evidence()
    result = calibrate(scores, true_is_vulnerable)

    if result is None:
        print("[calibrate] no threshold pair met MIN_COVERAGE - keeping decision_engine.py defaults")
        return

    # P0 Step 5: decision_engine.py only trusts this file when its
    # model_version matches the model actually in production - stamping
    # it here (the same sha256-prefix convention predictor.py already
    # uses for PRODUCTION_MODEL_INFO) makes that check possible instead
    # of silently reusing thresholds calibrated against whatever model
    # happened to be in ARTIFACT_DIR when this script last ran.
    with open(os.path.join(ARTIFACT_DIR, "xgboost_model.json"), "rb") as _f:
        model_version = hashlib.sha256(_f.read()).hexdigest()[:12]

    accuracy_among_auto, coverage, safe_thr, vuln_thr = result
    output = {
        "safe_threshold": float(safe_thr),
        "vulnerable_threshold": float(vuln_thr),
        "validation_accuracy_among_auto_decided": float(accuracy_among_auto),
        "validation_auto_decided_coverage": float(coverage),
        "validation_row_count": int(len(scores)),
        "model_version": model_version,
        "calibrated_against": os.path.join(ARTIFACT_DIR, "xgboost_model.json"),
        "note": (
            "Thresholds chosen on the VALIDATION split by maximizing accuracy "
            "among auto-decided (non-SUSPICIOUS_REVIEW) cases, subject to at "
            "least 40% coverage. Never touched the test split. Only trusted by "
            "decision_engine.py when model_version matches the model actually "
            "in production."
        ),
    }

    with open(os.path.join(ARTIFACT_DIR, "decision_engine_thresholds.json"), "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
