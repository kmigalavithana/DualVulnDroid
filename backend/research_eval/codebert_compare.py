"""
PHASE RESEARCH-EVAL-5B, Part 23/25: compares the frozen, freshly-verified
CodeBERT test result against the frozen RESEARCH-EVAL-1 SVM/RF/XGBoost
results and the RESEARCH-EVAL-5A LSTM result, all on the identical
168-row frozen test set. Read-only against every prior result file.

Run from backend/, AFTER research_eval.codebert_evaluate:
    python -m research_eval.codebert_compare
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import ARTIFACT_DIR

OUT_DIR = os.path.join(ARTIFACT_DIR, "codebert")
FEATURE_REPRESENTATION_CAVEAT = (
    "All models use the same source dataset and frozen evaluation split, but their internal "
    "representations are model-specific: SVM/Random Forest/XGBoost use TF-IDF word/char n-grams "
    "+ count vectorizer + 23 deterministic CWE-89/CWE-295 security features; LSTM uses a "
    "from-scratch learned token embedding; CodeBERT uses a pretrained Transformer code "
    "representation, fine-tuned on this task. Representations are NOT identical across models."
)


def load_frozen(path):
    with open(path) as f:
        return json.load(f)


def _binary_f1(m):
    bcm = m["binary_confusion_matrix"]
    tp, fp, fn = bcm["tp"], bcm["fp"], bcm["fn"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def main():
    codebert = load_frozen(os.path.join(OUT_DIR, "test_metrics.json"))
    svm = load_frozen(os.path.join(ARTIFACT_DIR, "svm", "test_metrics.json"))
    rf = load_frozen(os.path.join(ARTIFACT_DIR, "random_forest", "test_metrics.json"))
    xgb = load_frozen(os.path.join(ARTIFACT_DIR, "xgboost", "test_metrics.json"))
    lstm = load_frozen(os.path.join(ARTIFACT_DIR, "lstm", "test_metrics.json"))

    rows = []
    for name, typ, m in [
        ("Linear SVM", "Classical ML", svm), ("Random Forest", "Classical ML", rf),
        ("XGBoost", "Boosted Tree ML", xgb), ("LSTM", "Deep Learning", lstm),
        ("CodeBERT", "Transformer/DL", codebert),
    ]:
        rows.append({
            "Model": name, "Type": typ,
            "Accuracy": round(m["accuracy"], 4), "Macro F1": round(m["macro_f1"], 4),
            "ROC-AUC": round(m["roc_auc"], 4) if m.get("roc_auc") is not None else None,
            "Binary F1": round(_binary_f1(m), 4), "FPR": round(m["false_positive_rate"], 4),
            "FNR": round(m["false_negative_rate"], 4),
        })

    with open(os.path.join(OUT_DIR, "comparison_with_ml.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    codebert_row = rows[-1]
    summary = {
        "feature_representation_caveat": FEATURE_REPRESENTATION_CAVEAT,
        "comparison_table": rows,
        "codebert_rank_by_macro_f1": sorted(rows, key=lambda r: -r["Macro F1"]).index(codebert_row) + 1,
        "codebert_rank_by_fnr": sorted(rows, key=lambda r: r["FNR"]).index(codebert_row) + 1,
        "best_macro_f1_model": max(rows, key=lambda r: r["Macro F1"])["Model"],
        "best_fnr_model": min(rows, key=lambda r: r["FNR"])["Model"],
        "best_fpr_model": min(rows, key=lambda r: r["FPR"])["Model"],
        "note": "Ranks are 1=best. No claim of 'CodeBERT is better' is made unless the table itself supports it.",
    }
    with open(os.path.join(OUT_DIR, "comparison_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    make_plots(rows)

    print(json.dumps(rows, indent=2, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("comparison_table", "feature_representation_caveat")}, indent=2))
    return rows, summary


def make_plots(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    plots_dir = os.path.join(OUT_DIR, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    names = [r["Model"] for r in rows]
    fig, ax = plt.subplots(figsize=(9.5, 5))
    x = range(len(names))
    width = 0.2
    ax.bar([i - 1.5 * width for i in x], [r["Accuracy"] for r in rows], width, label="Accuracy")
    ax.bar([i - 0.5 * width for i in x], [r["Macro F1"] for r in rows], width, label="Macro F1")
    ax.bar([i + 0.5 * width for i in x], [r["FNR"] for r in rows], width, label="FNR")
    ax.bar([i + 1.5 * width for i in x], [r["FPR"] for r in rows], width, label="FPR")
    ax.set_xticks(list(x)); ax.set_xticklabels(names)
    ax.set_title("SVM vs RF vs XGBoost vs LSTM vs CodeBERT (frozen 168-row test set)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "model_comparison.png"), dpi=150); plt.close(fig)

    with open(os.path.join(ARTIFACT_DIR, "svm", "test_metrics.json")) as f:
        svm_full = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "random_forest", "test_metrics.json")) as f:
        rf_full = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "xgboost", "test_metrics.json")) as f:
        xgb_full = json.load(f)
    with open(os.path.join(ARTIFACT_DIR, "lstm", "cwe_metrics.csv"), newline="") as f:
        lstm_cwe_rows = list(csv.DictReader(f))
    with open(os.path.join(OUT_DIR, "cwe_metrics.csv"), newline="") as f:
        codebert_cwe_rows = list(csv.DictReader(f))

    def vs(full, key):
        recall = full["vulnerability_specific"][key].get("recall")
        return 1 - recall if recall is not None else None

    cwe89_fnr = {
        "SVM": vs(svm_full, "sql_injection_cwe_89"), "RF": vs(rf_full, "sql_injection_cwe_89"),
        "XGBoost": vs(xgb_full, "sql_injection_cwe_89"),
        "LSTM": float(next(r["fnr"] for r in lstm_cwe_rows if r["cwe"] == "CWE-89")),
        "CodeBERT": float(next(r["fnr"] for r in codebert_cwe_rows if r["cwe"] == "CWE-89")),
    }
    cwe295_fnr = {
        "SVM": vs(svm_full, "certificate_validation_cwe_295"), "RF": vs(rf_full, "certificate_validation_cwe_295"),
        "XGBoost": vs(xgb_full, "certificate_validation_cwe_295"),
        "LSTM": float(next(r["fnr"] for r in lstm_cwe_rows if r["cwe"] == "CWE-295")),
        "CodeBERT": float(next(r["fnr"] for r in codebert_cwe_rows if r["cwe"] == "CWE-295")),
    }

    import numpy as np
    fig, ax = plt.subplots(figsize=(9, 5))
    xarr = np.arange(len(cwe89_fnr))
    width = 0.35
    names2 = list(cwe89_fnr.keys())
    ax.bar(xarr - width / 2, [cwe89_fnr[n] for n in names2], width, label="CWE-89 FNR", color="teal")
    ax.bar(xarr + width / 2, [cwe295_fnr[n] for n in names2], width, label="CWE-295 FNR", color="indianred")
    ax.set_xticks(xarr); ax.set_xticklabels(names2)
    ax.set_ylabel("FNR"); ax.set_title("CWE-89 vs CWE-295 FNR by model")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(plots_dir, "cwe_comparison.png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
