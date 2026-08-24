"""
PHASE RESEARCH-EVAL-2, Part 7: does XGBoost's predicted-class probability
actually track correctness? Measured, not assumed.

Loads the FROZEN RESEARCH-EVAL-1 XGBoost model + shared feature pipeline
(research_eval_artifacts/xgboost/, research_eval_artifacts/shared_features/)
and the frozen test split - no retraining, no new split.

Run from backend/:  python -m research_eval.confidence_analysis
"""

import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml.evaluate import LABELS_ORDER, VULNERABLE_LABELS
from research_eval.data_split import load_split, ARTIFACT_DIR
from research_eval.features import load_features, transform, load_xgboost_booster, xgboost_predict

LABEL_TO_INT = {label: i for i, label in enumerate(LABELS_ORDER)}
INT_TO_LABEL = {i: label for label, i in LABEL_TO_INT.items()}
OUT_DIR = os.path.join(ARTIFACT_DIR, "security_selection")

BUCKETS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.0001)]
BUCKET_LABELS = ["0.50-0.59", "0.60-0.69", "0.70-0.79", "0.80-0.89", "0.90-1.00"]


def load_xgboost_and_predict(test_df):
    wv, cv, ctv = load_features()
    X_test = transform(test_df, wv, cv, ctv)

    booster, num_boost_round = load_xgboost_booster()
    probs = xgboost_predict(booster, num_boost_round, X_test)
    return probs


def per_sample_records(test_df, test_idx, probs):
    records = []
    for i, row in test_df.reset_index(drop=True).iterrows():
        p = probs[i]
        top_idx = int(np.argmax(p))
        pred_label = INT_TO_LABEL[top_idx]
        true_label = row["label"]
        vuln_prob = float(p[LABEL_TO_INT["s0"]] + p[LABEL_TO_INT["v0"]])
        records.append({
            "row_identifier": test_idx[i],  # position in clean_dataset.csv - the dataset has no filename
            "true_label": true_label,
            "predicted_label": pred_label,
            "predicted_probability": float(p[top_idx]),
            "vulnerability_probability": vuln_prob,
            "correct": bool(pred_label == true_label),
        })
    return records


def bucket_summary(records):
    summary = []
    for (lo, hi), name in zip(BUCKETS, BUCKET_LABELS):
        in_bucket = [r for r in records if lo <= r["predicted_probability"] < hi]
        n = len(in_bucket)
        if n == 0:
            summary.append({"bucket": name, "n_samples": 0, "accuracy": None, "vulnerability_recall": None, "false_negative_rate": None})
            continue

        accuracy = sum(r["correct"] for r in in_bucket) / n

        vuln_rows = [r for r in in_bucket if r["true_label"] in VULNERABLE_LABELS]
        if vuln_rows:
            # "vulnerability recall" within this bucket: of the truly-vulnerable
            # rows landing in this confidence bucket, how many did the model's
            # TOP-1 prediction still correctly call vulnerable (any of s0/v0,
            # not necessarily the exact CWE)?
            correctly_flagged = sum(1 for r in vuln_rows if r["predicted_label"] in VULNERABLE_LABELS)
            recall = correctly_flagged / len(vuln_rows)
            fnr = 1 - recall
        else:
            recall, fnr = None, None

        summary.append({
            "bucket": name, "n_samples": n, "accuracy": accuracy,
            "vulnerability_recall": recall, "false_negative_rate": fnr,
        })
    return summary


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    train_df, val_df, test_df, (train_idx, val_idx, test_idx) = load_split()

    probs = load_xgboost_and_predict(test_df)
    records = per_sample_records(test_df, test_idx, probs)
    summary = bucket_summary(records)

    below_50 = sum(1 for r in records if r["predicted_probability"] < 0.50)

    csv_path = os.path.join(OUT_DIR, "confidence_analysis.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    output = {
        "n_test_samples": len(records),
        "n_samples_below_0.50_predicted_probability": below_50,
        "note_on_below_50_bucket": (
            "4-class softmax with 4 classes has a floor of 0.25 for the top "
            "probability; predictions below 0.50 exist and are excluded from "
            "the 5 requested 0.50+ buckets - not silently merged into any of them."
        ),
        "buckets": summary,
    }
    with open(os.path.join(OUT_DIR, "confidence_bucket_summary.json"), "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))
    return records, summary


if __name__ == "__main__":
    main()
