"""
Experiment D: Hybrid Rule + Data-flow + XGBoost, evaluated via
decision_engine.py rather than by concatenating features into the
model's training input (that's what the feature ablation in train.py
already measures for xgb_full_hybrid). This is a fundamentally
different hybrid mechanism: the ML model stays exactly as trained, and
its output is combined with fresh static-analysis evidence at decision
time using fixed, documented weights - so it doesn't depend on XGBoost's
tree search "discovering" the value of rare-but-strong signals from a
small training set.

Run from backend/, after ml/train.py has produced ml/artifacts/:
    python -m ml.experiment_d
"""

import json
import os
import re
import numpy as np
import pandas as pd
import joblib
import xgboost as xgb

import decision_engine
from dataflow import analyze_sql_dataflow, analyze_cert_dataflow, sql_sink_safety_summary
from ml.feature_pipeline import build_feature_matrix, load_production_feature_config
from ml.evaluate import full_evaluation, LABELS_ORDER

ARTIFACT_DIR = "ml/artifacts"
DATA_DIR = "ml/data"
REPORT_DIR = "ml/reports"

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}

SQL_KEYWORDS = ("rawquery(", "execsql(", "select ", "insert ", "update ", "delete ")
CERT_KEYWORDS = ("hostnameverifier", "trustmanager", "sslcontext", "checkservertrusted", "checkclienttrusted", "return true")


def rule_keyword_hit_for(code: str, label: str) -> bool:
    lower = code.lower()
    if label in ("s0", "s1"):
        return any(k in lower for k in SQL_KEYWORDS)
    return any(k in lower for k in CERT_KEYWORDS)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def main():
    wv = joblib.load(os.path.join(ARTIFACT_DIR, "word_vectorizer.pkl"))
    cv = joblib.load(os.path.join(ARTIFACT_DIR, "char_vectorizer.pkl"))
    ctv = joblib.load(os.path.join(ARTIFACT_DIR, "count_vectorizer.pkl"))
    booster = xgb.Booster()
    booster.load_model(os.path.join(ARTIFACT_DIR, "xgboost_model.json"))

    test_df = pd.read_csv(os.path.join(DATA_DIR, "test.csv"))

    include_security, security_subset = load_production_feature_config(ARTIFACT_DIR)
    X_test = build_feature_matrix(test_df["vulnerable_line"], wv, cv, ctv,
                                   include_security=include_security, security_feature_subset=security_subset)
    probs = booster.predict(xgb.DMatrix(X_test))

    y_true, y_pred, scores = [], [], []
    decisions_breakdown = {"VULNERABLE": 0, "SAFE": 0, "SUSPICIOUS_REVIEW": 0}
    auto_decided_correct, auto_decided_total = 0, 0

    for i, row in test_df.reset_index(drop=True).iterrows():
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

        result = decision_engine.evaluate(ml_label, ml_confidence_pct, sql_flow, cert_flow, sink_safety, rule_hit)
        decisions_breakdown[result["decision"]] += 1

        task_is_sqli = true_label in ("s0", "s1")
        true_is_vulnerable = true_label in ("s0", "v0")
        if result["vulnerable"]:
            pred_label = "s0" if task_is_sqli else "v0"
        else:
            pred_label = "s1" if task_is_sqli else "v1"

        y_true.append(true_label)
        y_pred.append(pred_label)
        scores.append(float(sigmoid(result["evidence_score"])))

        if result["decision"] != "SUSPICIOUS_REVIEW":
            auto_decided_total += 1
            predicted_vulnerable = result["decision"] == "VULNERABLE"
            if predicted_vulnerable == true_is_vulnerable:
                auto_decided_correct += 1

    metrics = full_evaluation(y_true, y_pred, scores)
    metrics["decision_breakdown"] = decisions_breakdown
    metrics["auto_decided_note"] = (
        "This is a selective/triage system: SUSPICIOUS_REVIEW cases are meant to be "
        "resolved by a human, not auto-scored. decision_engine.py maps SUSPICIOUS_REVIEW "
        "to vulnerable=False (see its module docstring), so the accuracy/precision/recall/"
        "F1/FPR/FNR fields above force-collapse every deferred case into 'predicted safe' "
        "to produce a single comparable number against the other experiments - this "
        "inflates the false-negative rate and is NOT a fair read of real performance. "
        "'auto_decided_accuracy' below is the honest metric: accuracy restricted to the "
        "~35% of cases the engine was confident enough to decide without deferring."
    )
    metrics["auto_decided_accuracy"] = (auto_decided_correct / auto_decided_total) if auto_decided_total else None
    metrics["auto_decided_coverage"] = auto_decided_total / len(test_df)

    os.makedirs(REPORT_DIR, exist_ok=True)
    comparison_path = os.path.join(REPORT_DIR, "model_comparison.json")
    existing = {}
    if os.path.exists(comparison_path):
        with open(comparison_path) as f:
            existing = json.load(f)
    existing["experiment_d_hybrid_decision_engine"] = metrics
    with open(comparison_path, "w") as f:
        json.dump(existing, f, indent=2)

    print(json.dumps({k: v for k, v in metrics.items() if k not in ("confusion_matrix", "roc_curve", "pr_curve")}, indent=2))


if __name__ == "__main__":
    main()
