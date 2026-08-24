"""
PHASE RESEARCH-EVAL-2, Parts 12/13: false-negative and false-positive
tables for SVM, XGBoost, and XGBoost + Decision Engine, all on the same
168 frozen test rows.

"Reason for miss if determinable" is filled ONLY from facts already
present in the record (predicted-class rank/probability for pure ML
models; the decision engine's own recorded evidence reasons for the
hybrid pipeline) - never a guessed explanation. Where no such fact is
available, the field is literally "Cause not established.", per the
spec's explicit instruction not to guess.

Run from backend/, AFTER train_svm.py, train_xgboost.py, and
decision_engine_eval.py have all produced their artifacts:
    python -m research_eval.error_analysis
"""

import csv
import json
import os
import sys

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.features import load_features, transform, load_xgboost_booster, xgboost_predict
from research_eval.decision_engine_eval import run_pipeline as run_decision_engine_pipeline

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}
CWE_BY_LABEL_PREFIX = {"s": "CWE-89 (SQL Injection)", "v": "CWE-295 (Certificate Validation)"}
OUT_DIR = os.path.join(ARTIFACT_DIR, "security_selection")


def _cwe(label):
    return CWE_BY_LABEL_PREFIX[label[0]]


def _ml_miss_reason(true_label, probs_row, pred_label):
    """Only a determinable, factual observation - never a guess at WHY."""
    order = np.argsort(probs_row)[::-1]
    ranked_labels = [INT_TO_LABEL[i] for i in order]
    true_rank = ranked_labels.index(true_label)
    if true_rank == 1:
        return (f"True label '{true_label}' was the model's second-highest-probability class "
                f"({probs_row[LABEL_TO_INT[true_label]]:.3f} vs top '{pred_label}' "
                f"{probs_row[LABEL_TO_INT[pred_label]]:.3f}).")
    return "Cause not established."


def svm_predictions(test_df):
    wv, cv, ctv = load_features()
    X_test = transform(test_df, wv, cv, ctv)
    model = joblib.load(os.path.join(ARTIFACT_DIR, "svm", "model.joblib"))
    probs = model.predict_proba(X_test)
    classes = list(model.classes_)  # order of columns in `probs`, may not equal LABEL_TO_INT order
    # Re-order columns into LABELS_ORDER so downstream indexing by LABEL_TO_INT is valid.
    reordered = np.zeros((probs.shape[0], len(LABELS_ORDER)))
    for col, class_int in enumerate(classes):
        reordered[:, class_int] = probs[:, col]
    return reordered


def xgboost_predictions(test_df):
    wv, cv, ctv = load_features()
    X_test = transform(test_df, wv, cv, ctv)
    booster, num_boost_round = load_xgboost_booster()
    return xgboost_predict(booster, num_boost_round, X_test)


def ml_error_rows(name, test_df, test_idx, probs):
    fns, fps = [], []
    for i, row in test_df.reset_index(drop=True).iterrows():
        true_label = row["label"]
        p = probs[i]
        top_idx = int(np.argmax(p))
        pred_label = INT_TO_LABEL[top_idx]
        confidence = float(p[top_idx])

        true_vuln = true_label in VULNERABLE_LABELS
        pred_vuln = pred_label in VULNERABLE_LABELS

        base = {
            "approach": name,
            "row_identifier": test_idx[i],
            "true_label": true_label,
            "cwe": _cwe(true_label),
            "predicted_label": pred_label,
            "predicted_confidence": round(confidence, 4),
            "dataflow_evidence": "N/A (pure ML prediction, no decision-engine evidence)",
            "decision": "VULNERABLE" if pred_vuln else "SAFE",
        }
        if true_vuln and not pred_vuln:
            base["reason_for_miss"] = _ml_miss_reason(true_label, p, pred_label)
            fns.append(base)
        elif not true_vuln and pred_vuln:
            fps.append(base)
    return fns, fps


