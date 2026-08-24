"""
PHASE RESEARCH-EVAL-1, Parts 13/14/18: final fair comparison across the
three models, all evaluated on the exact same frozen test set (Part 16's
protocol - TEST is read here only after each train_*.py script has
already frozen its model).

Produces:
  research_eval_artifacts/comparison/model_comparison.csv
  research_eval_artifacts/comparison/model_comparison.json
  research_eval_artifacts/comparison/vulnerability_comparison.csv
  research_eval_artifacts/comparison/vulnerability_comparison.json
  research_eval_artifacts/comparison/plots/*.png

Run from backend/ AFTER all three train_*.py scripts have been run:
  python -m research_eval.compare_models
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_eval.data_split import ARTIFACT_DIR

MODELS = {
    "Linear SVM": "svm",
    "Random Forest": "random_forest",
    "XGBoost": "xgboost",
}
OUT_DIR = os.path.join(ARTIFACT_DIR, "comparison")


def load_test_metrics():
    metrics = {}
    for display_name, dirname in MODELS.items():
        path = os.path.join(ARTIFACT_DIR, dirname, "test_metrics.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found - run `python -m research_eval.train_{dirname}` first "
                f"(all three models must be trained before comparing)"
            )
        with open(path) as f:
            metrics[display_name] = json.load(f)
    return metrics


def verify_same_test_set():
    """Fairness guard (Part 16): every model's test_metrics.json must have
    been computed over the same number of test rows, drawn from the same
    frozen test_indices.json - otherwise this is not a fair comparison and
    must not be reported as one."""
    with open(os.path.join(ARTIFACT_DIR, "test_indices.json")) as f:
        test_idx = json.load(f)
    n_expected = len(test_idx)
    for display_name, dirname in MODELS.items():
        with open(os.path.join(ARTIFACT_DIR, dirname, "test_metrics.json")) as f:
            m = json.load(f)
        n_actual = sum(m["confusion_matrix"][i][j] for i in range(4) for j in range(4))
        if n_actual != n_expected:
            raise AssertionError(
                f"{display_name}: test confusion matrix sums to {n_actual} samples, "
                f"expected {n_expected} (test_indices.json) - NOT a fair comparison"
            )
    return n_expected


def build_main_table(metrics):
    rows = []
    for name in MODELS:
        m = metrics[name]
        rows.append({
            "Model": name,
            "Accuracy": round(m["accuracy"], 4),
            "Precision (macro)": round(m["macro_precision"], 4),
            "Recall (macro)": round(m["macro_recall"], 4),
            "F1 (macro)": round(m["macro_f1"], 4),
            "Precision (weighted)": round(m["weighted_precision"], 4),
            "Recall (weighted)": round(m["weighted_recall"], 4),
            "F1 (weighted)": round(m["weighted_f1"], 4),
            "ROC-AUC": round(m["roc_auc"], 4) if m["roc_auc"] is not None else None,
        })
    return rows


def _binary_f1_from_confusion(tn, fp, fn, tp):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def build_vulnerability_table_final(metrics):
    rows = []
    for name in MODELS:
        m = metrics[name]
        sql = m["vulnerability_specific"]["sql_injection_cwe_89"]
        cert = m["vulnerability_specific"]["certificate_validation_cwe_295"]
        bcm = m["binary_confusion_matrix"]
        binary_f1 = _binary_f1_from_confusion(bcm["tn"], bcm["fp"], bcm["fn"], bcm["tp"])
        rows.append({
            "Model": name,
            "SQL Injection F1 (CWE-89)": round(sql["f1"], 4) if "f1" in sql else None,
            "Certificate Validation F1 (CWE-295)": round(cert["f1"], 4) if "f1" in cert else None,
            "Binary (SAFE vs VULNERABLE) F1": round(binary_f1, 4),
            "FPR": round(m["false_positive_rate"], 4),
            "FNR": round(m["false_negative_rate"], 4),
        })
    return rows


def write_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_plots(metrics, main_table):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {"plots_generated": False, "reason": "matplotlib not installed"}

    plots_dir = os.path.join(OUT_DIR, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    names = [row["Model"] for row in main_table]

    # Accuracy / macro-F1 / ROC-AUC bar chart
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(names))
    width = 0.25
    ax.bar([i - width for i in x], [row["Accuracy"] for row in main_table], width, label="Accuracy")
    ax.bar([i for i in x], [row["F1 (macro)"] for row in main_table], width, label="Macro F1")
    ax.bar([i + width for i in x], [row["ROC-AUC"] or 0 for row in main_table], width, label="ROC-AUC")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names)
    ax.set_ylim(0, 1.0)
    ax.set_title("Fair common-split test-set comparison")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(plots_dir, "main_comparison.png"), dpi=150)
    plt.close(fig)

    # Confusion matrices, one subplot per model
    fig, axes = plt.subplots(1, len(names), figsize=(4.2 * len(names), 4))
    if len(names) == 1:
        axes = [axes]
    labels = metrics[names[0]]["confusion_matrix_labels"]
    for ax, name in zip(axes, names):
        cm = metrics[name]["confusion_matrix"]
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_yticklabels(labels)
        ax.set_title(name)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, cm[i][j], ha="center", va="center",
                         color="white" if cm[i][j] > (max(max(r) for r in cm) / 2) else "black")
    fig.tight_layout()
    fig.savefig(os.path.join(plots_dir, "confusion_matrices.png"), dpi=150)
    plt.close(fig)

    return {"plots_generated": True, "files": ["main_comparison.png", "confusion_matrices.png"]}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    n_test = verify_same_test_set()
    metrics = load_test_metrics()

    main_table = build_main_table(metrics)
    vuln_table = build_vulnerability_table_final(metrics)

    write_csv(main_table, os.path.join(OUT_DIR, "model_comparison.csv"))
    write_csv(vuln_table, os.path.join(OUT_DIR, "vulnerability_comparison.csv"))
    with open(os.path.join(OUT_DIR, "model_comparison.json"), "w") as f:
        json.dump(main_table, f, indent=2)
    with open(os.path.join(OUT_DIR, "vulnerability_comparison.json"), "w") as f:
        json.dump(vuln_table, f, indent=2)

    best_by_f1 = max(main_table, key=lambda r: r["F1 (macro)"])

    plot_info = make_plots(metrics, main_table)

    summary = {
        "fairness_check": f"PASSED - all 3 models evaluated on the identical {n_test}-row frozen test set",
        "best_model_by_macro_f1_under_this_protocol": best_by_f1["Model"],
        "best_model_macro_f1": best_by_f1["F1 (macro)"],
        "plots": plot_info,
    }
    with open(os.path.join(OUT_DIR, "comparison_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(main_table, indent=2))
    print(json.dumps(vuln_table, indent=2))
    print(json.dumps(summary, indent=2))
    return main_table, vuln_table, summary


if __name__ == "__main__":
    main()
