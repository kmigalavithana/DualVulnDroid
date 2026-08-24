"""
PHASE RESEARCH-EVAL-5A, Part 22/23: compares the frozen LSTM test result
against the frozen RESEARCH-EVAL-1 SVM/Random Forest/XGBoost results, all
on the IDENTICAL 168-row frozen test set. Reads only - never modifies
any of the RESEARCH-EVAL-1 result files.

IMPORTANT (Part 23): SVM/RF/XGBoost use the project's TF-IDF/count/
security-feature pipeline; LSTM uses a token-sequence representation.
The four models share the same data split and source data, but the
representation is model-appropriate rather than identical - this is
stated explicitly in the output, not glossed over.

Run from backend/, AFTER research_eval.lstm_evaluate:
    python -m research_eval.lstm_compare
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import ARTIFACT_DIR

OUT_DIR = os.path.join(ARTIFACT_DIR, "lstm")
FEATURE_REPRESENTATION_CAVEAT = (
    "The models share the same data split and source data, but the representation is "
    "model-appropriate rather than identical: SVM/Random Forest/XGBoost use the project's "
    "TF-IDF word/char n-grams + count vectorizer + 23 deterministic CWE-89/CWE-295 security "
    "features (ml/feature_pipeline.py, unchanged), while LSTM uses a learned embedding over "
    "a code-aware token sequence (research_eval/lstm_train.py's tokenizer). This is a real "
    "architectural difference, not an oversight - input representations are NOT identical."
)


def load_frozen(name, path):
    with open(path) as f:
        return json.load(f)


def main():
    lstm = load_frozen("LSTM", os.path.join(OUT_DIR, "test_metrics.json"))
    svm = load_frozen("SVM", os.path.join(ARTIFACT_DIR, "svm", "test_metrics.json"))
    rf = load_frozen("Random Forest", os.path.join(ARTIFACT_DIR, "random_forest", "test_metrics.json"))
    xgb = load_frozen("XGBoost", os.path.join(ARTIFACT_DIR, "xgboost", "test_metrics.json"))

    rows = []
    for name, m in [("Linear SVM", svm), ("Random Forest", rf), ("XGBoost", xgb), ("LSTM", lstm)]:
        rows.append({
            "Model": name,
            "Accuracy": round(m["accuracy"], 4),
            "Macro F1": round(m["macro_f1"], 4),
            "ROC-AUC": round(m["roc_auc"], 4) if m.get("roc_auc") is not None else None,
            "Binary F1": None,  # filled below from binary confusion matrix
            "FPR": round(m["false_positive_rate"], 4),
            "FNR": round(m["false_negative_rate"], 4),
        })
        bcm = m["binary_confusion_matrix"]
        tp, fp, fn = bcm["tp"], bcm["fp"], bcm["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        binary_f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        rows[-1]["Binary F1"] = round(binary_f1, 4)

    with open(os.path.join(OUT_DIR, "comparison_with_ml.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lstm_row = rows[-1]
    best_macro_f1 = max(rows, key=lambda r: r["Macro F1"])
    best_fnr = min(rows, key=lambda r: r["FNR"])

    summary = {
        "feature_representation_caveat": FEATURE_REPRESENTATION_CAVEAT,
        "comparison_table": rows,
        "lstm_rank_by_macro_f1": sorted(rows, key=lambda r: -r["Macro F1"]).index(lstm_row) + 1,
        "lstm_rank_by_fnr": sorted(rows, key=lambda r: r["FNR"]).index(lstm_row) + 1,
        "best_macro_f1_model": best_macro_f1["Model"],
        "best_fnr_model": best_fnr["Model"],
        "note": "Ranks are 1=best. No claim of 'LSTM is better' is made unless the table itself supports it.",
    }
    with open(os.path.join(OUT_DIR, "comparison_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    make_plot(rows)

    print(FEATURE_REPRESENTATION_CAVEAT)
    print(json.dumps(rows, indent=2, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k != "comparison_table" and k != "feature_representation_caveat"}, indent=2))
    return rows, summary


def make_plot(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plots_dir = os.path.join(OUT_DIR, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    names = [r["Model"] for r in rows]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = range(len(names))
    width = 0.2
    ax.bar([i - 1.5 * width for i in x], [r["Accuracy"] for r in rows], width, label="Accuracy")
    ax.bar([i - 0.5 * width for i in x], [r["Macro F1"] for r in rows], width, label="Macro F1")
    ax.bar([i + 0.5 * width for i in x], [r["FNR"] for r in rows], width, label="FNR")
    ax.bar([i + 1.5 * width for i in x], [r["FPR"] for r in rows], width, label="FPR")
    ax.set_xticks(list(x)); ax.set_xticklabels(names)
    ax.set_title("SVM vs Random Forest vs XGBoost vs LSTM (frozen 168-row test set)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(plots_dir, "model_comparison.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