def _decision_engine_reason(record):
    """Factual summary of decision_engine.py's own recorded reasons -
    never a new guess, just restating what it already computed."""
    if record["deferred"]:
        return (f"Evidence score {record['evidence_score']:.3f} fell inside the SUSPICIOUS_REVIEW "
                f"band (safe_threshold < score < vulnerable_threshold) - deferred rather than "
                f"confidently decided. Reasons: {json.dumps(record['reasons'])}")
    return f"evidence_score={record['evidence_score']:.3f}. Reasons: {json.dumps(record['reasons'])}"


def decision_engine_error_rows(records):
    fns, fps = [], []
    for r in records:
        base = {
            "approach": "XGBoost + Decision Engine",
            "row_identifier": r["row_identifier"],
            "true_label": r["true_label"],
            "cwe": _cwe(r["true_label"]),
            "predicted_label": r["xgb_prediction"],
            "predicted_confidence": round(r["xgb_confidence_pct"] / 100.0, 4),
            "dataflow_evidence": json.dumps({
                "sql_traced": r["sql_dataflow_traced"],
                "sql_concat_only": r["sql_dataflow_concat_only"],
                "sql_all_parameterized": r["sql_all_sinks_parameterized"],
                "cert_verdict": r["cert_dataflow_verdict"],
            }),
            "decision": r["decision"],
            "deferred": r["deferred"],
        }
        if r["true_is_vulnerable"] and not r["final_vulnerable_flag"]:
            base["reason_for_miss"] = _decision_engine_reason(r)
            fns.append(base)
        elif not r["true_is_vulnerable"] and r["final_vulnerable_flag"]:
            fps.append(base)
    return fns, fps


def write_csv(rows, path):
    if not rows:
        with open(path, "w", newline="") as f:
            f.write("")
        return
    all_keys = []
    for r in rows:
        for k in r:
            if k not in all_keys:
                all_keys.append(k)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _, _, test_df, (_, _, test_idx) = load_split()

    svm_probs = svm_predictions(test_df)
    xgb_probs = xgboost_predictions(test_df)
    de_records = run_decision_engine_pipeline(test_df, test_idx)

    svm_fns, svm_fps = ml_error_rows("Linear SVM", test_df, test_idx, svm_probs)
    xgb_fns, xgb_fps = ml_error_rows("XGBoost", test_df, test_idx, xgb_probs)
    de_fns, de_fps = decision_engine_error_rows(de_records)

    all_fns = svm_fns + xgb_fns + de_fns
    all_fps = svm_fps + xgb_fps + de_fps

    write_csv(all_fns, os.path.join(OUT_DIR, "false_negatives.csv"))
    write_csv(all_fps, os.path.join(OUT_DIR, "false_positives.csv"))

    summary = {
        "n_false_negatives": {"Linear SVM": len(svm_fns), "XGBoost": len(xgb_fns), "XGBoost + Decision Engine": len(de_fns)},
        "n_false_positives": {"Linear SVM": len(svm_fps), "XGBoost": len(xgb_fps), "XGBoost + Decision Engine": len(de_fps)},
        "fn_vs_fp_comparison": {
            name: {"fn": n_fn, "fp": n_fp, "fn_exceeds_fp_by": n_fn - n_fp}
            for name, n_fn, n_fp in [
                ("Linear SVM", len(svm_fns), len(svm_fps)),
                ("XGBoost", len(xgb_fns), len(xgb_fps)),
                ("XGBoost + Decision Engine", len(de_fns), len(de_fps)),
            ]
        },
        "note_on_decision_engine_counts": (
            "XGBoost + Decision Engine's FN/FP counts here use the ALL-CASE VIEW "
            "(deferred cases counted as not-vulnerable, matching the engine's own "
            "real boolean output) - see decision_engine_metrics.json for the "
            "separate AUTO-DECISION VIEW (deferred cases excluded)."
        ),
    }
    with open(os.path.join(OUT_DIR, "error_analysis_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
